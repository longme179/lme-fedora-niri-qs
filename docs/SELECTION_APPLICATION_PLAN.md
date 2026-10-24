# Selection/application action family

2026-10-24. Branch `refactor/selection-application-actions`, main `2390d8d`.
Owner authorized planning before coding, then execution on the same branch.
Ponytail/Modularity: extend existing domain providers; no new registry mechanism.

## Read contracts and scope

- `paletteApply`: validate preview colors first, then require the same image path
  and scheme/mode/contrast. Keep the existing Preferences.update transaction,
  lowercased palette/accent and element overrides; demo remains an unconditional no-op.
- `glassBlurApply`: call the existing liquid_glass.apply_blur service with the
  current preferences directory/values. Preserve generated marker, owned-file
  protection, atomic write, exact returned path/message and demo no-op.
- `gowallSetup`: check every pending gowall prefix before validating the source
  or choosing a terminal. Existing ImageUtilities.setup owns literal argv,
  Launchpad job/log behavior and terminal choice; demo stays permissive/no-op.
- `weatherSelect`: use weather.location unchanged, then reject the empty place.
  Live Preferences.update persists both location and automatic=false together;
  demo updates memory only. WeatherClient scheduling/lifecycle stays unchanged.
- All four permit shell and Settings before demo/live selection. Preserve
  result/sequence/client serial, error truncation, pending state and snapshots.
  Unknown prefixes retain legacy routing (including permissive demo gowall).

## Plan before implementation

1. Commit this plan; add characterization covering the four context/demo paths,
   validation/error ordering, transaction/state bytes, service calls and demo
   zero-I/O. Show it passing on unchanged main; ownership-only test is N/A there.
2. Extend palette_actions, gowall_actions and weather_actions capabilities with
   narrow callbacks; expose glass registration alongside the existing service.
   Delete the exact live/demo branches and four legacy admission IDs together.
   Keep public helper/import facades and all old assertions/fixtures unchanged.
3. During work run G0 plus affected/backend/registry units. On final runtime/test
   head run G0-G4/G6 once in disposable XDG/Sway/D-Bus, then one ten-launch
   preview/Settings main/head sanity and QS/backend RSS at 10 seconds.
4. Record final gates, adapters and laptop checks in <=30 migration lines; push a
   review branch/draft PR and stop. No main merge or later roadmap family.

No processes, executors, queues, timers, dependencies, schema/UI changes, A6 or D1
work. Shared runner and transaction/lifecycle owners stay. Explicit discovery
retires only with descriptor ownership/withdrawal/fallback parity; public facades
require zero consumers and owner approval. Actual niri blur/upscale/terminal/GPU
behavior needs real-session check; private VM results do not prove total RAM.

## Execution result

Implemented on runtime/test head a490075 after baseline characterization 4209727.
Seven baseline cases pass; one ownership-only N/A becomes a pass after extraction.
Old assertions/fixtures stay unchanged. Four sync entries extend existing providers
and the glass service; no new provider file/process or compatibility mechanism.
Final gates, one branch sanity and pending laptop checks are in MIGRATION_LOG.md.
No subsequent family is implemented or authorized by this branch.
