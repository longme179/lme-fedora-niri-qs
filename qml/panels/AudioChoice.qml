// Role: AudioChoice.qml (audio layer, fan-in 3).
// Panel/feature UI; dispatches backend actions via ShellState.run(action,payload) where applicable.
pragma ComponentBehavior: Bound
import QtQuick
import "../components"

LiquidComboBox {
    id: root
    property var choices: []
    property string actual: ""
    property string unknownText: "Not reported by server"
    readonly property int actualIndex: choices.findIndex(item => item.name === actual)
    signal chosen(string name)
    model: choices.map(item => item.title + (item.available ? "" : " · unavailable"))
    disabledIndices: choices.map((item,index) => item.available ? -1 : index).filter(index => index >= 0)
    currentIndex: actualIndex
    displayText: actualIndex >= 0 ? choices[actualIndex].title + (choices[actualIndex].available ? "" : " · unavailable") : unknownText
    onActualIndexChanged: currentIndex = actualIndex
    onModelChanged: currentIndex = actualIndex
    onActivated: index => {
        const item = choices[index];
        if (item && item.available) chosen(item.name);
        // Selection is a request; the displayed value always follows observed state.
        currentIndex = actualIndex;
    }
}
