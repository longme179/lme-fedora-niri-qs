import QtQuick
import "../theme"

Rectangle {
    id: root
    property bool shown: false
    property real strength: .13
    property real amount: 0
    // shortcut: ext-background-effect-v1 exposes a region, not blur strength;
    // animate the dim layer until the compositor offers blur interpolation.
    color: Theme.alpha(Theme.background, amount)
    function update() {
        fade.stop();
        if (!Theme.animations) amount = shown ? strength : 0;
        else { fade.to = shown ? strength : 0; fade.start(); }
    }
    onShownChanged: update()
    onStrengthChanged: if (shown) update()
    Component.onCompleted: update()
    NumberAnimation { id: fade; target: root; property: "amount"; duration: Math.round((root.shown ? 220 : 150) / Theme.motionSpeed); easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.effectsCurve }
    Connections { target: Theme; function onAnimationsChanged() { root.update(); } }
}
