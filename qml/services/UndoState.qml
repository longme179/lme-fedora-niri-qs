// Role: UndoState.qml (shared layer) — the undo-first registry: the act happens now,
// the way back is offered once and expires; a newer act settles the previous one.
// Consumers: ClipboardState (delete/clear), LaunchpadEditor (entry delete) and the
// settings reset actions (ElementsPage, AppearancePage) — instead of confirm dialogs.
// Pattern credit: an independent rewrite of snowarch/iNiR services/Undo.qml inspected
// at commit edca6cc (GPL-3.0); no upstream code is redistributed. See THIRD_PARTY.md.
pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick

QtObject {
    id: root

    signal offered(string text)

    property string label: ""
    readonly property bool pending: _undo !== null
    // The way back runs in the shell process that offered it; the callbacks own
    // their own error surfaces (tool messages, preference writes).
    property var _undo: null
    property var _commit: null

    // `commit` (optional) finishes what was only held aside once the offer expires
    // or is replaced — the two-phase deletion the pattern is named after.
    function offer(text, undo, commit) {
        settle();
        _undo = undo || null;
        _commit = commit || null;
        label = text;
        offered(text);
    }

    function undo() {
        const back = _undo;
        if (!back) return false;
        _undo = null;
        _commit = null;
        label = "";
        back();
        return true;
    }

    // The expiry path: the toast card drives this when its window closes.
    function settle() {
        const finish = _commit;
        _undo = null;
        _commit = null;
        label = "";
        if (finish) finish();
    }
}
