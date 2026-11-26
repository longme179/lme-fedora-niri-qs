// fakeshell.c — sandbox drill stand-in for Quickshell (scripts/perf/standin.py drill).
// argv is kept verbatim, so /proc/<pid>/cmdline looks like the real thing:
//   <...>/bin/quickshell -c lme-shell --no-duplicate     main shell: stays alive
//   <...>/bin/quickshell -p .../settings.qml             Settings: stays alive
//   <...>/bin/quickshell -c lme-shell ipc call lock status | probe ping
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static int has(char **argv, const char *needle) {
    for (; *argv; argv++)
        if (!strcmp(*argv, needle)) return 1;
    return 0;
}

/* any live pid (other than `self`) listed in the file */
static int alive(const char *pidfile, pid_t self) {
    FILE *f = fopen(pidfile, "r");
    char line[64];
    int any = 0;
    if (!f) return 0;
    while (fgets(line, sizeof line, f)) {
        pid_t pid = (pid_t)strtol(line, NULL, 10);
        char path[64];
        struct stat st;
        if (pid > 0 && pid != self) {
            snprintf(path, sizeof path, "/proc/%d", pid);
            if (stat(path, &st) == 0) any = 1;
        }
    }
    fclose(f);
    return any;
}

int main(int argc, char **argv) {
    const char *home = getenv("HOME");
    char path[4096], lockfile[4096];
    FILE *f;
    int settings;
    (void)argc;
    if (!home || strlen(home) > 3000) return 3;
    snprintf(lockfile, sizeof lockfile, "%s/.fake/locked", home);
    if (getenv("FAKE_IPC_SILENT") && has(argv, "ipc")) sleep(3600);  /* drill: a frozen event loop */
    if (has(argv, "ipc")) {
        if (has(argv, "lock") && has(argv, "status")) {
            puts(access(lockfile, F_OK) == 0 ? "locked" : "unlocked");
        } else if (has(argv, "probe") && has(argv, "ping")) {
            struct timespec ts;
            clock_gettime(CLOCK_MONOTONIC, &ts);
            printf("%lld\n", (long long)ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
        }
        return 0;
    }
    settings = has(argv, "-p");
    if (getenv("FAKE_FAIL_START")) return 7;  /* drill: this shell dies at startup */
    snprintf(path, sizeof path, "%s/.fake/%s.pids", home, settings ? "settings" : "main");
    if (!settings && has(argv, "--no-duplicate") && alive(path, getpid())) return 0;  /* instance exists */
    f = fopen(path, "a");
    if (f) { fprintf(f, "%d\n", getpid()); fflush(f); fclose(f); }
    if (access(lockfile, F_OK) == 0 && getenv("FAKE_SLEEP_WHEN_LOCKED")) sleep(3600);  /* drill: frozen loop */
    signal(SIGTERM, SIG_DFL);
    for (;;) pause();
}
