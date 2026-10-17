// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import "../theme"

Item {
    id: root
    property Item surface: null
    property bool mounted: false
    property bool horizontal: false
    property real velocity: 0
    property bool bounded: false
    readonly property bool engaged: Theme.motionPreset === "jelly-v2" && Theme.springMotion && Theme.animations && mounted && !!surface
    readonly property bool software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property real strain: engaged ? Math.max(-.42, Math.min(.42, shape.value)) : 0
    readonly property bool rendering: engaged && (shape.running || Math.abs(strain) > .00002)
    readonly property real stretch: 1 + .7 * Math.abs(strain)
    readonly property real fitScale: bounded ? 1 / (1 + .94 * Math.abs(strain)) : 1
    visible: false
    function attach() { if (surface && !surface.transform.includes(squeeze)) surface.transform.push(squeeze); }
    onSurfaceChanged: attach()
    Component.onCompleted: attach()
    SpringMotion {
        id: shape
        enabled: root.engaged
        readonly property real speed: root.surface ? root.velocity / Math.max(120, root.horizontal ? root.surface.width : root.surface.height) / Theme.motionSpeed : 0
        target: root.engaged ? speed / (3 + Math.abs(speed)) * (.28 + .18 * Theme.motionBounce) : 0
        stiffness: 760 * Theme.motionSpeed * Theme.motionSpeed
        damping: 2 * Math.sqrt(stiffness) * (.62 - .12 * Theme.motionBounce)
        positionEpsilon: .00002; velocityEpsilon: .0002
        onTargetChanged: retarget(target)
    }
    Scale {
        id: squeeze
        origin.x: root.surface ? root.surface.width / 2 : 0
        origin.y: root.surface ? root.surface.height / 2 : 0
        xScale: root.software ? (root.horizontal ? root.stretch : 1 / root.stretch) * root.fitScale : 1
        yScale: root.software ? (root.horizontal ? 1 / root.stretch : root.stretch) * root.fitScale : 1
    }
    Component {
        id: effect
        ShaderEffect {
            property var source
            property real strain: root.strain
            property real horizontal: root.horizontal ? 1 : 0
            property real fit: root.bounded ? 1 : 0
            property vector2d sizePx: Qt.vector2d(width, height)
            mesh: Qt.size(16, 16)
            vertexShader: Qt.resolvedUrl("shaders/popup-jelly.vert.qsb")
            fragmentShader: Qt.resolvedUrl("shaders/popup-jelly.frag.qsb")
        }
    }
    Binding { target: root.surface ? root.surface.layer : null; property: "effect"; value: effect; when: root.engaged && !root.software; restoreMode: Binding.RestoreBindingOrValue }
    Binding { target: root.surface ? root.surface.layer : null; property: "smooth"; value: true; when: root.engaged && !root.software; restoreMode: Binding.RestoreBindingOrValue }
    Binding { target: root.surface ? root.surface.layer : null; property: "enabled"; value: root.rendering; when: root.engaged && !root.software; restoreMode: Binding.RestoreBindingOrValue }
}
