pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"
import "../services"

ColumnLayout {
    id: root
    property int tab: 0
    spacing: 14
    RowLayout {
        Layout.fillWidth: true; Layout.topMargin: 8
        Repeater {
            model: ["Calendar", "To do", "Timer"].concat(ShellState.preferences.quickNotes !== false ? ["Notes"] : [])
            delegate: LiquidButton {
                required property string modelData
                required property int index
                Layout.fillWidth: true
                text: modelData
                selected: root.tab === index
                selectionColor: Theme.accent
                palette.button: Theme.surface
                palette.buttonText: root.tab === index ? Theme.background : Theme.text
                onClicked: root.tab = index
            }
        }
    }
    Loader { Layout.fillWidth: true; Layout.fillHeight: true; sourceComponent: root.tab === 0 ? calendar : root.tab === 1 ? tasks : root.tab === 3 ? notes : timer }
    Component { id: calendar; CalendarWidget {} }
    Component { id: tasks; TasksWidget {} }
    Component { id: notes; QuickNotes {} }
    Component { id: timer; TimerWidget {} }
}
