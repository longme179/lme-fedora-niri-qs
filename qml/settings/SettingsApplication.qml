pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "../components"
import "../services"
import "../theme"

ShellRoot {
    id: root
    property bool initialized: false
    property bool startupFailed: false
    property string requestedPage: SettingsRegistry.page(Quickshell.env("LME_SETTINGS_PAGE") || "appearance").key
    readonly property bool prepared: (Theme.ready && ShellState.backendReady) || startupFailed
    onPreparedChanged: if (prepared) initialized = true
    readonly property string screenshotPath: Quickshell.env("LME_SETTINGS_SCREENSHOT") || ""
    IpcHandler {
        target: "settings"
        function openPage(page: string): bool {
            if (page) root.requestedPage = SettingsRegistry.page(page).key;
            if (view.item) (view.item as SettingsView).navigate(root.requestedPage);
            window.minimized = false;
            if (view.status === Loader.Ready) window.visible = true;
            return window.visible && !window.minimized;
        }
        function startupPending(): bool { return !root.startupFailed && (!root.initialized || view.status === Loader.Loading); }
    }
    Timer {
        id: startupDeadline
        interval: 15000; running: !root.initialized && !root.startupFailed
        onTriggered: {
            ShellState.statusMessage = "Settings could not finish loading. Check the shell log, then reopen Settings to retry.";
            ShellState.statusError = true;
            root.startupFailed = true;
        }
    }
    FloatingWindow {
        id: window
        visible: view.status === Loader.Ready
        title: ShellState.shellName + " Settings" + (ShellState.demo ? " - Demo" : "")
        implicitWidth: 1100; implicitHeight: 780
        minimumSize: Qt.size(800, 600)
        color: "transparent"
        BackgroundEffect.blurRegion: window.visible && ShellState.liquidBlurEnabled ? glassBlur : null
        Region { id: glassBlur; regions: [bodyBlur, ...GlassState.popupsFor(window)] }
        SurfaceBlurRegion { id: bodyBlur; surface: view; radius: 28 }
        // Keep native window-manager close consistent with Escape and the close button.
        onClosed: Qt.quit()
        Loader {
            id: view
            anchors.fill: parent
            active: root.initialized
            sourceComponent: SettingsView { page: root.requestedPage; onCloseRequested: Qt.quit() }
        }
        Timer {
            interval: 1400; repeat: true; running: root.screenshotPath.length > 0
            onTriggered: {
                if (!ShellState.backendReady || view.status !== Loader.Ready) return;
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
