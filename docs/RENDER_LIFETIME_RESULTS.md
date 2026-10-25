# Render lifetime verification (2026-10-26)

Base: e91ca29. Branch: `fix/render-resource-lifetime`. Runtime files are unchanged;
this branch adds regression coverage and records the investigation, not a claimed
RAM optimization. Ponytail/Modularity favor a demonstrated correction over an
unverified cleanup timer, forced GC, restart or reduced visual quality.

## Ownership on the laptop

The owner's Quickshell instance list identifies the long-running main shell and
a standalone `settings.qml` instance. At e91ca29, the owner reports 186.12 MB
inclusive PSS after normal Settings close, with no Settings Quickshell/backend
remaining. The earlier two-instance inventory was 318.27 MB PSS; its 633.77 MB
summed RSS double-counts shared pages. Both reported PSS totals fit their budgets.
These are separate snapshots, not a controlled before/after saving. Theme, warmed
24/48-cycle and simultaneous Settings-open samples are still requested. Independent
wallpaper daemons/shared helpers still require ownership review.

## Repeatable private characterization

`LME_TEST_RENDER_LIFETIME=1 python3 -m unittest -v test_render_lifetime` inside the
disposable gate session runs two tests against a copied checkout. Production code
is unmodified. The copy gains counters, not runtime hooks in the real checkout.

- Two Settings open/close/reopen iterations: first frame prepared, no history
  worker in Settings, close-request signal (the X handler) exits successfully,
  its two processes disappear, original main/backend/history PIDs remain usable.
  The signal is injected in the copy; this does not claim a physical mouse test.
- Forty-eight Liquid/Jelly-v2 popup cycles: clipboard, Controls, Activity,
  Notifications, launcher and power, eight rounds. After every close, material,
  optics, backdrop and Jelly object counts equal their initial values; both
  Jelly layers are disabled, Loaders unmounted, pending empty. Process IDs stay
  fixed. The remaining backdrop/consumer belongs to the visible bar (1/1/0 regions).
- Real private history worker, synthetic backend, bundled wallpaper texture,
  one 1920x1080 output, software OpenGL/pixman, animations and texture resolution
  unchanged. Synthetic battery alerts are off so startup toasts cannot interfere.
  Settings navigation/readiness remains available after the workload.

Complete-counter total PSS, decimal MB, no outside-scope LME processes:

| Liquid scenario | PIDs | PSS MB |
| --- | ---: | ---: |
| Shell plus Settings, before cycles | 5 | 406.07 |
| After 6 / 12 / 18 cycles | 5 | 754.19 / 770.71 / 781.48 |
| After 24 / 30 / 36 cycles | 5 | 783.69 / 783.42 / 785.51 |
| After 42 / 48 cycles | 5 | 786.64 / 786.73 |
| Separate close test: main only | 3 | 226.43 |
| Settings open / closed, iteration 1 | 5 / 3 | 483.83 / 227.84 |
| Settings open / closed, iteration 2 | 5 / 3 | 471.99 / 227.38 |

The warmed VM still **fails** the 500 MB active target. Growth slows markedly
after warming, but these samples do not establish an indefinitely bounded plateau
or rule out leaks inside Qt/driver/allocator. QObject counts and layer flags do
not measure actual GPU texture destruction. No specific native allocation owner
has been established. Hardware GPU and niri compositor blur need a real session.

## Scratch experiments, not shipped fixes

- Disabling Jelly still produced strong warm-up growth (48-cycle total 896.49 MB).
  Thus removing Jelly is insufficient; that run is diagnostic, not a direct
  before/after comparison with the separate characterization run above.
- One llvmpipe thread still exceeded budget (839.33 MB after 48 cycles). No
  renderer/thread environment change is shipped or recommended for the laptop.
- Paired fresh copies, same 24 Activity cycles with Settings: automatic versus
  fixed maximum layer texture size ended at 748.75 versus 748.47 MB, from
  483.04 versus 483.61 MB. This provides no useful saving; the candidate was
  discarded. Blur, resolution, animations and resource policy remain unchanged.
- A further paired 18-cycle probe with default glibc arenas versus
  `MALLOC_ARENA_MAX=2` ended at 786.97 versus 763.33 MB (initial 482.98/472.99).
  Both miss the active budget; this single pair does not establish a reliable
  saving or safe allocation-contention/FPS trade-off. No allocator flag ships.

Initial uncommitted harness trials hit a startup-toast/count race and a pointer
delivery failure; setup now excludes synthetic alerts and exercises the actual
close-request signal. A concurrent scratch run made /proc counters unreadable
across sandbox parents; those incomplete runs are excluded. The final two native
tests ran sequentially, 2 passed / 0 failed / 0 skipped (81.144 s).

No production retention fix has been justified. Release memory approval remains
pending the requested warmed laptop samples; see RELEASE_CHECKLIST.md. Do not
call the VM budget passed or the shell "100% validated" from these results.
