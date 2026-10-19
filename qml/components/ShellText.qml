// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "../theme"

Text {
    id: root
    // Preserve each label's own color binding when returning to Smoked.
    Binding {
        target: root
        property: "color"
        value: "#ffffff"
        when: Theme.liquidGlass
        restoreMode: Binding.RestoreBindingOrValue
    }
}
