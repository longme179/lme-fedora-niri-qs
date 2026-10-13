import QtQuick
import Quickshell
import "../components"
import "../theme"

GlassPanel {
    id: root
    readonly property Region blurRegion: Region {
        item: root.visible && root.width > 0 ? root : null
        topLeftRadius: Math.round(root.topLeftRadius)
        topRightRadius: Math.round(root.topRightRadius)
        bottomLeftRadius: Math.round(root.bottomLeftRadius)
        bottomRightRadius: Math.round(root.bottomRightRadius)
    }
    property string zone: ""
    readonly property color fill: style.fillColor || Theme.barFill
    readonly property var style: zone ? Theme.islandStyle(zone) : ({})
    objectName: "barSurface"
    role: "barFill"
    radius: height / 2
    topLeftRadius: Theme.barCornerRadius("topLeft", height, zone)
    topRightRadius: Theme.barCornerRadius("topRight", height, zone)
    bottomLeftRadius: Theme.barCornerRadius("bottomLeft", height, zone)
    bottomRightRadius: Theme.barCornerRadius("bottomRight", height, zone)
    color: Theme.alpha(fill, Theme.panelOpacity)
    border.width: zone ? (style.borderWidth === undefined ? 1 : style.borderWidth) : Theme.barBorderWidth
    border.color: style.borderColor || Theme.barBorder
}
