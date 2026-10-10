import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    implicitWidth: dockRow.implicitWidth + 26
    implicitHeight: 68
    radius: 23
    property var entries: {
        const result = [];
        for (const candidates of [["firefox.desktop", "org.mozilla.firefox.desktop"], ["kitty.desktop", "org.gnome.Console.desktop", "org.gnome.Terminal.desktop"], ["org.gnome.Nautilus.desktop", "thunar.desktop", "org.kde.dolphin.desktop"]]) {
            const app = ShellState.apps.find(a => candidates.includes(a.id));
            if (app) result.push({app: app, windows: []});
        }
        for (const win of ShellState.niri.windows || []) {
            const appId = (win.app_id || "").toLowerCase().replace(/\.desktop$/, "");
            const app = ShellState.apps.find(a => a.id.toLowerCase().replace(/\.desktop$/, "") === appId
                                      || (a.icon || "").toLowerCase() === appId);
            let entry = result.find(e => app ? e.app.id === app.id : e.app.id === appId);
            if (!entry) {
                entry = {app: app || {id: appId, name: win.app_id || win.title, icon: win.app_id || ""}, windows: []};
                result.push(entry);
            }
            entry.windows.push(win);
        }
        return result.slice(0, 16);
    }
    RowLayout {
        id: dockRow
        anchors.centerIn: parent
        spacing: 5
        IconButton {
            glyph: "◈"; implicitWidth: 48; implicitHeight: 48
            tooltip: "Applications"
            active: ShellState.launcherOpen
            onClicked: ShellState.togglePanel("launcher")
        }
        Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 27; color: Theme.border }
        Repeater {
            model: root.entries
            delegate: AbstractButton {
                id: appButton
                required property var modelData
                readonly property bool focused: modelData.windows.some(w => w.is_focused)
                Layout.preferredWidth: 52; Layout.preferredHeight: 52
                hoverEnabled: true
                Accessible.name: modelData.app.name
                background: Rectangle {
                    radius: 16
                    color: appButton.hovered ? Theme.alpha(Theme.accent, 0.20) : appButton.focused ? Theme.alpha(Theme.text, 0.08) : "transparent"
                    border.width: appButton.visualFocus ? 2 : 0; border.color: Theme.accent
                    Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
                }
                contentItem: Item {
                    Image {
                        id: appImage
                        source: ShellState.appIcon(appButton.modelData.app.icon)
                        anchors.centerIn: parent; anchors.verticalCenterOffset: -2
                        width: 32; height: 32; sourceSize.width: 48; sourceSize.height: 48
                        fillMode: Image.PreserveAspectFit
                    }
                    LabelText {
                        visible: appImage.status !== Image.Ready
                        text: (appButton.modelData.app.name || "?").slice(0, 1).toUpperCase()
                        font.pixelSize: 22; font.weight: Font.DemiBold; color: Theme.purple
                        anchors.centerIn: parent; anchors.verticalCenterOffset: -2
                    }
                    Rectangle {
                        visible: appButton.modelData.windows.length > 0
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 2; anchors.horizontalCenter: parent.horizontalCenter
                        width: appButton.focused ? 15 : 5; height: 3; radius: 1.5
                        color: appButton.focused ? Theme.accent : Theme.muted
                    }
                }
                onClicked: {
                    if (modelData.windows.length) {
                        const current = modelData.windows.findIndex(w => w.is_focused);
                        const next = modelData.windows[(current + 1) % modelData.windows.length];
                        ShellState.run("focusWindow", {id: next.id});
                    } else ShellState.run("launch", {id: modelData.app.id});
                }
                TapHandler { acceptedButtons: Qt.MiddleButton; onTapped: ShellState.run("launch", {id: appButton.modelData.app.id}) }
                ToolTip.visible: hovered
                ToolTip.text: modelData.app.name + (modelData.windows.length ? " · " + modelData.windows.length + " window(s)" : "")
                ToolTip.delay: 450
            }
        }
        Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 27; color: Theme.border }
        IconButton { glyph: "⚙"; implicitWidth: 44; implicitHeight: 48; tooltip: "Shell settings"; onClicked: ShellState.togglePanel("settings") }
    }
}
