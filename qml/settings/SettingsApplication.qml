import QtQuick
import Quickshell
import Quickshell.Io
import "../services"

ShellRoot {
    id: root
    readonly property string screenshotPath: Quickshell.env("LME_SETTINGS_SCREENSHOT") || ""
    IpcHandler {
        target: "settings"
        function openPage(page: string): void {
            window.visible = true; window.minimized = false;
            if (page) view.navigate(page);
        }
    }
    FloatingWindow {
        id: window
        title: ShellState.demo ? "LME Shell Settings - Demo" : "LME Shell Settings"
        implicitWidth: 1100; implicitHeight: 780
        minimumSize: Qt.size(800, 600)
        color: "transparent"
        // Keep native window-manager close consistent with Escape and the close button.
        onClosed: Qt.quit()
        SettingsView { id: view; anchors.fill: parent; page: SettingsRegistry.page(Quickshell.env("LME_SETTINGS_PAGE") || "appearance").key; onCloseRequested: Qt.quit() }
        Timer {
            interval: 1400; repeat: true; running: root.screenshotPath.length > 0
            onTriggered: {
                if (!ShellState.backendReady) return;
                stop();
                view.grabToImage(result => {
                    if (!result.saveToFile(root.screenshotPath)) console.error("Settings screenshot could not be saved");
                    else console.log("Settings screenshot saved");
                    Qt.quit();
                });
            }
        }
    }
}
