import QtQuick
import Quickshell
import Quickshell.Services.Polkit
import "../services"

Scope {
    id: root
    readonly property bool registered: agent.isRegistered
    PolkitAgent {
        id: agent
        onAuthenticationRequestStarted: ShellState.closePanels()
    }
    Binding { target: ShellState; property: "authenticationActive"; value: agent.isActive }
    AuthenticationWindow {
        screen: ShellState.panelScreen || Quickshell.screens[0]
        flow: agent.flow
    }
}
