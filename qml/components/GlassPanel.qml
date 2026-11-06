import QtQuick
import "../theme"

Rectangle {
    id: root
    property string role: "panelFill"
    // Glass-on-glass marker: hosts that layer content above this panel
    // (background:/sibling placement) count it as the glass stratum below.
    readonly property bool isGlassFill: true
    property bool allowed: true
    property real shadow: 0
    radius: Theme.radius
    color: Theme.alpha(Theme.tokenColor(role), Theme.panelOpacity)
    // Compositor-blur hairline: while a blur preset is applied, a 1px outline
    // in the glass border token masks rounded-corner aliasing of the blur
    // region. The shader rim stays the highlight just inside it; with no
    // preset applied there is no outline, and Smoked mode is untouched.
    readonly property bool blurHairline: Theme.liquidGlass && !!Theme.glass.appliedBlur
    border.width: Theme.liquidGlass ? (blurHairline ? 1 : 0) : 1
    border.color: blurHairline ? Theme.border : Theme.outlineVariant
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
