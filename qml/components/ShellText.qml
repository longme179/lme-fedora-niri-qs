// SPDX-License-Identifier: GPL-3.0-or-later
// Base shell text item applying Theme font/metrics; wrapped by LabelText for common label roles.
// REL: qml/components/LabelText.qml – shared text contract; qml/theme/Theme.qml – font/color tokens.
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
