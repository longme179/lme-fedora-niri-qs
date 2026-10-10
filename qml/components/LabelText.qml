import QtQuick
import "../theme"
Text {
    color: Theme.text
    font.family: Theme.fontFamily
    font.pixelSize: Theme.bodySize
    font.hintingPreference: Font.PreferFullHinting
    textFormat: Text.PlainText
    renderType: Text.QtRendering
}
