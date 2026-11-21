// Role: DesktopCard.qml (desktop layer, fan-in 3).
// Panel/feature UI; dispatches backend actions via ShellState.run(action,payload) where applicable.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    required property string widgetId
    required property var record
    property bool editing: DesktopState.editing
    readonly property bool manipulating: grip.pressed || resizeGrip.pressed
    signal moveBy(real dx, real dy)
    signal resizeBy(real dx, real dy)
    signal committed()
    radius: 24
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 14; spacing: 8
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: ({clock: "Clock", notes: "Notes", media: "Media", weather: "Weather", calendar: "Calendar", user: "Account"})[root.record.type] || "Clock"; font.weight: Font.Bold; Layout.fillWidth: true }
            LabelText { visible: root.editing; text: "Drag header"; color: Theme.muted; font.pixelSize: 11 }
            MouseArea {
                id: grip; objectName: "desktopDrag-" + root.widgetId
                Layout.preferredWidth: 36; Layout.preferredHeight: 30; visible: root.editing
                property point previous: Qt.point(0,0)
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                activeFocusOnTab: true; Accessible.name: "Move desktop widget"; Accessible.role: Accessible.Button
                LabelText { anchors.centerIn: parent; text: "⠿"; color: Theme.accent }
                onPressed: mouse => { forceActiveFocus(); previous = mapToGlobal(mouse.x,mouse.y); }
                onPositionChanged: mouse => { if (!pressed) return; const p=mapToGlobal(mouse.x,mouse.y); root.moveBy(p.x-previous.x,p.y-previous.y); previous=p; }
                onReleased: root.committed()
                Keys.onPressed: event => {
                    const step = event.modifiers & Qt.ShiftModifier ? 1 : 10;
                    if (event.key===Qt.Key_Left) root.moveBy(-step,0);
                    else if (event.key===Qt.Key_Right) root.moveBy(step,0);
                    else if (event.key===Qt.Key_Up) root.moveBy(0,-step);
                    else if (event.key===Qt.Key_Down) root.moveBy(0,step);
                    else return;
                    root.committed(); event.accepted=true;
                }
            }
        }
        ScrollView {
            id: scroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            contentWidth: availableWidth
            Loader { objectName: "desktopCardBody"; width: scroll.availableWidth; sourceComponent: ({clock: clockCard, notes: notesCard, media: mediaCard, weather: weatherCard, calendar: calendarCard, user: userCard})[root.record.type] || clockCard }
        }
    }
    MouseArea {
        id: resizeGrip
        visible: root.editing; objectName: "desktopResize-" + root.widgetId
        anchors.right: parent.right; anchors.bottom: parent.bottom; width: 28; height: 28
        property point previous: Qt.point(0,0)
        cursorShape: Qt.SizeFDiagCursor
        Accessible.name: "Resize desktop widget"
        onPressed: mouse => previous=mapToGlobal(mouse.x,mouse.y)
        onPositionChanged: mouse => { if (!pressed) return; const p=mapToGlobal(mouse.x,mouse.y); root.resizeBy(p.x-previous.x,p.y-previous.y); previous=p; }
        onReleased: root.committed()
        LabelText { anchors.centerIn: parent; text: "◢"; color: Theme.accent }
    }
    Component {
        id: clockCard
        ColumnLayout {
            spacing: 6
            LabelText { text: Qt.formatDateTime(clock.date,"HH:mm"); font.pixelSize: Math.min(54,root.width*.15); font.weight: Font.Bold; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
            LabelText { text: Qt.formatDateTime(clock.date,"dddd, MMMM d"); color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
            SystemClock { id: clock; precision: SystemClock.Minutes; enabled: root.visible }
        }
    }
    Component { id: notesCard; QuickNotes {} }
    Component {
        id: mediaCard
        ColumnLayout {
            spacing: 10
            LabelText { text: ActivityState.track; Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold }
            LabelText { text: ActivityState.artist; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
            MediaProgress { player: ActivityState.player; playing: ActivityState.playing; Layout.fillWidth: true }
            MediaActions { player: ActivityState.player; Layout.fillWidth: true }
            LyricsView { player: ActivityState.player; Layout.fillWidth: true }
        }
    }
    Component {
        id: weatherCard
        ColumnLayout {
            id: conditions
            objectName: "weatherCardBody"
            spacing: 8
            readonly property var weather: ShellState.weather
            function number(value, suffix) { return value === null || value === undefined ? "—" : Math.round(value) + (suffix || ""); }
            RowLayout {
                Layout.fillWidth: true; spacing: 12
                ShellIcon { name: conditions.weather.icon || "weather-cloud"; color: Theme.yellow; Layout.preferredWidth: 40; Layout.preferredHeight: 40 }
                LabelText { text: conditions.number(conditions.weather.temperature, conditions.weather.unit || "°C"); font.pixelSize: 34; font.weight: Font.Bold }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 3
                    LabelText { text: conditions.weather.condition || (conditions.weather.available === true ? "" : "Weather unavailable"); Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Medium }
                    LabelText { text: "Feels like " + conditions.number(conditions.weather.feelsLike, conditions.weather.unit || "°C"); color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                }
            }
            LabelText { text: "Humidity " + conditions.number(conditions.weather.humidity, "%") + "  ·  Wind " + conditions.number(conditions.weather.wind, " " + (conditions.weather.windUnit || "km/h")); color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            LabelText { text: (conditions.weather.location || {}).name || "Local weather"; color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
        }
    }
    Component {
        id: calendarCard
        ColumnLayout {
            id: cal
            spacing: 6
            property int offset: 0
            SystemClock { id: calClock; precision: SystemClock.Minutes; enabled: root.visible }
            readonly property date today: calClock.date
            readonly property date anchor: new Date(cal.today.getFullYear(), cal.today.getMonth() + cal.offset, 1)
            readonly property int days: new Date(cal.anchor.getFullYear(), cal.anchor.getMonth() + 1, 0).getDate()
            readonly property int lead: (cal.anchor.getDay() - Qt.locale().firstDayOfWeek + 7) % 7
            RowLayout {
                Layout.fillWidth: true
                IconButton { glyph: "‹"; text: "Previous month"; onClicked: cal.offset-- }
                LabelText { text: Qt.formatDateTime(cal.anchor, "MMMM yyyy"); font.weight: Font.Bold; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                IconButton { glyph: "›"; text: "Next month"; onClicked: cal.offset++ }
            }
            Grid {
                id: month; objectName: "calendarGrid"; columns: 7; Layout.fillWidth: true; spacing: 2
                Repeater {
                    model: 7
                    delegate: LabelText {
                        required property int index
                        text: Qt.formatDateTime(new Date(cal.anchor.getFullYear(), cal.anchor.getMonth(), 1 - cal.lead + index), "ddd")
                        color: Theme.muted; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter
                        width: month.width / 7 - 2
                    }
                }
                Repeater {
                    model: cal.lead + cal.days
                    delegate: Rectangle {
                        required property int index
                        readonly property int day: index - cal.lead + 1
                        readonly property bool now: cal.offset === 0 && index >= cal.lead && day === cal.today.getDate()
                        width: month.width / 7 - 2; height: width; radius: 10
                        color: now ? Theme.alpha(Theme.accent, .8) : "transparent"
                        visible: index >= cal.lead
                        LabelText { anchors.centerIn: parent; text: String(parent.day); color: parent.now ? "#ffffff" : Theme.muted; font.pixelSize: 11 }
                    }
                }
            }
        }
    }
    Component {
        id: userCard
        ColumnLayout {
            id: account
            spacing: 10
            readonly property string name: Quickshell.env("USER") || "user"
            RowLayout {
                spacing: 12
                Rectangle {
                    objectName: "userAvatar"; Layout.preferredWidth: 64; Layout.preferredHeight: 64; radius: 32
                    color: Theme.alpha(Theme.accent, .3)
                    LabelText { anchors.centerIn: parent; text: account.name.charAt(0).toUpperCase(); font.pixelSize: 26; font.weight: Font.Bold }
                }
                ColumnLayout {
                    spacing: 2
                    LabelText { text: account.name; font.weight: Font.Bold; font.pixelSize: 16 }
                    LabelText { text: "Signed in"; color: Theme.muted; font.pixelSize: 12 }
                }
            }
        }
    }
}
