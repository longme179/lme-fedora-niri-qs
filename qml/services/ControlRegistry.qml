pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    property var cards: []
    property var tiles: []
    readonly property var cardIds: cards.map(item => item.id)
    readonly property var titles: [...cards, ...tiles].reduce((map, item) => { map[item.id] = item.title; return map; }, {})
    readonly property var defaults: [...cards, ...tiles].map(item => ({id: item.id, enabled: true, size: item.size || (item.cols >= 4 ? "full" : "half")}))
    property FileView catalog: FileView {
        path: Quickshell.shellPath("config/control-grid.json")
        onLoaded: { const data = JSON.parse(text()); root.cards = data.cards; root.tiles = data.tiles; }
    }
}
