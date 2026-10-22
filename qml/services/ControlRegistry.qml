pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    property var cards: []
    property var tiles: []
    readonly property var navigation: JSON.parse(catalog.text())
    readonly property var tabs: FeatureCatalog.project("controlTab", navigation.tabs || [], "id")
    readonly property var agendaTabs: FeatureCatalog.project("agendaTab", navigation.agendaTabs || [], "id")
    readonly property var cardIds: cards.map(item => item.id)
    readonly property var titles: [...cards, ...tiles].reduce((map, item) => { map[item.id] = item.title; return map; }, {})
    readonly property var defaults: [...cards, ...tiles].map(item => ({id: item.id, enabled: true, size: item.size || (item.cols >= 4 ? "full" : "half")}))
    function tabForIndex(index, agenda = false) {
        const entries = agenda ? agendaTabs : tabs;
        return entries.find(tab => tab.legacyIndex === index) || entries.find(tab => tab.fallback) || {};
    }
    function indexForId(id, agenda = false) {
        return (agenda ? agendaTabs : tabs).find(tab => tab.id === id)?.legacyIndex ?? 0;
    }
    function positionForIndex(index) { return tabs.findIndex(tab => tab.legacyIndex === index); }
    function visibleAgendaTabs(notesEnabled) { return agendaTabs.filter(tab => !tab.setting || notesEnabled !== false); }
    property FileView catalog: FileView {
        path: Quickshell.shellPath("config/control-grid.json")
        // Tab identity must be available before the first loader/entry hook runs.
        blockLoading: true
        onLoaded: { const data = JSON.parse(text()); root.cards = data.cards; root.tiles = data.tiles; }
    }
}
