pragma Singleton
import QtQuick
QtObject {
    readonly property var pages: [
        {key: "appearance", title: "Appearance", icon: "settings", description: "Material shapes, glass and Dracula colors", keywords: "accent opacity animations motion theme font roboto profiles density"},
        {key: "topbar", title: "Top bar", icon: "overview", description: "Your modules, in your order", keywords: "modules layout islands activity timer media pill clock workspaces tray size"},
        {key: "controlLayout", title: "Control center", icon: "overview", description: "Arrange your tiles and cards", keywords: "widgets modular drag drop layout size width hide"},
        {key: "display", title: "Displays", icon: "overview", description: "Resolution, refresh rate and arrangement", keywords: "monitor screen scale 60 120 hz resolution revert"},
        {key: "wallpaper", title: "Wallpaper", icon: "applications", description: "A backdrop that feels like you", keywords: "background image picture folder library favorites thumbnail"},
        {key: "weather", title: "Weather", icon: "weather-sun", description: "Local conditions, wherever you are", keywords: "location city automatic ip forecast celsius fahrenheit temperature"},
        {key: "clipboard", title: "Clipboard", icon: "clipboard", description: "Text and images, ready when you need them", keywords: "history capture copy paste image pin"},
        {key: "behavior", title: "Behavior", icon: "resources", description: "Small choices for your everyday workflow", keywords: "terminal applications preferences"},
        {key: "about", title: "About", icon: "bell", description: "LME Shell for Fedora and niri", keywords: "version license requirements credits inir"}
    ]
    function page(key) { return pages.find(p => p.key === key) || pages[0]; }
    function search(query) {
        const words = query.toLowerCase().trim().split(/\s+/);
        return pages.filter(p => words.every(w => (p.title + " " + p.description + " " + p.keywords).toLowerCase().includes(w)));
    }
}
