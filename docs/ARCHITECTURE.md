# LME Shell architecture — Phase 1 proposal

**Status at authoring:** design for approval; no Phase 2 implementation. **Date:** 2026-10-20.
**Source checked:** `58349e7`; corrections recorded in [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md).
Approved order: **A7 → A4 → A1 → A2 → A3 (ONE domain pilot) → A5**. A6 is deferred.
Examples below are proposed interfaces/data, not files or APIs already implemented.

## 1. Evidence, scope and ownership

- Verified: 134 QML files plus 30 other files in `qml/`, seven root QML entries,
  31 Python modules, 147 default preferences, 89 finite live action IDs,
  41 Settings-allowed IDs and 62 backend constructor fields.
- `desktop_backend.py` has 2,221 lines: `handle` starts at 1364; live `perform`
  occupies 1607–1983; the **separate demo dispatch tree** occupies 1402–1597.
  Demo matches 81 finite IDs plus seven known live IDs through prefixes;
  `gowall` also accepts other names; `appearance` delegates validation. `desktopEdit` has no demo match.
  Migration must preserve these differences, not assume live/demo parity.
- Main shell and standalone Settings have distinct backend instances. Persisted
  files and selected IPC are their boundaries; a Python singleton cannot coordinate them.
- UI/layout customization changes frequently; protocol providers change less often.
  Keep closely related implementation together and reduce duplicated requirements
  across languages/processes, following [Balanced Coupling](https://coupling.dev/posts/core-concepts/balance/).

| Layer | Owns | Must not own |
| --- | --- | --- |
| Feature implementation | Its UI, controller, validation details and tests | Other features' private state or global dispatch lists |
| Existing QML registries | Identity lookup, metadata projection, entry factories | Hardware commands or a second settings writer |
| Services / composition | Transport, existing worker scheduling, injected capabilities | Copied domain rules or providers' parsing logic |
| Shared infrastructure | Existing runner/errors, atomic JSON/locks, pure content helpers | Feature controllers, feature-specific daemons or preferences policy |
| Settings schema | Defaults, constraints and explicit export/profile membership | Settings UI generation or persistence transactions |

## 2. Contracts and one source for each fact

### 2.1 Catalog and QML registry contract

Keep `BarRegistry.info/clone`, `SettingsRegistry.pages/page/search` and `ControlRegistry`
as the public QML APIs. Replace their duplicated registration arrays incrementally;
do not keep a new registry running alongside them for the same ID.
Source: bundled `config/features.json` names explicit descriptors; Clipboard uses
`config/clipboard.json`. The examples below remain target interfaces; the current
pilot contract and ordering rules are in [M4B_DESIGN.md](archive/migration/M4B_DESIGN.md).
One generic reader per process loads/validates/caches descriptors once; widgets do not.
```json
{"version":1,"features":[{"id":"clipboard","descriptor":"config/feature-clipboard.json","enabled":true}]}
```
```json
{
  "id":"clipboard",
  "sources":["qml/panels/ClipboardPanel.qml","qml/panels/ClipboardFeature.qml","qml/settings/ClipboardPage.qml","scripts/clipboard.py"],
  "publicServices":["qml/services/ClipboardState.qml"],
  "bar":{"id":"clipboard","title":"Clipboard","icon":"clipboard","renderer":"action","panel":"clipboard"},
  "panel":{"id":"clipboard","entry":"qml/panels/ClipboardPanel.qml"},
  "bootstrap":{"entry":"qml/panels/ClipboardFeature.qml","contexts":["shell"]},
  "settingsPage":{"key":"clipboard","title":"Clipboard","icon":"clipboard","description":"Text and images, ready when you need them","keywords":"history capture copy paste image pin","entry":"qml/settings/ClipboardPage.qml"},
  "worker":{"entry":"scripts/clipboard.py","owner":"ClipboardState","commands":["search","copy","pin","delete","clear","pause"]},
  "requiredTools":["wl-paste","wl-copy"]
}
```

The sample omits schema fields for readability; §2.3 belongs in the same descriptor.
The real index will enumerate all existing registrations; this sample is not a default layout.
Index order preserves existing UI order; default zone placement is stored once in
the same catalog and projected to both `BarRegistry.defaults` and Python `BAR_MODULES`/defaults.
Panel/tab gesture choices and validation derive from these IDs; keep existing builtin
gesture actions/labels. Project required tool names to the runner whitelist, retaining
legacy tools until their descriptors migrate; do not require a shared TOOLS edit per new feature.
`config/control-grid.json` remains authoritative for card/tile sizes, placement and
visibility defaults; extend it with stable tab records and entry references, not duplicate them.
`config/liquid-glass.json`, `theme-tokens.json` and `palettes.json` remain authoritative
for their fields. Descriptors reference these catalogs; they do not copy their contents.

Registry outputs: `bar(id)`, `panel(id)`, `page(key)` return validated descriptors/factories;
`tabs()` returns ordered `{id,title,entry,enterHook}` records from the control catalog.
Entry paths resolve beneath the checkout, use declared file types and cannot escape it.
Duplicate IDs/setting keys or malformed required resources fail validation with diagnostics.
Disabled entries keep their IDs valid in saved layouts and keep schema loaded; renderers
skip their UI without rewriting layouts. Inactive implementation files need not be loaded.
Missing external tools keep current unavailable/error UI; they do not hide the feature.
Clipboard's capture switch must not become a switch hiding its history UI.

Factories preserve `screenInfo`, `windowInfo`, `compact`, `titleBudget`, page width and
existing editing bindings. Page entries may emit `navigateRequested(pageId)`; adapt
Utilities/Notifications' existing navigation signals locally, without a universal bus.
Keep shared bar renderers and specialized bindings; extract an entry adapter only when needed.
Named tab hooks call the existing refresh/mark-read functions at the same lifecycle points.
No JSON expression evaluation or new callback language is permitted.
The proposed feature-owned bootstrap adapter calls existing `ClipboardState.start()`
once in the main shell; demo/Settings keep their current guards. It replaces the
literal call in `shell.qml`, not the worker's lifecycle/retry policy. New feature-local
types use local imports/qmldir or URL entries; no shared qmldir registration is needed.
Existing global singleton/type exports remain compatibility facades until M8, if chosen.

Registry readiness joins the existing Settings startup barrier before constructing its
first page; failure uses the existing diagnostic path. Preserve `openPage()` visible-window
confirmation and `startupPending()`. Round-4 startup cost was measured and accepted
by the owner on 2026-10-21; see [archived D1 decision](archive/migration/MIGRATION_LOG.md#d1-owner-decision-and-startup-budget--2026-10-21).

### 2.2 Backend action registry contract, including demo

Retain JSON-lines requests `{action,...payload}` and results
`{action,ok,message,sequence,pending?}`. Preserve error truncation/redaction, acknowledgement
before completion, one completion at a time, and the existing snapshot shape/order.
The host obtains `demo`/`settings_only` from process configuration, never the request.
`ActionSpec.presentation` references its descriptor's presentation data; it does not
duplicate those rules in Python. Example: `"actionPresentation":{"launchpadRun":{"success":"status","error":"status"}}`.

```python
# Proposed interface in scripts/backend_actions.py; callbacks are Python, not JSON.
ActionSpec(name, contexts, live, demo, execution="sync", complete=None, presentation=None)
# Pilot provider scripts/launchpad_actions.py; injected narrow capabilities:
ActionSpec("launchpadRun", contexts={"shell", "settings"},
           live=run_saved_entry, demo=lambda request: None, execution="sync")
# run_saved_entry uses current preferences + the existing Launchpad controller.
```

Each domain exports action specs and its public state projection; the composition
root binds required services. It must not pass the entire `DesktopBackend` object.
Provider entry names are explicit bundled descriptor references, loaded only by the
composition root through stdlib imports; registration must not execute commands.
For example, Launchpad's descriptor adds
`"backend":{"entry":"scripts/launchpad_actions.py","factory":"provide"}`;
`provide(capabilities)` returns specs and a state callback using the existing controller.
Context checks occur before demo/live selection, as in `handle()` today.
Registered actions never fall back to legacy routing after an error.
Unmigrated IDs/prefixes keep their original live **and separate demo** handlers.
Reject duplicate ownership; do not silently shadow one dispatcher with another.

The pilot is **Launchpad only**: its single central action is `launchpadRun` (1850),
with demo no-op at 1446, existing controller at `launchpad.py`, and `launchpadJobs`
projection at the same `feature_snapshot` call site. Preserve detached jobs, logs, eight-job per-controller limit,
literal argv, explicit Bash/terminal choice and disabled-live/permissive-demo behavior.
No async domain migration is authorized by proving this synchronous pilot.

For a future async spec, `execution="worker"` delegates to existing `start_feature()`;
`complete(value)` installs domain state before the unchanged result emitter publishes it.
No new executor, queue, sampling hook, cache invalidation policy or timer is introduced.
Existing per-action invalidation remains in place; A6 is not smuggled into this registry.

Clipboard is a different contract: `ClipboardState` owns `clipboard.py` JSON-lines
and six worker commands; Settings must not start that worker. Keep its snapshot
`entries/available/capturing/paused/total/error/lastResult`, sequence and restart semantics.
`setting` and `imageAnnotate` still use the desktop backend. Image annotation belongs
to the capture service, not the Clipboard worker; no six new desktop actions are invented.

### 2.3 Settings schema contract

Descriptor `preferences` fragments are merged into one read-only schema, not a second
settings file. These exact existing flat keys remain in `settings.json`:

```json
{"preferences":{
  "clipboardEnabled":{"type":"boolean","default":true,"portable":true,"appearance":false},
  "clipboardImages":{"type":"boolean","default":true,"portable":true,"appearance":false},
  "clipboardLimit":{"type":"integer","default":100,"min":20,"max":500,"portable":true,"appearance":false,"validator":"clipboardLimit"}
}}
```

Schema interface: `defaults(context)`, `validate(key,value)`, `portable_keys()`,
`appearance_keys()`; retain `DEFAULT_PREFERENCES` and `validate_preference` as adapters.
Named validators/default resolvers bind to existing Python functions, never `eval`.
Reject bool-as-int, NaN, invalid token patches and unknown keys exactly as today.
Portable/profile membership is explicit and default-deny; preserve privacy exclusions.
Runtime paths retain existing resolvers. UI reads metadata for limits/options while
remaining handwritten; Clipboard's five suggested sizes must not narrow its 20–500 validator.
Registry-derived defaults such as `barLayout` use catalog resolvers rather than copied arrays.
The worker reads the same three defaults/validators, retaining its existing malformed-file
fallback behavior; main Preferences retains its different last-valid reload behavior.
**Do not change** lock → reload → merge/token patch → fsync → atomic replace, backup,
file permissions, flat key names, migrations or existing user data.

## 3. Vertical slice: Clipboard before and after

Current flow: Gear → `settings.sh --page clipboard` → Settings registry/switch →
`setting` → Preferences; Super+V/bar → `ShellState` → popup → `ClipboardState` →
`clipboard.py` → SQLite + wl-clipboard. Image click → `imageAnnotate` → capture/editor.
Demo uses `ClipboardState.demoEntries` and must not capture or copy the real clipboard.

| Concern | Today: exact existing files that adding/removing this slice requires reviewing/editing | Proposed steady-state owner |
| --- | --- | --- |
| Bar identity/defaults/rendering | `qml/bar/BarRegistry.qml`, `BarModule.qml`, `BarGestures.qml`, `scripts/desktop_backend.py` (`BAR_MODULES`, layout/gesture validation) | Descriptor + shared renderer/gesture projection |
| Popup/worker startup and routes | `shell.qml` (start, component, dispatch), `qml/services/ShellState.qml` (flags, close, allowed names) | Descriptor panel/worker ownership; existing host/ClipboardState service |
| Page identity/loading/CLI | `qml/settings/SettingsRegistry.qml`, `SettingsView.qml`, `qmldir`, `qml/services/ShellState.qml`, `scripts/settings.sh` | Descriptor + existing SettingsRegistry API and generic CLI catalog reader |
| Implementation | `qml/panels/ClipboardPanel.qml`, `qml/settings/ClipboardPage.qml`, `qml/services/ClipboardState.qml`, `scripts/clipboard.py`, `qml/services/qmldir` | Same files initially; exported service/type entries remain local mechanical declarations |
| Defaults/range/export | `scripts/desktop_backend.py`, `scripts/clipboard.py`, `scripts/settings_transfer.py`, `ClipboardPage.qml` | Descriptor schema; existing Preferences writer/worker read adapter |
| Shared content imports blocking deletion | `desktop_backend.py` imports `clipboard.MAX_TEXT`; `screen_capture.py` imports `clipboard.image_type` | A7 shared content helper, not a Clipboard dependency |
| Shortcut/docs/tests | `config/niri/lme-shell.kdl`; `README.md`, `docs/CLIPBOARD_ACTIVITY.md`, `CONFIGURATION.md`; `tests/test_clipboard.py`, `test_local_qml.py`, `test_settings.py`, `test_capture_night.py`, `test_image_annotation_ui.py` | Feature-owned docs/tests; unchanged public `shell toggle clipboard` and optional niri example |

This table describes integration edits, not a requirement to delete shared files when
removing a feature. Preserve `screen_capture.py`, annotation notifications and shared bar controls.
Existing imports/local exports can stay as compatibility facades; full physical deletion
of a legacy singleton is not promised by disabling its catalog entry.
After migration, adding a comparable bar/panel/page slice changes its descriptor,
implementation/docs/tests and **one index entry**; no generic host/validator/router edit.
Paths can remain where they are: logical ownership is enough for this acceptance test.
For Clipboard, the resulting edit set is `config/features.json` (one entry),
`config/feature-clipboard.json`, the four implementation files above plus the new
`qml/panels/ClipboardFeature.qml` adapter, and the docs/tests named in the table.
The generic `shell.qml`, ShellState, SettingsView, settings.sh and backend need no registration edits.
To withdraw Clipboard from a build, disable its one index entry: keep schema declarations
loaded, suppress its UI/worker registrations, and retain settings/history files.
Hard deletion of schema/data is a separate migration, not a removal side effect.
An opt-in supplied niri shortcut may remain an inert unknown route; document removal of
that example without editing the user's niri config. Re-enabling the entry restores access.

After-flow: descriptor → existing registry projections → same components/ClipboardState;
schema → existing Preferences/worker readers; annotation → same public desktop action.
No feature imports the capture implementation, and no extra backend process is added.

## 4. Checkable dependency rule (future check-architecture.sh)

Use descriptor `sources`, `publicServices`, provider/entry references and a small explicit
shared/host path classification in the same index. Ownership must be unique; exported
service APIs are interfaces, not permission to import another feature's implementation.
No mandatory directory move is needed to check existing paths.

```text
feature X implementation -> X implementation OR public shared/services APIs
feature X implementation -X-> feature Y implementation
generic shared/service code -X-> any private feature implementation/composition root
host/composition -> declared provider/entry exports only (factories/compatibility edges)
catalog references -> existing owned files beneath checkout; no traversal/duplicate IDs
```

Checker design: resolve local Python imports with `ast` (including imports inside CLI
functions); resolve literal QML/JS imports, qmldir exports, local type construction and
entry/script URL references. Require dynamic entry resolution to pass through the sealed
catalog loader; flag undeclared dynamic references for review rather than claiming proof.
Existing `ClipboardState` worker launch is an explicit declared service-to-provider edge.
Maintain an exact legacy-edge allowlist with reason/retirement step; forbid new violations
and cycles, shrink exceptions as migrations land. No blanket feature-directory exemption.
File limits are ratcheted from verified baselines; proposed new-file cap: 250 nonblank
source lines, exceptions reviewed. Do not fail the untouched 2,221-line backend on day one.
Static checks cannot prove runtime callback isolation; contract/Wayland tests remain required.

## 5. Validation gates for every migration commit

Run **before and after each step/commit**, against a disposable XDG config/state/runtime
and private Sway/Wayland + private D-Bus, never the user's running shell:

- **G0:** `./scripts/check.sh`; configure actual Qt/Quickshell import paths and run
  `qmllint` for touched QML and callers. A skipped required gate is not a pass.
- **G1:** stage a checkout alias in private `XDG_CONFIG_HOME/quickshell`, start
  `./scripts/start.sh --preview --config <alias>`, open/close affected panels, inspect
  logs, then close; launch standalone `scripts/settings.sh --demo --page <page>`.
  Also run native Settings startup with backend demo data to cover the non-demo host.
- **G2:** `LME_TEST_PERSONALIZATION_UI=1`: `test_settings_startup.NativeSettingsStartupCase`
  and `test_personalization.NativePersonalizationCase` (Gear reuse, close/reopen,
  first-frame appearance). Supply private virtual-pointer helpers; do not accept their skips.
- **G3:** `LME_TEST_UPGRADE_UI=1`: `test_control_grid.ControlGridUiCase` and
  `test_upgrade_ui.UpgradeInterfaceCase`; also `test_bar_gestures.BarGestureQmlCase`.
- **G4:** `LME_TEST_CLIPBOARD_NATIVE=1` and `LME_TEST_CLIPBOARD_UI=1`:
  `test_clipboard.NativeClipboardCase` / `ClipboardInterfaceCase`; plus
  `LME_TEST_ANNOTATION_UI=1 test_image_annotation_ui.AnnotationInterfaceCase`.
- **G5:** `LME_TEST_DISPLAY_WATCHDOG=1 test_upgrades.DetachedDisplayCase`
  (fake niri; initiator exits), `test_managed_commands.ManagedCommandsCase` and saver tests.
- **G6:** `test_launchpad.LaunchpadCase` and `LaunchpadQmlCase`; then
  `LME_TEST_POLLING_UI=1 test_polling_ui.NativePollingCase` as a regression gate only.

Test module names above run through `PYTHONPATH=tests:scripts python3 -m unittest ...`.
Use RHI/OpenGL for visual checks where available; software fallback alone is insufficient
for glass/Jelly pixels. GPU/backlight/Bluetooth/suspend remain **needs real-session check**.
Characterization names marked **new** below are specifications to add, not existing tests.
New `NativeTabCase`/`NativeEntryCase`/`NativeRoutingCase` use `LME_TEST_UPGRADE_UI=1` in that private session.
One behavior-preserving refactor per commit; if gates fail, revert that step rather than
stacking unrelated fixes. Keep characterization tests that already pass on the baseline.

Startup budget (owner decision, 2026-10-21): each later milestone re-measures Settings
and preview cold launches against the previous accepted head with the same warm-cache,
mapped-window and bootstrap-CI method. If the 95% CI lower bound of the added median
cost exceeds 10 ms on either path, **STOP and ask**. The round-4 rule is not redefined.

## 6. Ordered migration, adapters and rollback

Sizes estimate production source/metadata touched, excluding tests: S ≤150 lines,
M 150–350, L 350–700. Split larger work into smaller commits with all gates repeated.
No estimates below authorize a second A3 domain or A6 work.

### M1 — A7: shared runner and atomic persistence (low, M)

- Add **new** `test_infrastructure.SharedContractsCase`: exact JSON permissions,
  failed-write cleanup, independent locks, runner exception/redaction identity, and a
  watchdog import with `desktop_backend` deliberately unavailable. Pin existing behavior first.
- Extract runner/errors/current TOOLS to flat `scripts/command_runner.py`, persistence
  to `storage.py`; update consumers including the detached CLI. No package/tree reorganization.
- Gates: G0–G2 + G5. Adapter: re-export existing public names from old modules;
  remove private aliases only after repository/fixture imports reach zero, retain external CLI.
- Rollback: revert extraction/import commit; journals, settings and watchdog argv remain compatible.

### M2 — A7 slice prerequisite: shared content constants/parser (low, S; decision D2)

- Add **new** `test_infrastructure.ContentContractsCase`: exact text byte bound,
  PNG/JPEG/GIF/BMP/WebP recognition and unchanged rejection/error text; retain capture tests.
- Extract `MAX_TEXT`/`image_type` into flat `scripts/content_types.py`, redirect desktop/
  capture imports. Keep Clipboard compatibility exports until all callers/fixtures migrate.
- Gates: G0–G2 + G4, `test_capture_night`; no editor/GPU implementation changes.
- Remove aliases only after no consumer imports them. Rollback: revert imports/extraction;
  history/database/image formats are unchanged. This closes a deletion blocker, not a new feature.

### M3 — A4: stable Control Center/Agenda IDs (medium, M)

- Add **new** `test_navigation.TabContractCase`: current order, numeric↔ID mapping,
  invalid-input fallback, refresh/mark-read conditions and `quickNotes` visibility.
  **New** `test_navigation.NativeTabCase` runs on Wayland: reorder/insert test-only tabs,
  verify bar audio/devices/agenda/system routes, monitor button and selection indicator.
- Extend existing control catalog/ControlRegistry; replace positional routing in
  ControlCenter, Agenda, BarGestures and ControlDashboard. Preserve entry/visibility hooks.
- Gates: G0–G3 + G6 polling regression + new native case. No new refresh cadence.
- Adapter: old `controlTab` integer and named `LME_SHELL_CONTROL_TAB` retain mapping;
  remove internal numeric writes once fixtures migrate; keep the env contract.
- Rollback: revert ID/adapter commit; there is no persisted tab-state migration.

### M4 — A1: catalog projections, first Clipboard then remaining registrations (medium, L/batch)

- Add **new** `test_feature_catalog.CatalogContractCase`: current 19 bar/16 page contracts
  as parity fixtures, not a permanent count cap; test an injected new entry without host edits,
  labels/order/default layout, duplicate/path rejection, disabled entry, retained schema,
  CLI invalid-page behavior and missing required-resource diagnostics.
  **New** `test_feature_catalog.NativeEntryCase`: Clipboard bar→popup→page, then every
  converted entry's specialized bindings, bottom bar, selection, worker isolation and first-frame readiness.
- Introduce index/descriptors; project through existing registries. Migrate bar, pages,
  popup factories and control entry maps in separate bounded commits; keep control-grid
  geometry/default data. A catalog entry must replace its old list entry, not supplement it.
- Gates: G0–G4 + new native case. Adapters preserve existing APIs and local specialized
  entry bindings. Remove each legacy switch only when coverage proves every ID converted;
  leave no broad silent fallback after the last entry. Preserve required-resource diagnostics.
- Rollback: revert that projection batch; keep descriptors inert until its loader returns.
  No user layout, niri file, feature data or saved IDs are rewritten.

### M5 — A2: Clipboard schema pilot, then bounded key groups (medium, M/group)

- Add **new** `test_settings_schema.SchemaParityCase`: all defaults/types/ranges/export/
  profile sets, unknown keys, bool-as-int, token deletion and dynamic paths; assert the
  Clipboard worker and main read the same defaults but retain their distinct error policies.
- Move three Clipboard fields first; derive old default/validator/export interfaces.
  Extend by group only after parity; reuse glass/theme/palette catalogs and keep UI handwritten.
- Gates: G0–G4, `test_settings.SettingsCase`, `test_personalization.PersonalizationCase`,
  `test_ports.TransferCase`; pin stale-writer/token merges and import backups.
- Adapter: old constants/functions remain projections. Remove copied definitions after
  each group's readers migrate; keep stable import/CLI names as needed.
- Rollback: revert schema-consumer commit. No settings rewrite/version bump is required.

### M6 — A3: Launchpad ONLY, live plus separate demo (medium, M)

- Add **new** `test_action_registry.LaunchpadDispatchCase`: shell/settings × live/demo,
  disabled-live vs no-op-demo, invalid ID/mode, exact messages/sequence, zero demo spawn/disk
  writes, duplicate ownership and identical `launchpadJobs` projection. Pin legacy errors too.
- Register one action/provider; inject current preferences/controller capabilities.
  First delegate its two old branches; then route the registered ID and remove those branches.
  Keep demo snapshot initialization, Settings check and pending/result emitter ordering.
- Gates: G0–G2 + G6; `test_upgrades.UpgradesCase.test_background_completions_each_clear_their_pending_action`
  guards the unchanged executor path, not proof that an async provider has been migrated.
- Adapter: unregistered live/demo actions still use their original trees, including
  prefix semantics. Remove only the Launchpad cases when parity passes. **Review pilot
  results before any second domain.** No polling/cache/power changes.
- Rollback: revert pilot routing/provider commit; user jobs stay detached and data stays intact.

### M7 — A5: routing and result-presentation seam (medium, M/commit)

- Add **new** `test_shell_routing.RoutingContractCase`: close/open/unknown/auth gating,
  pending acknowledgement/completion, existing success/error suppression and Settings-only
  messages; **new** `NativeRoutingCase`: rapid popup reversal, Gear reuse, annotation handoff.
- Keep ShellState's public API; delegate catalog route lookup and pure message decisions.
  For registered actions, ActionSpec and QML consume the same descriptor presentation
  metadata; legacy actions keep existing suppression until individually migrated.
- Gates: G0–G4 + G6 + new native case. Preserve capture/record close deadlines, blur/Jelly
  geometry, OSD, peripheral alerts, retries, worker leases and power policy unchanged.
- Remove internal route-list adapters after zero callers/parity; retain public shell/settings
  IPC facades. Rollback: revert the seam commit, leaving the original singleton policy usable.

### M8 — Optional LAST: physical feature folders (high, L/batch)

Only after the above gates and a separate approval: relocate one feature's declared
files, update its descriptor/qmldir/test resources and README Project layout.
First add **new** `test_feature_paths.EntryPathCase` for CLI, symlink checkout, resource,
worker and shader paths. Run G0–G6 plus touched-feature native gates before/after.
Old entry shims stay until zero internal callers; public CLI keeps forwarding.
Rollback is a pure path/shim revert. Keeping the current directories indefinitely is valid.

## 7. Non-goals and open decisions

No universal event bus; no backend per widget; no generated Settings UI; no big-bang
file moves; no Preferences transaction changes; no new packages/privileges/features,
visual changes, sampling cadence, cache invalidation redesign or power-policy changes.
Python core remains stdlib; the existing separate Gio/GLib pairing helper is unchanged.
Directory restructuring is last and optional. A6 remains outside this proposal.

| Decision for owner | Recommendation | Alternative / trade-off |
| --- | --- | --- |
| D1: metadata source — resolved | JSON index + descriptors, cost accepted by the owner on 2026-10-21; existing registries are projections | The pre-registered round-4 rule was not met; the owner accepted the measured cost. Optional optimizations remain unauthorized. |
| D2: shared content extraction | Include M2 to make Clipboard independently removable | Leave helpers in Clipboard: smaller initial scope, but physical deletion still breaks capture/backend; do not claim slice independence |
| D3: compatibility lifetime | Keep public IPC/CLI/env/import facades; retire private adapters at each stated zero-caller gate | Timed public deprecation: less legacy surface, breaks external scripts without a release policy |
| D4: feature withdrawal | Disable index entry, retain schema/data | Delete descriptor/keys: fewer dormant definitions, requires a separately approved data/layout migration |
| D5: A3 pilot | Launchpad, one sync action with known demo difference | Clipboard worker or async palette: richer coverage but does not test the same central dispatcher, or has greater state/job risk |
| D6: schema organization | Per-feature fragments + references to existing catalogs | One aggregate schema: fewer files/reads but higher shared-edit contention; same single-writer contract required |
| D7: enforcement | Ratchet known legacy edges/sizes; 250-line proposed new-file cap | Enforce everything immediately: simpler rule but forces unrelated refactors; cap choice can change after pilot evidence |
| D8: folder consolidation | Defer unless logical ownership still causes costly edits | Approve M8 later: better locality, more path/resource/fixture risk without new behavior |
| D9: presentation transport | Read immutable descriptor metadata in both layers | Export resolved action metadata in snapshots: useful for runtime capabilities, but adds a protocol field this static policy does not need |

Historical Phase 1 verification covered source facts/design only; later evidence and
current authorizations are in STATE.md; historical records are in archive/migration/. M4b converts Clipboard only; M5 and later remain unauthorized.
