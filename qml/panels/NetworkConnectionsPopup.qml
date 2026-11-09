// Role: NetworkConnectionsPopup.qml (wifi layer, fan-in 2).
// Panel/feature UI; dispatches backend actions via ShellState.run(action,payload) where applicable.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

MotionPopup {
    id: root
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(660, parent ? parent.width - 32 : 660)
    height: Math.min(780, parent ? parent.height - 32 : 780)
    padding: 20; modal: true; focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    readonly property var inventory: ShellState.networkConnections || {}
    readonly property var profiles: inventory.profiles || []
    readonly property var operation: inventory.operation || {}
    readonly property bool busy: ["networkRefresh", "networkConnect", "networkDisconnect", "networkHotspotPlan", "networkHotspotStart", "networkEdit", "wifiScan", "wifiConnect", "wifiSaved", "wifiDisconnect", "wifiForget", "wifiToggle"].some(a => ShellState.pendingActions[a])
    property var selections: ({})
    property string plannedUuid: ""
    property string plannedDevice: ""
    readonly property var plan: inventory.hotspotPlan || null
    function device(id) { return (inventory.devices || []).find(d => d.id === id) || null; }
    function activations(profile) { return (inventory.active || []).filter(a => a.uuid === profile.uuid); }
    function selected(profile) {
        const hint = inventory.lastRequest || {};
        const chosen = selections[profile.uuid] || (hint.uuid === profile.uuid && hint.serverId === inventory.serverId ? hint.deviceId : "");
        const active = activations(profile).find(a => profile.compatible.includes(a.deviceId));
        return profile.compatible.includes(chosen) ? chosen : active ? active.deviceId : profile.compatible[0] || "";
    }
    function choose(profile, id) { selections = Object.assign({}, selections, {[profile.uuid]:id}); }
    function request(profile, action) {
        const payload = {serverId:inventory.serverId,uuid:profile.uuid,deviceId:selected(profile)};
        if (profile.kind === "hotspot") {
            plannedUuid = profile.uuid; plannedDevice = payload.deviceId;
            ShellState.run("networkHotspotPlan",payload);
        } else ShellState.run(action,payload);
    }
    function refresh() { if (ShellState.backendReady && !busy) ShellState.run("networkRefresh"); }
    onOpened: refresh()
    onClosed: { selections = ({}); plannedUuid = ""; plannedDevice = ""; }
    Connections {
        target: ShellState
        function onLastResultChanged() {
            const result = ShellState.lastResult;
            if (result && result.action === "networkHotspotPlan" && !result.pending && result.ok && root.visible &&
                root.plan && root.plan.uuid === root.plannedUuid && root.plan.deviceId === root.plannedDevice) hotspotWarning.open();
        }
    }
    background: Rectangle {
        radius: Theme.radius; color: Theme.panel
        border.width: Theme.liquidGlass ? 0 : 1; border.color: Theme.border
        GlassMaterial { anchors.fill: parent; radius: parent.radius }
    }
    contentItem: ColumnLayout {
        objectName: "networkConnectionsBody"
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Saved network connections"; font.pixelSize: 22; font.weight: Font.Bold; Layout.fillWidth: true }
            IconButton { objectName: "networkClose"; glyph: "×"; tooltip: "Close network connections"; onClicked: root.close() }
        }
        LabelText {
            text: "NetworkManager applies saved routes and DNS. Credentials stay in your system keyring or network agent."
            color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText {
                Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.muted
                text: root.busy ? root.operation.cancelling ? "Cancelling; checking the actual connection…" : "Reading or updating NetworkManager…"
                    : root.inventory.checkedAt ? "Checked at " + Qt.formatDateTime(new Date(root.inventory.checkedAt), "hh:mm:ss") + ". Refresh after external changes."
                    : "Read on demand; no additional network monitor."
            }
            LiquidButton { objectName: "networkRefresh"; text: "Refresh"; enabled: ShellState.backendReady && !root.busy; onClicked: root.refresh() }
            LiquidButton {
                objectName: "networkCancel"; visible: !!root.operation.cancellable
                text: root.operation.cancelling ? "Cancelling…" : "Cancel activation"
                enabled: ShellState.backendReady && !root.operation.cancelling
                onClicked: ShellState.run("networkCancel")
            }
        }
        LabelText {
            objectName: "networkError"; visible: !!text
            text: root.inventory.error || root.inventory.notice || ""
            color: root.inventory.error ? Theme.red : Theme.muted
            Layout.fillWidth: true; wrapMode: Text.Wrap
        }
        Flickable {
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            contentWidth: width; contentHeight: groups.implicitHeight + 12
            boundsBehavior: Flickable.StopAtBounds; ScrollBar.vertical: ScrollBar {}
            ColumnLayout {
                id: groups; width: parent.width - 8; spacing: 14
                NetworkProfilesGroup { Layout.fillWidth: true; controller: root; title: "VPN & WireGuard"; entries: root.profiles.filter(p => p.kind === "vpn" || p.kind === "wireguard") }
                NetworkProfilesGroup { Layout.fillWidth: true; controller: root; title: "Ethernet"; entries: root.profiles.filter(p => p.kind === "ethernet") }
                LabelText { text: "IP addresses, DNS and VPN authentication are edited in the system network editor."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
                NetworkProfilesGroup { Layout.fillWidth: true; controller: root; title: "Hotspot"; entries: root.profiles.filter(p => p.kind === "hotspot") }
                LabelText {
                    text: "Create a secure shared hotspot profile in Advanced network settings. Starting it requires a fresh warning; a running hotspot does not prove Internet access."
                    color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12
                }
            }
        }
        LiquidButton {
            text: "Advanced network settings"; Layout.fillWidth: true
            onClicked: { ShellState.closePanels(); ShellState.run("openSettings",{target:"network"}); }
        }
    }
    MotionPopup {
        id: hotspotWarning
        parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(540,parent ? parent.width - 32 : 540)
        padding: 24; modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        onClosed: { root.plannedUuid = ""; root.plannedDevice = ""; }
        background: Rectangle {
            radius: 24; color: Theme.panel; border.width: Theme.liquidGlass ? 0 : 1; border.color: Theme.border
            GlassMaterial { anchors.fill: parent; radius: parent.radius }
        }
        contentItem: ColumnLayout {
            spacing: 14
            LabelText { text: "Start hotspot?"; font.pixelSize: 21; font.weight: Font.Bold }
            LabelText {
                objectName: "networkHotspotWarning"
                Layout.fillWidth: true; wrapMode: Text.Wrap
                text: !root.plan ? "Review the selected hotspot again." :
                    (root.plan.disconnectWifi ? "This will disconnect Wi-Fi “" + root.plan.previousConnection + "” on " + root.plan.interface + ".\n\n" : "Use " + root.plan.interface + " for “" + root.plan.name + "”.\n\n") +
                    (root.plan.uplinks.length ? "Other observed uplinks: " + root.plan.uplinks.join(", ") + ".\n\n" : "No other connected Ethernet/Wi-Fi uplink was observed. Sharing may have no Internet access.\n\n") + root.plan.warning
            }
            RowLayout {
                Layout.fillWidth: true
                LiquidButton { objectName: "networkHotspotCancel"; text: "Cancel"; onClicked: hotspotWarning.close() }
                Item { Layout.fillWidth: true }
                LiquidButton {
                    objectName: "networkHotspotConfirm"; text: "Start hotspot"
                    enabled: ShellState.backendReady && !root.busy && !!root.plan
                    onClicked: {
                        const plan = root.plan;
                        ShellState.run("networkHotspotStart",{serverId:root.inventory.serverId,uuid:plan.uuid,deviceId:plan.deviceId,planToken:plan.token,confirmed:true});
                    }
                }
            }
        }
    }
}
