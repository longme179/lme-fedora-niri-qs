// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "../theme"

Text {
    id: root
    property bool glassText: true
    // Preserve each label's own color binding when returning to Smoked.
    Binding {
        target: root
        property: "color"
        value: "#ffffff"
        when: Theme.liquidGlass && root.glassText
        restoreMode: Binding.RestoreBindingOrValue
    }
}
