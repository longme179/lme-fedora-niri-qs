pragma Singleton
import QtQuick
import "../services"

QtObject {
    readonly property var zones: ["left", "center", "right"]
    readonly property var defaults: ({left: ["launcher", "overview", "workspaces"], center: ["activity"], right: ["privacy", "clipboard", "tray", "notifications", "audio", "network", "battery", "clock", "settings"]})
    readonly property var knownModules: FeatureCatalog.project("bar", legacyModules, "id", true)
    readonly property var modules: FeatureCatalog.project("bar", legacyModules, "id")
    readonly property var legacyModules: [
        {id: "launchpad", title: "Launchpad", detail: "Your scripts and binaries", icon: "applications"},
        {id: "launcher", title: "Applications", detail: "Application launcher", icon: "applications"},
        {id: "overview", title: "Overview", detail: "niri overview and workspace board", icon: "overview"},
        {id: "workspaces", title: "Workspaces", detail: "Workspace switcher", icon: "overview"},
        {id: "windowTitle", title: "Window title", detail: "Focused application title", icon: "applications"},
        {id: "activity", title: "Activity island", detail: "Expandable media, focus timer and stopwatch", icon: "media"},
        {id: "media", title: "Media", detail: "Current player and track", icon: "media"},
        {id: "resources", title: "Resources", detail: "CPU and memory usage", icon: "resources"},
        {id: "tray", title: "System tray", detail: "Tray dropdown when apps are present", icon: "tray"},
        {id: "notifications", title: "Notifications", detail: "Notification history and unread indicator", icon: "bell"},
        {id: "audio", title: "Audio", detail: "Volume and control center", icon: "audio"},
        {id: "network", title: "Network", detail: "Connection status", icon: "wifi"},
        {id: "battery", title: "Battery", detail: "Charge level when a battery is present", icon: "battery"},
        {id: "clock", title: "Clock", detail: "Date, time and agenda", icon: "clock"},
        {id: "desktop", title: "Desktop widgets", detail: "Arrange desktop widgets", icon: "overview"},
        {id: "power", title: "Power", detail: "Lock, sleep, restart or shut down", icon: "power"},
        {id: "settings", title: "Settings", detail: "Open the separate settings app", icon: "settings"},
        {id: "privacy", title: "Privacy", detail: "Active microphone, camera and screen sharing", icon: "screen-share"},
        {id: "clipboard", title: "Clipboard", detail: "Search text and image history", icon: "clipboard"}
    ]
    function info(id) { return knownModules.find(item => item.id === id) || {id: id, title: id, icon: "applications"}; }
    function clone(layout) {
        const value = layout || defaults;
        return {left: value.left.slice(), center: value.center.slice(), right: value.right.slice()};
    }
}
