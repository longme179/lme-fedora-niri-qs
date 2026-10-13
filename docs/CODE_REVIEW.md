# Control Center and process lifecycle review — 2026-10-13

This review followed the clipboard/notification logs and the editable Control
Center request. It inspected QML ownership, command dispatch, preference writes
and validation, settings transfer, clipboard subprocess lifetime and the relevant
capture/display helpers. It is not a claim that every platform path has been
exercised on the owner's machine.

## Independent controls and conservative cleanup follow-up

The feedback about unrelated movement was reproducible in the collision helper:
its first-fit fallback could move controls outside the drop's footprint. It was
not driven by the Settings card order. That fallback is removed. Empty cells
move one control; equal-size cells swap two; incompatible occupied drops cancel.
The native QML check now covers 5,628 scenarios and asserts unaffected positions.

Cleanup stays within Control Center and its direct dependencies:

- `ControlRegistry.qml` reads one shared button/card catalog for QML and Python.
  Repeated quick-ID/title/default lists are removed. Settings displays button
  visibility separately from the five ordered/sized cards.
- `ControlSlider.qml` replaces the old three-slider card, three duplicated
  flush functions and dashboard timers. It retains mute, audio settings,
  bounded updates, a release flush and bindings that wait for action results.
- The dashboard's card model has five stable loaders instead of the former
  fifteen-entry mixed model. Canvas updates do not recreate card instances;
  a native check compares their actual QObject identities. Hidden canvas controls
  are loaded only when visible.
- Old grid positions and hidden slider/capture groups migrate before writing.
  Scattered layouts grow downward instead of repacking existing tiles. New
  Power/Settings actions use the existing settings launcher and confirmation
  menu; an optional bar module uses the same panel route.

`ControlDashboard.qml` is reduced from 422 to 319 lines, with slider handling
shared by the three new tiles. An AST name-use scan of Python imports found no
unused-import candidates; it is a limited static check, not whole-program proof.
No broad service rewrite, package replacement or architecture change is included.

Fresh MIT DMS `CcSliderRow.qml`/`AudioSliderRow.qml` and GPLv3 iNiR
`AndroidPowerProfileToggle.qml` informed the design. LME keeps its own IPC,
theme and Fedora provider logic; precise revisions and credits are in
[THIRD_PARTY.md](../THIRD_PARTY.md). RAM/FPS/GPU improvements have not been measured.

## Confirmed findings

| Priority | Finding | Resolution |
| --- | --- | --- |
| High | Quickshell 0.3.2 destroys `Process` with SIGKILL. `clipboard.py` relied on `finally` to terminate `wl-paste`; abrupt death left both watchers alive and released the capture lock so another owner could start another pair. | Reused `idle_control.py client` to install Linux's parent-death signal before executing each watcher. A native test reproduced both surviving children before the fix, then confirmed their termination afterward. Existing orphans from older versions require a session restart to clear. |
| Medium | Layout editing existed only in Settings as a list. Its full/half card sizing could not express an exact cell position, and it mixed toggle controls with taller cards. | Added the bounded quick-control canvas to the popup; kept the detailed card editor and its previous visibility/sizing preferences. Grid geometry is saved atomically as one preference, validated before writing and included in portable transfers. |
| Medium | A moving button could share a clipping viewport with its drawing/interaction. | The edit ghost renders on the dashboard layer outside the scrolling viewport; the source/landing remain in-grid. Edit mode intercepts input and disables real actions. Ten-pixel gaps reserve hover/border drawing space. |

The reported duplicate `button` IDs in `BarModule.qml` belong to separate explicit
`Component` scopes. The supported Qt 6.8.2/Quickshell 0.3.2 runtime loads both; a
same-scope negative control does fail. No rename was required for that report.
Qt 6.12's reported lint output was not provided or reproduced.

## Reference feasibility

Fresh shallow checkouts outside this repo were inspected:

| Reference | Revision and license | Relevant files and decision |
| --- | --- | --- |
| DankMaterialShell | `d041ffccb0c95f2a4fd5a5d7e75512ce69cfa13d`, MIT | `quickshell/Common/GridLayout.js`, `Widgets/DEditableGridSlot.qml`, `Modules/ControlCenter/ControlCenterContent.qml`: same QML stack; adapted the overlap predicate, retained its MIT credit, and implemented bounded placement with LME controls/settings. |
| iNiR | `48cdcecb0f6089cfbb7019054602eab28e154b3b`, GPLv3 | `modules/sidebarRight/quickToggles/AndroidQuickPanel.qml`: one/two-cell controls and isolated editing are applicable; no QML source copied. |
| Noctalia | `b6d1c44d44ebaafcc218b9b2e69d8c626278fdbf`, MIT | `src/shell/control_center/control_center_panel.cpp`: current Control Center uses C++; inspected its tab/input structure, with no direct code port. |

No Hyprland IPC or new runtime dependency is introduced. Source/license details
are recorded in [THIRD_PARTY.md](../THIRD_PARTY.md).

## Manual checks on Fedora/niri

1. Open Controls → Edit layout. Drag DND onto Bluetooth; controls should reposition
   with no overlap and neither should toggle. Try an outside drop; it cancels.
2. Focus a tile and use arrow keys. Escape should leave Edit mode first. After
   Done, clicking a tile should execute its normal action.
3. Select eight columns/eight rows, place a tile near the last row and scroll.
   Edge dragging should scroll; reopening/restarting should retain the position.
4. Hide a control in Widgets, then enable it: its saved cell should remain. Export
   and import a preset; the canvas and card visibility should round-trip.
5. On a narrow output or with a larger font, inspect two-line toggle labels and
   all four edges during hover. Detailed cards remain below the quick canvas.

Live Bluetooth, gamma, GPU capture and 120 Hz motion performance still need the
owner's Fedora/niri session. Automated evidence is in [VALIDATION.md](VALIDATION.md).
