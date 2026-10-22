# Working in LME Shell

Read `docs/STATE.md` first. Read `docs/ARCHITECTURE.md` for design questions.
Do not read `docs/archive/` unless a specific historical question requires it.
Use `.agents/skills/ponytail/SKILL.md` at full level, as requested by the owner.
Keep source, UI text and documentation in English. Prefer existing controls,
service APIs and stdlib helpers. Preserve attribution for third-party code.

## Layout and dependency rule

- `shell.qml`: live entry; `settings.qml`: standalone Settings entry.
- `qml/bar`, `qml/panels`, `qml/settings`: current feature UI and legacy hosts.
- `qml/components`, `qml/theme`, `qml/services`: shared controls/theme/service APIs.
- `scripts/desktop_backend.py`: unprivileged JSON-lines backend; domain helpers
  and shared runner/storage/content/catalog modules remain flat in `scripts/`.
- `config/features.json`: versioned index; descriptors own feature registrations.
- `scripts/backend_actions.py`: sync registry; providers use narrow callbacks and explicit host bindings.
- `tests/`: unit contracts and opt-in private Wayland checks.
- `docs/STATE.md`: current status; `docs/MIGRATION_LOG.md`: concise new milestones.

A feature implementation imports only its own files and shared/service APIs,
never another feature implementation. Composition hosts may load feature entries.
`scripts/check-architecture.sh` resolves local Python AST imports, literal QML/JS
imports and entry URLs. `config/architecture.json` records legacy ownership,
exact exceptions with reasons, existing cyclic edges and source-size ceilings.
Computed imports/URLs need manual review; the guard resolves static literals.
Remove exceptions when their edge disappears; never widen them to pass a check.
New source files have a 250-nonblank-line cap. Existing large files may not grow;
ratchet their recorded ceiling down when shrinking them. No tree reorganization.

## Add a feature

1. Reuse shared APIs; put implementation in its own files (future feature folders
   use `qml/features/<id>/` or `scripts/features/<id>/`).
2. Add a descriptor with its sources, entry URLs and static metadata.
3. Add one canonical index entry; use an explicit `after` anchor for order.
   Remove corresponding legacy registrations in the SAME commit; no duplicates.
4. Add characterization/contracts, withdrawal and relevant native coverage.
5. Update user docs and STATE; keep public IPC/CLI/env/import facades compatible.
   Schema definitions live in descriptor preferences plus the legacy fragment.
   Declare portable/profile membership explicitly; defaults deny both. Bind named
   validators/resolvers to Python functions; JSON contains no code.
   Guard cross-surface page links with ShellState.settingsPageAvailable; preserve saved IDs on withdrawal.
   Pages emit navigateRequested(pageId); PageNavigation connects locally to the Settings host, not a global bus.

## Commands and checks

- `./scripts/check.sh`: architecture/catalog checks, unit discovery, Bash syntax,
  demo JSON validation. `PYTHONPATH=scripts:tests python3 -m unittest discover
  -s tests -p 'test_NAME.py' -v` runs focused tests.
- `./scripts/run-gates.sh --gates G0` runs G0 including qmllint, isolated in
  disposable XDG directories, private Sway/Wayland and D-Bus.
  Optional `--env-file FILE --pointer-dir DIR` supplies installed test tools.
- G1 startup, G2 Settings, G3 controls/navigation/catalog, G4 clipboard/capture,
  G6 polling: see `tests/migration_checks.py` for flags and case names.
- `./scripts/start.sh --preview`; `./scripts/settings.sh --page appearance`.

## Owner process reset (2026-10-21)

- Priorities: modularity, scalability, functionality, stability, memory footprint.
- D1/startup optimization is CLOSED. No profiling, bootstrap CIs, A/A arms,
  seeds, raw CSV, aggregate c or backend-validation scheduling. A6 is out of scope:
  no polling, cache or power-policy changes.
- Characterize before refactoring; separate tests, extraction and docs commits.
  Never edit an existing assertion without asking. If a gate fails, revert the
  responsible commit rather than fixing forward. Never call skips/failures passed.
- Never touch real niri/Quickshell config or the running session. Use disposable
  XDG/Sway/D-Bus. Hardware-only checks must say "needs real-session check".
- During work: Python changes use G0 + relevant units; QML changes use G0 + G1
  + relevant native cases. Run G0-G4 and G6 polling ONCE before requesting merge.
  An explicit milestone gate scope takes precedence.
- Before merge, once per branch: 10 cold launches each of preview and Settings,
  main vs head, medians only; Quickshell/backend RSS at 10 seconds. Ask only if
  Settings exceeds +100 ms or either process RSS exceeds +10%.
- Batch future conversions by families, 3-6 per branch; one review stop per branch.
  No unauthorized milestone, merge or push to main. Owner merges review branches.
- Ask only for behavior or public API/data-format changes, unclassifiable baseline
  failures, or the launch/RSS flags. Otherwise continue within authorized scope.
- Replies <=40 lines; one migration entry <=30 lines per milestone, checklist <=6
  lines. Commit a final gate summary only, no raw logs/evidence directories.
- Keep Preferences file-lock/merge/fsync/atomic-write semantics; stdlib backend;
  installers must never overwrite `~/.config/niri/config.kdl`.
