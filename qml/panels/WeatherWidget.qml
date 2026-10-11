pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

Rectangle {
    id: root
    readonly property var weather: ShellState.weather
    readonly property var place: weather.location || {}
    implicitHeight: content.implicitHeight + 32
    radius: 24
    color: Theme.alpha(Theme.surfaceContainerHigh, 0.78)
    function number(value, suffix) { return value === null || value === undefined ? "—" : Math.round(value) + (suffix || ""); }
    ColumnLayout {
        id: content
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16
        spacing: 12
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            ColumnLayout {
                Layout.fillWidth: true; spacing: 3
                LabelText { text: root.place.name || "Local weather"; font.weight: Font.Bold; font.pixelSize: 16; Layout.fillWidth: true; elide: Text.ElideRight }
                LabelText { text: ShellState.demo ? "Demo forecast" : root.weather.automatic ? "Approximate location · by IP" : root.place.country || "Selected location"; color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
            }
            IconButton { iconName: "refresh"; tooltip: "Refresh weather"; Accessible.name: "Refresh weather"; enabled: ShellState.backendReady && !root.weather.loading; onClicked: ShellState.run("weatherRefresh") }
            IconButton { iconName: "settings"; tooltip: "Weather settings"; onClicked: ShellState.openSettingsPage("weather") }
        }
        RowLayout {
            visible: root.weather.available === true
            Layout.fillWidth: true; spacing: 14
            ShellIcon { name: root.weather.icon || "weather-cloud"; color: Theme.yellow; Layout.preferredWidth: root.width < 340 ? 28 : 42; Layout.preferredHeight: root.width < 340 ? 28 : 42 }
            LabelText { text: root.number(root.weather.temperature, root.weather.unit || "°C"); font.pixelSize: root.width < 340 ? 26 : 34; font.weight: Font.Bold }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                LabelText { text: root.weather.condition || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Medium }
                LabelText { text: "Feels like " + root.number(root.weather.feelsLike, root.weather.unit || "°C"); color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
        }
        LabelText {
            visible: root.weather.available === true
            text: "Humidity " + root.number(root.weather.humidity, "%") + "  ·  Wind " + root.number(root.weather.wind, " " + (root.weather.windUnit || "km/h"))
            color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap
        }
        RowLayout {
            visible: root.width >= 340 && root.weather.available === true && (root.weather.daily || []).length > 0
            Layout.fillWidth: true; spacing: 8
            Repeater {
                model: root.weather.daily || []
                delegate: Rectangle {
                    id: day
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: 67
                    color: Theme.alpha(Theme.panel, 0.6); radius: 16
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 9; spacing: 2
                        LabelText { text: day.index === 0 ? "Today" : Qt.locale("en_US").toString(new Date(day.modelData.date + "T12:00:00"), "ddd"); font.pixelSize: 11; font.weight: Font.Bold; Layout.alignment: Qt.AlignHCenter }
                        LabelText { text: root.number(day.modelData.max, "°") + " / " + root.number(day.modelData.min, "°"); font.pixelSize: 12; Layout.alignment: Qt.AlignHCenter }
                        LabelText { text: root.number(day.modelData.rainChance, "% rain"); color: Theme.cyan; font.pixelSize: 10; Layout.alignment: Qt.AlignHCenter }
                    }
                }
            }
        }
        LabelText {
            visible: !root.weather.available || !!root.weather.error || !!root.weather.loading
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: root.weather.error ? Theme.yellow : Theme.muted; font.pixelSize: 12
            text: root.weather.error ? (root.weather.available ? "Last forecast · " : "") + root.weather.error
                : root.weather.loading ? (root.place.name ? "Updating forecast…" : "Finding your approximate location…")
                : "Choose a location in Weather settings."
        }
        LabelText {
            text: "Weather by Open-Meteo"; color: Theme.muted; font.pixelSize: 10
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally("https://open-meteo.com/") }
        }
    }
}
