import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "../components"
import "../services"

ShellRoot {
    id: root
    readonly property string screenshotPath: Quickshell.env("LME_SETTINGS_SCREENSHOT") || ""
    IpcHandler {
        target: "settings"
        function openPage(page: string): bool {
            window.visible = true; window.minimized = false;
            if (page) view.navigate(page);
            return window.visible && !window.minimized;
        }
    }
    FloatingWindow {
        id: window
        title: ShellState.shellName + " Settings" + (ShellState.demo ? " - Demo" : "")
        implicitWidth: 1100; implicitHeight: 780
        minimumSize: Qt.size(800, 600)
        color: "transparent"
        BackgroundEffect.blurRegion: window.visible && ShellState.liquidBlurEnabled ? glassBlur : null
        Region { id: glassBlur; regions: [bodyBlur, ...GlassState.popupsFor(window)] }
        SurfaceBlurRegion { id: bodyBlur; surface: view; radius: 28 }
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
