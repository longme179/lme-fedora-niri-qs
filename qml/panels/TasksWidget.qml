pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    readonly property var tasks: ShellState.preferences.tasks || []
    spacing: 14
    function save(value) { ShellState.run("setting", {key: "tasks", value: value}); }
    function add() {
        const value = entry.text.trim();
        if (!value || tasks.length >= 100 || ShellState.pendingActions.setting) return;
        save([...tasks, {id: Date.now() + "-" + Math.floor(Math.random() * 1000000), text: value, done: false}]);
        entry.clear();
    }
    LabelText { text: "A little progress every day."; font.pixelSize: 19; font.weight: Font.Bold }
    RowLayout {
        Layout.fillWidth: true
        TextField {
            id: entry
            Layout.fillWidth: true; maximumLength: 240
            placeholderText: "Add a task…"; color: Theme.text
            palette.placeholderText: Theme.muted
            selectionColor: Theme.accent; selectedTextColor: Theme.background
            font.family: Theme.fontFamily; font.pixelSize: 13
            background: Rectangle { color: Theme.surface; radius: 12; border.width: 1; border.color: entry.activeFocus ? Theme.accent : Theme.border }
            onAccepted: root.add()
        }
        LiquidButton { text: "Add"; enabled: entry.text.trim().length > 0 && root.tasks.length < 100 && !ShellState.pendingActions.setting; onClicked: root.add() }
    }
    LabelText { text: root.tasks.filter(task => !task.done).length + " remaining"; color: Theme.muted; font.pixelSize: 12 }
    ListView {
        Layout.fillWidth: true; Layout.fillHeight: true
        model: root.tasks; clip: true; spacing: 8
        ScrollBar.vertical: ScrollBar {}
        delegate: Rectangle {
            id: task
            required property var modelData
            width: ListView.view.width; height: Math.max(58, taskText.implicitHeight + 24)
            radius: 14; color: Theme.surface
            RowLayout {
                anchors.fill: parent; anchors.margins: 10
                CheckBox {
                    id: completion
                    checked: task.modelData.done
                    enabled: !ShellState.pendingActions.setting
                    Accessible.name: "Complete " + task.modelData.text
                    indicator: Rectangle {
                        implicitWidth: 22; implicitHeight: 22; radius: 6
                        x: completion.leftPadding; y: (completion.height - height) / 2
                        color: completion.checked ? Theme.accent : Theme.panel
                        border.width: completion.visualFocus ? 2 : 1
                        border.color: completion.checked || completion.visualFocus ? Theme.accent : Theme.border
                        LabelText { anchors.centerIn: parent; text: "✓"; color: Theme.background; visible: completion.checked }
                    }
                    onToggled: root.save(root.tasks.map(item => item.id === task.modelData.id ? Object.assign({}, item, {done: checked}) : item))
                }
                LabelText { id: taskText; text: task.modelData.text; Layout.fillWidth: true; wrapMode: Text.Wrap; font.strikeout: task.modelData.done; color: task.modelData.done ? Theme.muted : Theme.text }
                IconButton { glyph: "×"; tooltip: "Delete task"; enabled: !ShellState.pendingActions.setting; onClicked: root.save(root.tasks.filter(item => item.id !== task.modelData.id)) }
            }
        }
    }
    LiquidButton { text: "Clear completed"; enabled: root.tasks.some(task => task.done) && !ShellState.pendingActions.setting; onClicked: root.save(root.tasks.filter(task => !task.done)) }
    LabelText { text: ShellState.demo ? "Tasks are kept only in this demo session." : "Tasks are saved with your shell preferences."; color: Theme.muted; font.pixelSize: 12 }
}
