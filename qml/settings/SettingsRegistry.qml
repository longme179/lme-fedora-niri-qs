pragma Singleton
import QtQuick
import "../services"
QtObject {
    readonly property var pages: FeatureCatalog.project("settingsPage", legacyPages, "key")
    readonly property var legacyPages: [
        {key: "elements", title: "Elements and fonts", icon: "settings", description: "Your colors, down to the element", keywords: "theme hex color class token typography font family buttons inputs surfaces palette"},
        {key: "appearance", title: "Appearance", icon: "settings", description: "Color palettes, glass and motion", keywords: "island maximum size width height name identity branding smoked glass liquid surface refraction tint brightness feather smearing rim lens accent opacity animations motion theme font roboto profiles density popup blur overlay compositor palette material rose pine gruvbox nord catppuccin media wave timeline playback progress seek shuffle repeat stable metadata shapes"},
        {key: "topbar", title: "Top bar", icon: "overview", description: "Your modules, in your order", keywords: "click right middle scroll gestures mute volume dnd modules layout islands activity timer media pill clock workspaces tray size corners border fill round square left center right"},
        {key: "controlLayout", title: "Control center", icon: "overview", description: "Arrange your tiles and cards", keywords: "widgets modular drag drop layout size width hide"},
        {key: "display", title: "Displays", icon: "overview", description: "Resolution, refresh rate and arrangement", keywords: "monitor screen scale 60 120 hz resolution revert"},
        {key: "behavior", title: "Behavior", icon: "resources", description: "Small choices for your everyday workflow", keywords: "launcher ranking usage history clear frequency recent terminal applications preferences recording audio system microphone bluetooth pair pin passkey peripheral battery low alerts threshold headphones mouse keyboard lyrics lrc lrclib cache follow transcript current line island"},
    ]
    function page(key) { return pages.find(p => p.key === key) || pages[0]; }
    function search(query) {
        const words = query.toLowerCase().trim().split(/\s+/);
        return pages.filter(p => words.every(w => (p.title + " " + p.description + " " + p.keywords).toLowerCase().includes(w)));
    }
}
