pragma Singleton
import QtQuick
QtObject {
    readonly property var pages: [
        {key: "elements", title: "Elements and fonts", icon: "settings", description: "Your colors, down to the element", keywords: "theme hex color class token typography font family buttons inputs surfaces palette"},
        {key: "appearance", title: "Appearance", icon: "settings", description: "Color palettes, glass and motion", keywords: "accent opacity animations motion theme font roboto profiles density popup blur overlay compositor palette material rose pine gruvbox nord catppuccin"},
        {key: "topbar", title: "Top bar", icon: "overview", description: "Your modules, in your order", keywords: "modules layout islands activity timer media pill clock workspaces tray size corners border fill round square left center right"},
        {key: "controlLayout", title: "Control center", icon: "overview", description: "Arrange your tiles and cards", keywords: "widgets modular drag drop layout size width hide"},
        {key: "display", title: "Displays", icon: "overview", description: "Resolution, refresh rate and arrangement", keywords: "monitor screen scale 60 120 hz resolution revert"},
        {key: "nightLight", title: "Night Light", icon: "weather-sun", description: "Softer light after sunset", keywords: "blue gamma warm temperature schedule sunrise sunset wlsunset"},
        {key: "wallpaper", title: "Wallpaper", icon: "applications", description: "A backdrop that feels like you", keywords: "background image picture folder library thumbnail matugen material scheme contrast palette light dark"},
        {key: "weather", title: "Weather", icon: "weather-sun", description: "Local conditions, wherever you are", keywords: "location city automatic ip forecast celsius fahrenheit temperature"},
        {key: "notifications", title: "Notifications", icon: "bell", description: "Messages with room to breathe", keywords: "popup toast appearance width position padding radius border opacity title body color font idle animation rotation cloud"},
        {key: "clipboard", title: "Clipboard", icon: "clipboard", description: "Text and images, ready when you need them", keywords: "history capture copy paste image pin"},
        {key: "idle", title: "Idle and sleep", icon: "battery", description: "Timeouts that follow your charger", keywords: "laptop ac battery display lock suspend sleep swayidle awake"},
        {key: "keybinds", title: "Keyboard shortcuts", icon: "applications", description: "Your niri keybindings at a glance", keywords: "keybind bindings cheatsheet hotkey keys keyboard config includes search"},
        {key: "behavior", title: "Behavior", icon: "resources", description: "Small choices for your everyday workflow", keywords: "terminal applications preferences recording audio system microphone"},
        {key: "about", title: "About", icon: "bell", description: "LME Shell for Fedora and niri", keywords: "version license requirements credits inir"}
    ]
    function page(key) { return pages.find(p => p.key === key) || pages[0]; }
    function search(query) {
        const words = query.toLowerCase().trim().split(/\s+/);
        return pages.filter(p => words.every(w => (p.title + " " + p.description + " " + p.keywords).toLowerCase().includes(w)));
    }
}
