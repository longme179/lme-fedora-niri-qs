// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Illia Miroshnichenko
// Adapted for LME simple glass; source and changes: third_party/Serpantinum-NOTICE.
import QtQuick
import "../theme"

ShaderEffect {
    id: root

    property real topLeftRadius: 0
    property real topRightRadius: 0
    property real bottomLeftRadius: 0
    property real bottomRightRadius: 0
    property color tintColor: Theme.panel
    property real tintAmount: 0.175
    property real bezel: Math.max(5, Math.min(26, Math.min(width, height) * 0.36))
    property real rim: 0.45
    property real glassPad: 0
    property real shadowAmt: 0
    property real nest: 0
    property vector2d filletDir: Qt.vector2d(0, 0)
    property real filletRadius: 0
    property real filletInset: 0
    property bool earsOnly: false
    property rect boxRect: Qt.rect(0, 0, 0, 0)
    property real panelOpacity: 0.65
    property real grain: 0.004

    property vector2d itemSize: Qt.vector2d(width, height)
    property vector4d radii: Qt.vector4d(topLeftRadius, topRightRadius, bottomRightRadius, bottomLeftRadius)
    property vector4d fillet: Qt.vector4d(filletDir.x, filletDir.y, filletRadius, earsOnly ? 1 : 0)
    property vector4d box: boxRect.width > 0 ? Qt.vector4d(boxRect.x + boxRect.width * 0.5 - width * 0.5, boxRect.y + boxRect.height * 0.5 - height * 0.5, boxRect.width * 0.5, boxRect.height * 0.5) : Qt.vector4d(0, 0, 0, 0)

    fragmentShader: Qt.resolvedUrl("shaders/liquid-glass.frag.qsb")
}
