// SPDX-License-Identifier: AGPL-3.0-or-later
// uinput_inject.c - real-input injector for scripts/perf (harness tooling; never installed).
//
// Creates one virtual keyboard and one virtual absolute pointer through /dev/uinput. Events take
// the path of a physical device: kernel evdev -> compositor libinput -> seat -> focused surface,
// so key binds, focus, layer-shell keyboard interactivity and pointer delivery are all the
// compositor's real ones (ydotool's route, without the ydotool dependency).
//
// Long-lived by design (creating a device reconfigures the compositor seat): it reads one command
// per line on stdin and answers one `ok` line per command, stamped CLOCK_MONOTONIC and
// CLOCK_REALTIME right after the last event was written.
//
//   key NAME down|up        press / release (ESC, Tab, LeftCtrl, LeftMeta, comma, a..z, 1..9, or a number)
//   tap NAME... [hold=MS]   press in order, release in reverse order (modifiers first)
//   move X Y                absolute pointer position in output pixels
//   click left|right        press + release a button
//   sleep MS                wait
//   sync                    answer only (a timing fence for the driver)
//   release                 release every pressed key and button
//   quit
//
// Every event batch is echoed as `ev MONO_NS REAL_NS TYPE:CODE=VALUE ...`. stdin closing, SIGTERM
// or DEADMAN_MS without a command releases everything, so nothing can stay held if the driver dies.
//
// Build: gcc -O2 -Wall -o uinput_inject uinput_inject.c
// Needs write access to /dev/uinput (logind grants it to the active seat user on Fedora).
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define ABS_RANGE 32767
#define MAX_CHORD 8

static int kbd_fd = -1, ptr_fd = -1;
static int out_w = 1920, out_h = 1080;
static long deadman_ms = 3000, settle_ms = 600, click_hold_ms = 8;
static bool key_down[KEY_MAX + 1];
static bool btn_down[KEY_MAX + 1];
static volatile sig_atomic_t interrupted;
static uint64_t seq;

// One event batch: written with a single write(), SYN_REPORT appended, then logged.
static struct {
    struct input_event ev[MAX_CHORD + 2];
    size_t n;
    int fd;
    char desc[256];
    size_t desc_len;
} pending;

