import QtQuick

Item {
    id: root
    z: 10
    required property string moduleId
    property var screenInfo: null
    property real wheelRemainder: 0
    property int wheelSteps: 0
    TapHandler {
        acceptedButtons: Qt.RightButton | Qt.MiddleButton
        onTapped: (eventPoint, button) => BarGestures.perform(root.moduleId, button === Qt.RightButton ? "right" : "middle", root.screenInfo)
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
            if (root.wheelSteps) BarGestures.perform(root.moduleId, root.wheelSteps > 0 ? "scrollUp" : "scrollDown", root.screenInfo, Math.abs(root.wheelSteps));
            root.wheelSteps = 0;
        }
    }
}
