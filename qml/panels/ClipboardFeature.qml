// Role: ClipboardFeature.qml (clipboard layer, fan-in 2).
// Panel/feature UI; dispatches backend actions via ShellState.run(action,payload) where applicable.
import QtQuick
import "../services"

QtObject { Component.onCompleted: ClipboardState.start() }
