import QtQuick
import "../services"

Item {
    id: root
    z: 10
    required property string moduleId
    property var screenInfo: null
    property var windowInfo: null
    property int originSerial: 0
    property real wheelRemainder: 0
    property int wheelSteps: 0
    function armOrigin() { originSerial = ShellState.armBarOrigin(parent, screenInfo, windowInfo); }
    function releaseOrigin() {
        const serial = originSerial;
        Qt.callLater(() => ShellState.clearBarOrigin(serial));
    }
    Connections {
        target: (root.parent as Loader).item
        ignoreUnknownSignals: true
        function onPressed() { root.armOrigin(); }
        function onReleased() { root.releaseOrigin(); }
        function onCanceled() { root.releaseOrigin(); }
    }
    TapHandler {
        acceptedButtons: Qt.RightButton | Qt.MiddleButton
        onTapped: (eventPoint, button) => {
            root.armOrigin();
            BarGestures.perform(root.moduleId, button === Qt.RightButton ? "right" : "middle", root.screenInfo);
            root.releaseOrigin();
        }
    }
    WheelHandler {
        target: null
        enabled: ["scrollUp", "scrollDown"].some(g => BarGestures.action(root.moduleId, g) !== "none")
        onWheel: event => {
            root.wheelRemainder += event.angleDelta.y / 120;
            const steps = Math.trunc(root.wheelRemainder);
            root.wheelRemainder -= steps;
            root.wheelSteps += steps;
            if (steps && !flush.running) flush.start();
        }
    }
    Timer {
        id: flush; interval: 60
        onTriggered: {
            if (root.wheelSteps) {
                const serial = ShellState.armBarOrigin(root.parent, root.screenInfo, root.windowInfo);
                BarGestures.perform(root.moduleId, root.wheelSteps > 0 ? "scrollUp" : "scrollDown", root.screenInfo, Math.abs(root.wheelSteps));
                ShellState.clearBarOrigin(serial);
            }
            root.wheelSteps = 0;
        }
    }
}
