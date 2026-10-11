import QtQuick
import "../theme"
Text {
    id: root
    property bool heading: false
    // QFont notifies as a group; reading its weight in the family binding loops.
    onFontChanged: value => root.heading = value.weight >= Font.DemiBold
    Component.onCompleted: heading = font.weight >= Font.DemiBold
    color: Theme.text
    font.family: heading ? Theme.headingFamily : Theme.fontFamily
    font.pixelSize: Theme.bodySize
    font.hintingPreference: Font.PreferFullHinting
    textFormat: Text.PlainText
    renderType: Text.QtRendering
}
