pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"

ColumnLayout {
    id: root
    property date month: new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    property date today: new Date()
    readonly property int firstDay: (month.getDay() + 6) % 7
    readonly property int dayCount: new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
    property var months: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    spacing: 16
    Timer { interval: 60000; running: true; repeat: true; onTriggered: root.today = new Date() }
    RowLayout {
        Layout.fillWidth: true
        IconButton { glyph: "‹"; tooltip: "Previous month"; onClicked: root.month = new Date(root.month.getFullYear(), root.month.getMonth() - 1, 1) }
        LabelText { text: root.months[root.month.getMonth()] + " " + root.month.getFullYear(); font.pixelSize: 21; font.weight: Font.Bold; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
        IconButton { glyph: "›"; tooltip: "Next month"; onClicked: root.month = new Date(root.month.getFullYear(), root.month.getMonth() + 1, 1) }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 7; columnSpacing: 6; rowSpacing: 8
        Repeater {
            model: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            delegate: LabelText { required property string modelData; text: modelData; color: Theme.muted; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; Layout.preferredWidth: 1 }
        }
        Repeater {
            model: 42
            delegate: Rectangle {
                required property int index
                readonly property int day: index - root.firstDay + 1
                readonly property bool valid: day >= 1 && day <= root.dayCount
                readonly property bool isToday: valid && day === root.today.getDate() && root.month.getMonth() === root.today.getMonth() && root.month.getFullYear() === root.today.getFullYear()
                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 48
                radius: 14; color: isToday ? Theme.accent : valid ? Theme.surface : "transparent"
                LabelText { anchors.centerIn: parent; text: parent.valid ? parent.day : ""; color: parent.isToday ? Theme.background : Theme.text }
            }
        }
    }
    LiquidButton { text: "Today"; Layout.alignment: Qt.AlignHCenter; onClicked: root.month = new Date(root.today.getFullYear(), root.today.getMonth(), 1) }
    LabelText { text: "" + Qt.locale("en_US").toString(root.today, "dddd, MMMM d, yyyy"); color: Theme.muted; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
    Item { Layout.fillHeight: true }
}
