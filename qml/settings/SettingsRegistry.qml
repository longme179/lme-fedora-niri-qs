pragma Singleton
import QtQuick
QtObject {
    readonly property var pages: [
        {key: "appearance", title: "Appearance", icon: "settings", description: "Material shapes, glass and Dracula colors", keywords: "accent opacity animations motion theme font roboto"},
        {key: "topbar", title: "Top bar", icon: "overview", description: "Your modules, in your order", keywords: "modules layout islands pill clock workspaces tray size"},
        {key: "wallpaper", title: "Wallpaper", icon: "applications", description: "A backdrop that feels like you", keywords: "background image picture"},
        {key: "behavior", title: "Behavior", icon: "resources", description: "Small choices for your everyday workflow", keywords: "terminal applications preferences"},
        {key: "about", title: "About", icon: "bell", description: "LME Shell for Fedora and niri", keywords: "version license requirements credits inir"}
    ]
    function page(key) { return pages.find(p => p.key === key) || pages[0]; }
    function search(query) {
        const words = query.toLowerCase().trim().split(/\s+/);
        return pages.filter(p => words.every(w => (p.title + " " + p.description + " " + p.keywords).toLowerCase().includes(w)));
    }
}
