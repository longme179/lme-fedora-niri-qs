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
    readonly property color fill: Theme.batterySaver ? Theme.solid(style.fillColor || Theme.barFill) : Theme.liquidGlass ? Theme.barFill : style.fillColor || Theme.barFill
    readonly property var style: zone ? Theme.islandStyle(zone) : ({})
    objectName: "barSurface"
    role: "barFill"
    shadow: Theme.glassPillShadow
    compositorBlur: Theme.compositorBarBlur
    radius: Math.max(0, height / 2)
    topLeftRadius: Theme.barCornerRadius("topLeft", height, zone)
    topRightRadius: Theme.barCornerRadius("topRight", height, zone)
    bottomLeftRadius: Theme.barCornerRadius("bottomLeft", height, zone)
    bottomRightRadius: Theme.barCornerRadius("bottomRight", height, zone)
    color: Theme.alpha(fill, Theme.panelOpacity)
    // Hairline while a blur preset is applied (see GlassPanel); otherwise the
    // shader rim is the glass edge. Non-glass zones keep the styled border.
    border.width: Theme.liquidGlass ? (blurHairline ? 1 : 0) : zone ? (style.borderWidth === undefined ? 1 : style.borderWidth) : Theme.barBorderWidth
    border.color: blurHairline ? Theme.border : Theme.liquidGlass ? Theme.barBorder : style.borderColor || Theme.barBorder
}
