pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    id: root
    spacing: 20
    readonly property var status: ShellState.snapshot.idle || {}
    readonly property var durations: [0,1,2,3,5,10,15,20,30,60,120,240]
    function refresh() { if (ShellState.backendReady) ShellState.run("idleRefresh"); }
    Component.onCompleted: refresh()
    Connections { target: ShellState; function onBackendReadyChanged() { if (ShellState.backendReady) root.refresh(); } }
    Timer { interval: 2000; running: ShellState.backendReady; repeat: true; onTriggered: root.refresh() }
    function choices(source, key, minutes) {
        const all = durations.includes(minutes) ? durations : durations.concat(minutes).sort((a,b)=>a-b);
        const profile = (ShellState.preferences.idleProfiles || {})[source] || {};
        return all.filter(n => n === 0 || key === "display" || (key === "lock" ? !profile.suspend || n <= profile.suspend : !profile.lock || n >= profile.lock));
    }
    function update(source, key, minutes) {
        const profiles = JSON.parse(JSON.stringify(ShellState.preferences.idleProfiles));
        profiles[source][key] = minutes;
        ShellState.run("setting", {key: "idleProfiles", value: profiles});
    }
    SettingsCard {
        title: "Laptop idle profiles"
        description: "Switch timeouts automatically when the charger is plugged in or removed. Enable after choosing your timeouts."
        PreferenceSwitch { title: "Automatic idle management"; detail: "The desktop shell owns one swayidle process."; preference: "idleEnabled" }
        LabelText { text: "Current source: "+(root.status.source === "ac" ? "AC power" : "Battery")+(root.status.paused ? " · Stay awake" : root.status.running ? " · Running" : ""); color: Theme.accent; font.weight: Font.Bold }
        LabelText { visible: root.status.available === false; text: "Install swayidle and swaylock, then restart the shell to enable idle management."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.yellow }
        LabelText { visible: !!root.status.error; text: root.status.error || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.red }
    }
    Repeater {
        model: [{key:"ac",title:"On AC power"},{key:"battery",title:"On battery"}]
        delegate: SettingsCard {
            id: profile; required property var modelData
            title: modelData.title
            description: "0 minutes disables that timeout. Lock must happen before automatic suspend."
            Repeater {
                model: [{key:"display",title:"Turn off displays"},{key:"lock",title:"Lock session"},{key:"suspend",title:"Suspend"}]
                delegate: RowLayout {
                    id: timeout; required property var modelData
                    Layout.fillWidth: true
                    LabelText { text: timeout.modelData.title; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    LiquidComboBox {
                        objectName: "idle-"+profile.modelData.key+"-"+timeout.modelData.key
                        Layout.preferredWidth: 150
                        property int minutes: ((ShellState.preferences.idleProfiles || {})[profile.modelData.key] || {})[timeout.modelData.key] || 0
                        property var choices: root.choices(profile.modelData.key, timeout.modelData.key, minutes)
                        model: choices.map(n => ({label: n === 0 ? "Never" : n+" min", minutes:n}))
                        textRole: "label"
                        currentIndex: choices.indexOf(minutes)
                        enabled: ShellState.backendReady && !ShellState.pendingActions.setting
                        Accessible.name: profile.modelData.title+" "+timeout.modelData.title
                        onActivated: root.update(profile.modelData.key, timeout.modelData.key, choices[currentIndex])
                    }
                }
            }
        }
    }
    SettingsCard {
        title: "Before sleep"
        PreferenceSwitch { title: "Lock before suspend"; detail: "Wait for swaylock to confirm a locked session before automatic or shell-requested suspend."; preference: "idleLockBeforeSleep" }
        LabelText { text: "Stay awake pauses these timeouts. Displays turn back on after input or resume. Disable other swayidle autostarts to avoid competing timers."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
}
