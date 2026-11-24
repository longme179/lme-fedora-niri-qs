// Role: Agenda.qml (agenda layer, fan-in 2).
// Panel/feature UI; dispatches backend actions via ShellState.run(action,payload) where applicable.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"
import "../services"

ColumnLayout {
    id: root
    property int tab: 0
    property bool pageActive: true
    readonly property var tabs: ControlRegistry.visibleAgendaTabs(ShellState.preferences.quickNotes)
    readonly property var pages: ({CalendarWidget: calendar, TasksWidget: tasks, TimerWidget: timer, QuickNotes: notes})
    function selectTab(id) { tab = ControlRegistry.indexForId(id, true); }
    spacing: 14
    RowLayout {
        Layout.fillWidth: true; Layout.topMargin: 8
        Repeater {
            model: root.tabs
            delegate: LiquidButton {
                required property var modelData
                required property int index
                Layout.fillWidth: true
                text: modelData.title
                readonly property bool current: root.tab === modelData.legacyIndex
                selected: current
                selectionColor: Theme.accent
                palette.button: Theme.surface
                palette.buttonText: current ? Theme.background : Theme.text
                onClicked: root.selectTab(modelData.id)
            }
        }
    }
    Loader { id: pageLoader; Layout.fillWidth: true; Layout.fillHeight: true; sourceComponent: root.pages[ControlRegistry.tabForIndex(root.tab, true).entry] || FeatureCatalog.component(ControlRegistry.tabForIndex(root.tab, true).entry)
        onLoaded: if (item && "pageActive" in item) item.pageActive = root.pageActive }
    onPageActiveChanged: if (pageLoader.item && "pageActive" in pageLoader.item) pageLoader.item.pageActive = root.pageActive
    Component { id: calendar; CalendarWidget {} }
    Component { id: tasks; TasksWidget {} }
    Component { id: notes; QuickNotes {} }
    Component { id: timer; TimerWidget {} }
}
