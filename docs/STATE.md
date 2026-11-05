# Agent state (2026-11-01)

Read this file at task start; consult ARCHITECTURE.md for contracts.
Do not read archive/ unless answering a specific historical question.
## Merged and authorized

- M0-M3, M4a/M4b, M5/M6, M4c-1/2/3, M7a/b/c/d, F1-F5, resource/lifecycle, Capture, Display preview, Mirroring and selection/application merged; registry including W2: 86/100 IDs (50 sync entry calls + 36 workers).
  Ten catalog pages; 79 descriptor keys/68 legacy; Clipboard bar converted; tab/bootstrap adapters implemented (19 catalog records, nine with empty startup UI metadata).
- D1 startup optimization CLOSED; further async conversions need authorization; M8 deferred.
- Roadmap accepted 100% (10/10) by owner on 2026-11-01: normal-use functionality tested, aggregate shell/process RAM reported at or below 400 MB in btop. This replaces the pending laptop/PSS acceptance gate; no new quantitative PSS/GPU measurement or RAM-saving fix is claimed. PR #42 is merged. W1 Audio/headset (PR #44) adds four on-demand workers and observed ports/profiles/routes; native revisions approved/applied, physical headset checks remain. PR #44 is merged (bcbb359). Launcher Gio lifetime fix PR #45 is merged (4e5fbf1); restart the shell after updating. W2 review branch feature/network-connections adds on-demand saved connections and confirmed secure hotspot activation; physical NM/keyring/AP/wired checks remain. W3+ is unauthorized. See AUDIO_HEADSET.md and NETWORK_CONNECTIONS.md.
- M1 (P-01…P-06) merged via PR #48; the G0/G1 follow-up merged via PR #49. M2 (P-07/P-09) merged via PR #50. M3 (P-10…P-12) is in progress on its own branch.
- A6 remains out of scope: no polling, cache or power-policy changes.
- Development skills: Ponytail full + .agents/skills/modularity/SKILL.md; use proportionately, without extra ceremony.
- Total-shell memory target: <=400 MB steady / <=500 MB ordinary active use, including workers and open Settings.
  Prefer aggregate PSS, label summed RSS limitations and temporary-job peaks; individual PID samples are not the total.

## In progress

- M3 (P-10…P-12) on fix/m3-diagnostics: theme files validate their shapes, keep safe defaults and expose `themeDiagnosticsText` in About; OSD output selection falls back from a missing named/all output to focused, panel then first screen; `ARCHITECTURE_AUDIT.md` is stamped superseded, the README indexes the audits and VALIDATION has a six-row hardware-check matrix. P-08 stayed skipped in M2.
- M3 verification: offscreen QML guard/fallback test green; G0 completed with 842 passed / 0 failed / 184 skipped and qmllint 153 files with 0 errors/warnings; G1 passed 9 / 0 failed / 0 skipped. Hardware matrix rows still need owner/laptop checks.

## Compatibility adapters and retirement

- Runner/errors/TOOLS, storage/content-type/image-path/peripheral-value/display-layout re-exports: retain until zero consumers plus owner-approved retirement.
- F3 legacy pending reducer retains old-peer/fixture fallback; retire only at zero legacy consumers plus owner approval. pendingActions and emit/handle/snapshot stay public facades.
- Integer controlTab/named env mapping: public compatibility; internal adapters retire after all callers/fixtures use stable IDs.
- Hybrid registry projections, legacy lists, legacy_ids() source bridge and panel
  allowlist: retire per namespace after its final legacy registration/fixture.
- ClipboardFeature -> ClipboardState.start(): retain until equivalent bootstrap
  preserves main-only once semantics and Settings/demo/preview guards.
- ClipboardButton -> ActionBarButton: retain until an equivalent entry preserves
  geometry, gestures and screen context. No Clipboard implementation files moved.
- Eight descriptor-provider domains (light + controller batches + audio + wifi): explicit fallback factories/narrow capabilities remain; disabled/missing entries keep actions, broken references retain legacy UI + diagnostic. W2 composes existing WifiCapabilities/provide; disabled wifi hides W2 UI only and retains legacy Wi-Fi/data. Others stay explicit. Retire fallbacks/import facades only with equivalent fault/withdrawal coverage + owner approval. PreparedWork/complete/presentation retain host scheduling/Future tags; Weather/Saver/Mirror keep lifecycle, journals and child ownership. Public perform/perform_demo/wifi_action facades retain their zero-consumer retirement rule and cadence.
- PageNavigation forwards navigateRequested(pageId); retain old page signals until owner-approved retirement.
- W1 audio composes the existing AudioCapabilities/provider facades and descriptor fallback; retain until zero consumers and owner-approved retirement. Demo projection excludes legacy launchpadJobs until an approved contract change. No new daemon/poller; routing requires verified server/object identity and read-back.
- Notifications.start/demo readiness and legacy bar availability guards retire only with equivalent catalog composition/worker isolation; public flags/IDs stay.
- DEFAULT_PREFERENCES/validate_preference and PORTABLE/APPEARANCE_KEYS are schema
  facades; retain public names until explicit owner-approved compatibility changes.
- Legacy fragment (68 keys), validator/default bindings, inventory, bar-layout resolver
  and bundled-fragment fallback retire at their last consumer/fault contract. Worker policy is separate.
- Architecture exceptions/size ceilings: remove vanished edges, lower shrunken
  large-file ceilings; no new cross-feature edges or cycles.

## Gates and working rules

- `./deploy.sh`: deployment plan/apply/rollback (DEPLOYMENT.md). `./scripts/check.sh`: architecture/catalog + unit discovery + Bash/demo checks.
- `python3 scripts/memory_report.py --label steady`: read-only PSS inventory; review ownership/partial counters before accepting totals.
- `./scripts/run-gates.sh --gates G0` isolates XDG, Sway/Wayland and D-Bus;
  optional `--env-file FILE --pointer-dir DIR`. Gate cases: tests/migration_checks.py.
- During work: Python = G0 + relevant units; QML = G0 + G1 + relevant native case.
  Runtime branches: full G0-G4 + G6 polling ONCE before merge review; explicit task scope overrides.
  Docs/skills-only: G0 only, no GUI gates/sanity. Report actual pass/fail/skip counts and reasons.
- Tests first, then implementation, then docs. No assertion edits without asking;
  revert a failed commit, never fix forward. Refactors preserve behavior; authorized fixes/QoLs may improve it (2026-10-23), with tests and reported differences.
- Disposable sessions only; never real config/session. Hardware: needs real-session check.
- Runtime branch sanity once before merge: 10 preview/Settings launches each,
  main vs head medians; QS/backend RSS at 10 s. Ask if Settings >+100 ms or RSS >+10%.
- No more D1 profiling, CIs, A/A, seeds, aggregate c or validation scheduling.
- Priorities: modularity, scalability, functionality, stability, memory footprint.
- Future family batches: 3-6 features per branch; one review stop per branch.
- Ask only for unapproved behavior/API/data-format changes, unclassifiable baseline failure,
  or sanity flags. Never start an unauthorized milestone or merge/push main.
- Replies <=40 lines; report ROADMAP acceptance % and current branch delivery %. One MIGRATION entry <=30 lines, laptop checklist <=6 lines.
  Commit only final gate summaries; no raw evidence directories.
- Preserve stdlib/unprivileged backend, English text, Preferences lock/merge/atomic
  writes, preview/standalone Settings and non-destructive installers.
