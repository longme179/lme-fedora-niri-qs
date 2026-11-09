// Glass-styled panel surface with Theme role mapping; base for cards/popups/settings surfaces.
// REL: qml/theme/Theme.qml, qml/components/GlassMaterial.qml – role/color/blur semantics.
import QtQuick
import "../theme"

Rectangle {
    id: root
    property string role: "panelFill"
    // Glass-on-glass marker: hosts that layer content above this panel
    // count it as the glass stratum below.
    readonly property bool isGlassFill: true
    property bool allowed: true
    property real shadow: 0
    radius: Theme.radius
    color: Theme.liquidGlass ? "transparent" : Theme.alpha(Theme.tokenColor(role), Theme.panelOpacity)
    border.width: Theme.liquidGlass ? 0 : 1
    border.color: Theme.outlineVariant
    GlassMaterial {
        anchors.fill: parent
        radius: root.radius
        shadow: root.shadow
        topLeftRadius: root.topLeftRadius; topRightRadius: root.topRightRadius
        bottomLeftRadius: root.bottomLeftRadius; bottomRightRadius: root.bottomRightRadius
    }
    Rectangle {
        visible: !Theme.liquidGlass
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - parent.radius * 2)
        height: 1
        color: Theme.alpha(Theme.text, 0.14)
    }
}