static uint64_t now_ns(clockid_t clk) {
    struct timespec ts;
    clock_gettime(clk, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static void out_line(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void out_line(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    putchar('\n');
    fflush(stdout);
}

static void emit(int fd, uint16_t type, uint16_t code, int32_t value) {
    if (pending.n == sizeof(pending.ev) / sizeof(pending.ev[0]) - 1) return;
    struct input_event *ev = &pending.ev[pending.n++];
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ev->input_event_sec = ts.tv_sec;
    ev->input_event_usec = ts.tv_nsec / 1000;
    ev->type = type;
    ev->code = code;
    ev->value = value;
    pending.fd = fd;
    int len = snprintf(pending.desc + pending.desc_len, sizeof(pending.desc) - pending.desc_len,
                       "%s%u:%u=%d", pending.desc_len ? " " : "", type, code, value);
    if (len > 0 && (size_t)len < sizeof(pending.desc) - pending.desc_len) pending.desc_len += (size_t)len;
}

static void flush(void) {
    if (!pending.n) return;
    struct input_event *syn = &pending.ev[pending.n++];
    syn->input_event_sec = pending.ev[0].input_event_sec;
    syn->input_event_usec = pending.ev[0].input_event_usec;
    syn->type = EV_SYN;
    syn->code = SYN_REPORT;
    syn->value = 0;
    size_t bytes = pending.n * sizeof(struct input_event);
    if (write(pending.fd, pending.ev, bytes) != (ssize_t)bytes)
        out_line("err write %s", strerror(errno));
    out_line("ev %" PRIu64 " %" PRIu64 " %s", now_ns(CLOCK_MONOTONIC), now_ns(CLOCK_REALTIME), pending.desc);
    pending.n = 0;
    pending.desc_len = 0;
    pending.desc[0] = 0;
}

static void msleep(long ms) {
    struct timespec ts = { .tv_sec = ms / 1000, .tv_nsec = (ms % 1000) * 1000000L };
    while (!interrupted && nanosleep(&ts, &ts) == -1 && errno == EINTR) {}
}

static void on_signal(int sig) { (void)sig; interrupted = 1; }

static int open_uinput(void) {
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (fd < 0) {
        out_line("err open /dev/uinput: %s", strerror(errno));
        exit(1);
    }
    return fd;
}

// Finalizes a device whose capability bits are already set on `fd`.
static int create_device_on(int fd, const char *name, int product, int abs_max) {
    struct uinput_user_dev user;
    memset(&user, 0, sizeof user);
    snprintf(user.name, UINPUT_MAX_NAME_SIZE, "%s", name);
    user.id.bustype = BUS_USB;
    user.id.vendor = 0x1;
    user.id.product = (__u16)product;
    user.id.version = 1;
    // The range of an absolute axis is part of this struct, read for every ABS bit that is
    // already set. Left at 0 the axis is [0, 0], libinput drops it and the pointer never moves.
    user.absmin[ABS_X] = 0;
    user.absmax[ABS_X] = abs_max;
    user.absmin[ABS_Y] = 0;
    user.absmax[ABS_Y] = abs_max;
    if (write(fd, &user, sizeof user) != (ssize_t)sizeof user) {
        out_line("err uinput setup write: %s", strerror(errno));
        exit(1);
    }
    if (ioctl(fd, UI_DEV_CREATE) < 0) {
        out_line("err UI_DEV_CREATE: %s", strerror(errno));
        exit(1);
    }
    return fd;
}

static int setup_kbd(void) {
    int fd = open_uinput();
    ioctl(fd, UI_SET_EVBIT, EV_SYN);
    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    ioctl(fd, UI_SET_EVBIT, EV_MSC);
    ioctl(fd, UI_SET_EVBIT, EV_REP);
    // 1..0xff: every key code and no button code, so the device is a pure keyboard.
    for (int code = 1; code < 0x100; ++code) ioctl(fd, UI_SET_KEYBIT, (unsigned long)code);
    return create_device_on(fd, "LME Perf Harness Keyboard", 1, 0);
}

static int setup_ptr(void) {
    int fd = open_uinput();
    ioctl(fd, UI_SET_EVBIT, EV_SYN);
    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    ioctl(fd, UI_SET_EVBIT, EV_ABS);
    ioctl(fd, UI_SET_EVBIT, EV_REL);      // the wheel: REL_WHEEL clicks (see "wheel")
    ioctl(fd, UI_SET_KEYBIT, BTN_LEFT);
    ioctl(fd, UI_SET_KEYBIT, BTN_RIGHT);
    ioctl(fd, UI_SET_ABSBIT, ABS_X);
    ioctl(fd, UI_SET_ABSBIT, ABS_Y);
    ioctl(fd, UI_SET_RELBIT, REL_WHEEL);
    ioctl(fd, UI_SET_PROPBIT, INPUT_PROP_POINTER);
    return create_device_on(fd, "LME Perf Harness Pointer", 2, ABS_RANGE);
}

static const struct { const char *name; int code; } KEYS[] = {
    {"esc", KEY_ESC}, {"escape", KEY_ESC},
    {"1", KEY_1}, {"2", KEY_2}, {"3", KEY_3}, {"4", KEY_4}, {"5", KEY_5},
    {"6", KEY_6}, {"7", KEY_7}, {"8", KEY_8}, {"9", KEY_9}, {"0", KEY_0},
    {"minus", KEY_MINUS}, {"equal", KEY_EQUAL}, {"backspace", KEY_BACKSPACE},
    {"tab", KEY_TAB}, {"enter", KEY_ENTER}, {"return", KEY_ENTER}, {"kpenter", KEY_KPENTER},
    {"space", KEY_SPACE},
    // Punctuation, for the shell's own binds (Settings is Mod+Comma on niri).
    {"comma", KEY_COMMA}, {"period", KEY_DOT}, {"dot", KEY_DOT}, {"slash", KEY_SLASH},
    {"semicolon", KEY_SEMICOLON}, {"apostrophe", KEY_APOSTROPHE}, {"grave", KEY_GRAVE},
    {"leftbrace", KEY_LEFTBRACE}, {"rightbrace", KEY_RIGHTBRACE}, {"backslash", KEY_BACKSLASH},
    {"kpcomma", KEY_KPCOMMA}, {"kpdot", KEY_KPDOT}, {"kpslash", KEY_KPSLASH},
    {"kpasterisk", KEY_KPASTERISK}, {"kpplus", KEY_KPPLUS}, {"kpminus", KEY_KPMINUS},
    {"a", KEY_A}, {"b", KEY_B}, {"c", KEY_C}, {"d", KEY_D}, {"e", KEY_E}, {"f", KEY_F},
    {"g", KEY_G}, {"h", KEY_H}, {"i", KEY_I}, {"j", KEY_J}, {"k", KEY_K}, {"l", KEY_L},
    {"m", KEY_M}, {"n", KEY_N}, {"o", KEY_O}, {"p", KEY_P}, {"q", KEY_Q}, {"r", KEY_R},
    {"s", KEY_S}, {"t", KEY_T}, {"u", KEY_U}, {"v", KEY_V}, {"w", KEY_W}, {"x", KEY_X},
    {"y", KEY_Y}, {"z", KEY_Z},
    {"leftctrl", KEY_LEFTCTRL}, {"ctrl", KEY_LEFTCTRL}, {"rightctrl", KEY_RIGHTCTRL},
    {"leftshift", KEY_LEFTSHIFT}, {"shift", KEY_LEFTSHIFT}, {"rightshift", KEY_RIGHTSHIFT},
    {"leftalt", KEY_LEFTALT}, {"alt", KEY_LEFTALT}, {"rightalt", KEY_RIGHTALT},
    {"leftmeta", KEY_LEFTMETA}, {"meta", KEY_LEFTMETA}, {"super", KEY_LEFTMETA},
    {"leftsuper", KEY_LEFTMETA}, {"rightmeta", KEY_RIGHTMETA},
    {"capslock", KEY_CAPSLOCK},
    {"up", KEY_UP}, {"down", KEY_DOWN}, {"left", KEY_LEFT}, {"right", KEY_RIGHT},
    {"home", KEY_HOME}, {"end", KEY_END}, {"pageup", KEY_PAGEUP}, {"pagedown", KEY_PAGEDOWN},
    {"insert", KEY_INSERT}, {"delete", KEY_DELETE},
    {"f1", KEY_F1}, {"f2", KEY_F2}, {"f3", KEY_F3}, {"f4", KEY_F4}, {"f5", KEY_F5}, {"f6", KEY_F6},
    {"f7", KEY_F7}, {"f8", KEY_F8}, {"f9", KEY_F9}, {"f10", KEY_F10}, {"f11", KEY_F11}, {"f12", KEY_F12},
    {"play", KEY_PLAYPAUSE}, {"next", KEY_NEXTSONG}, {"prev", KEY_PREVIOUSSONG},
    {"volup", KEY_VOLUMEUP}, {"voldown", KEY_VOLUMEDOWN}, {"mute", KEY_MUTE},
    {"brightup", KEY_BRIGHTNESSUP}, {"brightdown", KEY_BRIGHTNESSDOWN},
};

// A table name, or a raw linux event code.
static int key_code(const char *name) {
    for (size_t i = 0; i < sizeof(KEYS) / sizeof(KEYS[0]); ++i)
        if (!strcasecmp(KEYS[i].name, name)) return KEYS[i].code;
    char *end = NULL;
    long code = strtol(name, &end, 0);
    if (end && *end == '\0' && code > 0 && code <= KEY_MAX) return (int)code;
    return -1;
}

static int release_all(void) {
    int released = 0;
    for (int code = 1; code <= KEY_MAX; ++code) {
        if (key_down[code]) { emit(kbd_fd, EV_KEY, (__u16)code, 0); key_down[code] = false; released++; }
    }
    flush();
    for (int code = BTN_LEFT; code <= BTN_RIGHT; ++code) {
        if (btn_down[code]) { emit(ptr_fd, EV_KEY, (__u16)code, 0); btn_down[code] = false; released++; }
    }
    flush();
    return released;
}

static void cleanup(void) {
    release_all();
    if (kbd_fd >= 0) { ioctl(kbd_fd, UI_DEV_DESTROY); close(kbd_fd); kbd_fd = -1; }
    if (ptr_fd >= 0) { ioctl(ptr_fd, UI_DEV_DESTROY); close(ptr_fd); ptr_fd = -1; }
}

static long clamp_long(long v, long lo, long hi) { return v < lo ? lo : v > hi ? hi : v; }

// Commands return 0, or -1 when the driver asked to quit. The reply is stamped after the work.
static int handle_line(char *original) {
    char *line = original;
    while (*line == ' ' || *line == '\t' || *line == '\r') line++;
    size_t len = strlen(line);
    while (len && (line[len - 1] == '\r' || line[len - 1] == ' ' || line[len - 1] == '\t')) line[--len] = 0;
    if (!len) return 0;
    char work[512];
    snprintf(work, sizeof work, "%s", line);
    char *save = NULL;
    char *cmd = strtok_r(work, " \t", &save);
    int quit = 0, bad = 0;
    if (!strcmp(cmd, "key")) {
        char *name = strtok_r(NULL, " \t", &save), *how = strtok_r(NULL, " \t", &save);
        int code = name ? key_code(name) : -1;
        if (code < 0 || !how) bad = 1;
        else if (!strcmp(how, "down")) { if (!key_down[code]) { emit(kbd_fd, EV_KEY, (__u16)code, 1); flush(); } key_down[code] = true; }
        else if (!strcmp(how, "up")) { if (key_down[code]) { emit(kbd_fd, EV_KEY, (__u16)code, 0); flush(); } key_down[code] = false; }
        else bad = 1;
    } else if (!strcmp(cmd, "tap")) {
        int codes[MAX_CHORD], n = 0;
        long hold = 10;
        for (char *tok = strtok_r(NULL, " \t", &save); tok; tok = strtok_r(NULL, " \t", &save)) {
            if (!strncmp(tok, "hold=", 5)) { hold = atol(tok + 5); continue; }
            int code = key_code(tok);
            if (code < 0 || n == MAX_CHORD) { bad = 1; break; }
            codes[n++] = code;
        }
        if (n && !bad) {
            for (int i = 0; i < n; ++i) { emit(kbd_fd, EV_KEY, (__u16)codes[i], 1); key_down[codes[i]] = true; flush(); }
            msleep(hold);
            for (int i = n - 1; i >= 0; --i) { emit(kbd_fd, EV_KEY, (__u16)codes[i], 0); key_down[codes[i]] = false; flush(); }
        }
    } else if (!strcmp(cmd, "move")) {
        char *xs = strtok_r(NULL, " \t", &save), *ys = strtok_r(NULL, " \t", &save);
        if (!xs || !ys) bad = 1;
        else {
            long x = clamp_long(atol(xs), 0, out_w - 1), y = clamp_long(atol(ys), 0, out_h - 1);
            emit(ptr_fd, EV_ABS, ABS_X, (__s32)(x * ABS_RANGE / (out_w - 1)));
            emit(ptr_fd, EV_ABS, ABS_Y, (__s32)(y * ABS_RANGE / (out_h - 1)));
            flush();
        }
    } else if (!strcmp(cmd, "click")) {
        char *which = strtok_r(NULL, " \t", &save), *hold = strtok_r(NULL, " \t", &save);
        int code = !which || !strcmp(which, "left") ? BTN_LEFT : !strcmp(which, "right") ? BTN_RIGHT : -1;
        if (code < 0) bad = 1;
        else {
            long ms = hold ? atol(hold) : click_hold_ms;
            emit(ptr_fd, EV_KEY, (__u16)code, 1); btn_down[code] = true; flush();
            msleep(ms);
            emit(ptr_fd, EV_KEY, (__u16)code, 0); btn_down[code] = false; flush();
        }
    } else if (!strcmp(cmd, "wheel")) {
        // A notch of the wheel: REL_WHEEL with a click count (positive = up, away from
        // the user). Sent on the pointer device, like a real mouse wheel.
        char *deltas = strtok_r(NULL, " \t", &save);
        if (!deltas) bad = 1;
        else {
            long steps = atol(deltas);
            if (steps < -20 || steps > 20) bad = 1;
            else {
                emit(ptr_fd, EV_REL, REL_WHEEL, (__s32)steps); flush();
            }
        }
    } else if (!strcmp(cmd, "sleep")) {
        char *ms = strtok_r(NULL, " \t", &save);
        if (!ms) bad = 1; else msleep(atol(ms));
    } else if (!strcmp(cmd, "sync") || !strcmp(cmd, "ping")) {
        ; // a timing fence: the reply carries the stamps
    } else if (!strcmp(cmd, "release")) {
        release_all();
    } else if (!strcmp(cmd, "quit")) {
        quit = 1;
    } else {
        bad = 1;
    }
    out_line("%s %" PRIu64 " %" PRIu64 " %" PRIu64 " %s", bad ? "bad" : "ok", ++seq,
             now_ns(CLOCK_MONOTONIC), now_ns(CLOCK_REALTIME), line);
    return bad ? -2 : quit ? -1 : 0;
}

int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--width") && i + 1 < argc) out_w = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--height") && i + 1 < argc) out_h = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--deadman-ms") && i + 1 < argc) deadman_ms = atol(argv[++i]);
        else if (!strcmp(argv[i], "--settle-ms") && i + 1 < argc) settle_ms = atol(argv[++i]);
        else if (!strcmp(argv[i], "--hold-ms") && i + 1 < argc) click_hold_ms = atol(argv[++i]);
        else { fprintf(stderr, "usage: uinput_inject [--width W] [--height H] [--deadman-ms MS] [--settle-ms MS] [--hold-ms MS]\n"); return 2; }
    }
    signal(SIGTERM, on_signal);
    signal(SIGINT, on_signal);
    signal(SIGPIPE, SIG_IGN);
    atexit(cleanup);
    kbd_fd = setup_kbd();
    ptr_fd = setup_ptr();
    // udev must tag both devices for the seat before the compositor's libinput adds them.
    msleep(settle_ms);
    out_line("ready %" PRIu64 " %" PRIu64, now_ns(CLOCK_MONOTONIC), now_ns(CLOCK_REALTIME));

    char buf[4096];
    size_t have = 0;
    while (!interrupted) {
        struct pollfd p = { .fd = STDIN_FILENO, .events = POLLIN, .revents = 0 };
        int r = poll(&p, 1, deadman_ms);
        if (r < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (r == 0) {
            // Dead man: the driver stopped commanding; nothing may stay pressed.
            if (release_all()) out_line("deadman");
            continue;
        }
        ssize_t n = read(STDIN_FILENO, buf + have, sizeof(buf) - have - 1);
        if (n <= 0) break;
        have += (size_t)n;
        buf[have] = 0;
        for (;;) {
            char *nl = memchr(buf, '\n', have);
            if (!nl) break;
            *nl = 0;
            int rc = handle_line(buf);
            size_t used = (size_t)(nl - buf) + 1;
            memmove(buf, buf + used, have - used);
            have -= used;
            if (rc == -1) interrupted = 1;
        }
        if (have == sizeof(buf) - 1) have = 0; // an over-long line without a newline: drop it
    }
    return 0;
}
