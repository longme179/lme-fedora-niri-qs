import QtQuick
import QtQuick.Layouts
import Quickshell
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    spacing: 20
    SettingsCard {
        title: "Lyrics"
        description: "Open Lyrics in a media card. Player metadata and local .lrc files are used first; LRCLIB results are cached. Online lookup sends track title, artist, album and duration to lrclib.net while a lyrics view is open or Activity Island displays lyrics during playback."
        PreferenceSwitch { title: "Enable lyrics"; detail: "Display synchronized or plain lyrics in media cards"; preference: "lyricsEnabled" }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Display mode"; Layout.fillWidth: true }
            LiquidComboBox {
                objectName: "lyricsDisplayMode"
                model: ["Full transcript · scroll", "Current line"]
                currentIndex: ShellState.preferences.lyricsMode === "line" ? 1 : 0
                Accessible.name: "Lyrics display mode"
                onActivated: ShellState.run("setting", {key: "lyricsMode", value: currentIndex ? "line" : "scroll"})
            }
        }
        PreferenceSwitch { title: "Follow lyrics by default"; detail: "Center the current line in the full transcript; manual scrolling pauses follow until you press Follow"; preference: "lyricsFollow" }
        PreferenceSwitch { title: "Lyrics on Activity Island"; detail: "Show the current synchronized line while playing; use the track title when lyrics or timing are unavailable"; preference: "activityLyrics" }
        PreferenceSwitch { title: "Online lyrics · LRCLIB"; detail: "Optional network lookup; cached and local lyrics work offline"; preference: "lyricsOnline" }
    }
    SettingsCard {
        title: "Bluetooth pairing"
        description: "Scan and pair from Control center → Devices, including PIN and passkey confirmation. The agent runs only while the Devices panel is open. Requires python3-gobject-base (Gio/GLib)."
        PreferenceSwitch { title: "Pair Bluetooth devices in the shell"; detail: "External device settings remain available"; preference: "bluetoothPairing" }
    }
    SettingsCard {
        title: "Device batteries"
        description: "Headphones, mice and keyboards appear in Control center → Devices when BlueZ or the kernel reports their battery. A device without a reading shows no estimated percentage. Alerts respect Do Not Disturb."
        PreferenceSwitch { title: "Low device battery alerts"; detail: "Warn once per low-battery cycle; reconnecting does not repeat an alert in this shell session"; preference: "peripheralBatteryAlerts" }
        LabelText { text: "Low battery threshold · " + (ShellState.preferences.peripheralBatteryThreshold || 20) + "%" }
        LiquidSlider {
            objectName: "peripheralBatteryThreshold"
            Layout.fillWidth: true; from: 5; to: 50; stepSize: 1
            value: ShellState.preferences.peripheralBatteryThreshold || 20
            onMoved: if (!pressed) ShellState.run("setting", {key: "peripheralBatteryThreshold", value: Math.round(value)})
            onPressedChanged: if (!pressed) ShellState.run("setting", {key: "peripheralBatteryThreshold", value: Math.round(value)})
            Accessible.name: "Low device battery threshold"
        }
    }
    SettingsCard {
        title: "Privacy and media"
        description: "PipeWire capture activity and niri screen casts. Direct V4L2 camera access outside PipeWire is not detected."
        PreferenceSwitch { title: "Quick notes"; detail: "An autosaved text buffer in Control Center → Agenda"; preference: "quickNotes" }
        PreferenceSwitch { title: "Audio spectrum"; detail: "Real Cava spectrum while a visible media card is playing; requires cava"; preference: "audioVisualizer" }
        PreferenceSwitch { title: "Battery health details"; detail: "Show health, power and time when reported by the kernel"; preference: "batteryDetails" }
        PreferenceSwitch { title: "Capture indicators"; detail: "Show active microphone, camera and screen sharing"; preference: "privacyIndicators" }
        PreferenceSwitch { title: "Silence popups while sharing"; detail: "Automatic suppression preserves your manual DND setting"; preference: "dndWhileSharing" }
    }
    SettingsCard {
        title: "Screen recording"
        description: "Auto tries NVIDIA NVENC, integrated GPU VAAPI, then CPU. Drivers are probed only when you start recording, so the RTX is not polled while idle."
        PreferenceSwitch { title: "Recording controls"; detail: "Capture card and Island start/stop controls"; preference: "recordingEnabled" }
        RowLayout {
            ExpressiveField { id: recordings; Layout.fillWidth:true; text:ShellState.preferences.recordingFolder || ""; Accessible.name:"Recording folder" }
            LiquidButton { text:"Save folder"; onClicked:ShellState.run("setting",{key:"recordingFolder",value:recordings.text}) }
        }
        RowLayout {
            LabelText { text: "Encoder"; Layout.fillWidth: true }
            LiquidComboBox {
                property var values: ["auto","nvidia","radeon","cpu"]
                model: ["Auto · NVIDIA → iGPU → CPU","NVIDIA only · NVENC","Radeon only · VAAPI","CPU only"]
                currentIndex: values.indexOf(ShellState.preferences.recordingEncoder || "auto")
                Accessible.name: "Recording encoder"
                onActivated: ShellState.run("setting",{key:"recordingEncoder",value:values[currentIndex]})
            }
        }
        RowLayout {
            LabelText { text: "Container"; Layout.fillWidth: true }
            LiquidComboBox {
                id: recordingFormat; objectName: "recordingFormat"; model: ["mkv","mp4","mov","webm"]
                currentIndex: model.indexOf(ShellState.preferences.recordingFormat || "mkv")
                Accessible.name: "Recording container"
                onActivated: {
                    const allowed = currentText === "webm" ? ["auto","av1","vp9"] : currentText === "mov" ? ["auto","h264","hevc"] : ["auto","h264","hevc","av1","vp9"];
                    ShellState.run("setting",{key:"recordingFormat",value:currentText});
                    if (!allowed.includes(ShellState.preferences.recordingCodec || "auto")) ShellState.run("setting",{key:"recordingCodec",value:"auto"});
                }
            }
        }
        RowLayout {
            LabelText { text: "Video codec"; Layout.fillWidth: true }
            LiquidComboBox {
                objectName: "recordingCodec"
                model: ShellState.preferences.recordingFormat === "webm" ? ["auto","av1","vp9"] : ShellState.preferences.recordingFormat === "mov" ? ["auto","h264","hevc"] : ["auto","h264","hevc","av1","vp9"]
                currentIndex: Math.max(0, model.indexOf(ShellState.preferences.recordingCodec || "auto"))
                Accessible.name: "Recording video codec"
                onActivated: ShellState.run("setting",{key:"recordingCodec",value:currentText})
            }
        }
        RowLayout {
            LabelText { text: "Frame rate"; Layout.fillWidth: true }
            LiquidComboBox {
                model: ["24 fps","30 fps","60 fps","120 fps"]
                currentIndex: [24,30,60,120].indexOf(ShellState.preferences.recordingFps || 30)
                Accessible.name: "Recording frame rate"
                onActivated: ShellState.run("setting",{key:"recordingFps",value:[24,30,60,120][currentIndex]})
            }
        }
        RowLayout {
            LabelText { text: "Bitrate · kbps"; Layout.fillWidth: true }
            ExpressiveField { id: bitrate; Layout.preferredWidth: 110; text: String(ShellState.preferences.recordingBitrate || 12000); maximumLength: 6; Accessible.name: "Recording bitrate in kbps" }
            LiquidButton { text: "Apply"; enabled: /^\d+$/.test(bitrate.text) && Number(bitrate.text) >= 1000 && Number(bitrate.text) <= 100000; onClicked: ShellState.run("setting",{key:"recordingBitrate",value:Number(bitrate.text)}) }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Default recording audio"; Layout.fillWidth: true }
            LiquidComboBox { objectName: "recordingAudioDefault"; model: ["No audio", "System audio", "Microphone"]; currentIndex: ["none","system","microphone"].indexOf(ShellState.preferences.recordingAudio || "system"); Accessible.name: "Default recording audio"; onActivated: ShellState.run("setting", {key: "recordingAudio", value: ["none","system","microphone"][currentIndex]}) }
        }
        LabelText { text: "Your audio choice is saved. Microphone recording is explicit; System audio captures the default speaker or Bluetooth output. Saved audio recordings are checked with ffprobe."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
        LabelText { text:"Requires wf-recorder and FFmpeg with the chosen codecs. Audio needs pactl (pulseaudio-utils); region selection needs slurp. MP4/MOV use AAC audio; MKV/WebM use Opus. Other recording apps are never stopped. High frame rates and CPU AV1 can be expensive."; Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted }
    }
    SettingsCard {
        title: "Image annotation"
        description: "Click a clipboard image or screenshot notification to open this editor with a saved copy. Screenshot studio → Annotate externally saves your flattened edits, including redactions. External edits are not imported back into the studio."
        RowLayout {
            LabelText { text: "External editor"; Layout.fillWidth: true }
            LiquidComboBox {
                property var values: ["auto","satty","swappy"]
                model: ["Auto · Satty then Swappy","Satty","Swappy"]
                currentIndex: values.indexOf(ShellState.preferences.captureEditor || "auto")
                Accessible.name: "External screenshot editor"
                onActivated: ShellState.run("setting",{key:"captureEditor",value:values[currentIndex]})
            }
        }
        LabelText { text: "Fedora: sudo dnf install swappy. Satty is also supported if installed separately. Choose the output path inside the external editor when saving further edits."; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
    }
    SettingsCard {
        title: "Launcher file search"
        description: "Use / followed by a filename in the launcher. Hidden files and symlinks are skipped; each search has a time/path/result limit. No background index is created."
        PreferenceSwitch { title: "Search files and folders"; detail: "Names in your selected local folders"; preference: "fileSearchEnabled" }
        ExpressiveField { id: fileFolders; Layout.fillWidth: true; text: (ShellState.preferences.fileSearchRoots || []).join("; "); placeholderText: "Folders separated by semicolons"; Accessible.name: "Launcher search folders" }
        LiquidButton { text: "Save search folders"; onClicked: ShellState.run("setting",{key:"fileSearchRoots",value:fileFolders.text.split(";").map(p=>p.trim()).filter(Boolean)}) }
    }
    SettingsCard {
        title: "Launcher app ranking"
        description: "Bring frequently and recently launched apps forward. Exact name matches keep priority. Only launches from this shell are counted locally; no window-use tracking or favorites."
        PreferenceSwitch { title: "Rank by usage"; detail: "Seven-day decay, up to 60 days of history"; preference:"launcherRanking" }
        LiquidButton { objectName:"launcherHistoryClear"; text:"Clear launch history"; enabled:ShellState.backendReady && !ShellState.pendingActions.launcherHistoryClear; onClicked:ShellState.run("launcherHistoryClear") }
        LabelText { visible:!!ShellState.snapshot.launcherHistoryError; text:ShellState.snapshot.launcherHistoryError || ""; color:Theme.yellow; wrapMode:Text.Wrap; Layout.fillWidth:true }
    }
    SettingsCard {
        title: "Default terminal"
        description: "Executable name only, for example kitty or foot."
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ExpressiveField {
                id: terminal
                Layout.fillWidth: true
                text: ShellState.preferences.terminal || "kitty"
                placeholderText: "kitty"
                Accessible.name: "Default terminal executable"
                onAccepted: if (save.enabled) save.clicked()
            }
            LiquidButton {
                id: save
                text: "Save"
                enabled: terminal.text.trim().length > 0 && ShellState.backendReady && !ShellState.pendingActions.setting
                onClicked: ShellState.run("setting", {key: "terminal", value: terminal.text.trim()})
            }
        }
    }
    SettingsCard {
        title: "Volume and brightness OSD"
        description: "Spring popups follow the focused niri output, a chosen output, or all connected displays. Each output owns its popup timer."
        PreferenceSwitch { title: "Show OSD"; detail: "Volume and brightness feedback"; preference: "osdEnabled" }
        RowLayout {
            LabelText { text: "Position"; Layout.fillWidth: true }
            LiquidComboBox { property var positions: ["top-left","top-center","top-right","center-left","center","center-right","bottom-left","bottom-center","bottom-right"]; model: positions; currentIndex: positions.indexOf(ShellState.preferences.osdPosition || "bottom-center"); onActivated: ShellState.run("setting",{key:"osdPosition",value:currentText}); Accessible.name: "OSD position" }
        }
        RowLayout {
            LabelText { text: "Layout"; Layout.fillWidth: true }
            LiquidComboBox { model: ["Horizontal","Vertical"]; currentIndex: ShellState.preferences.osdLayout === "vertical" ? 1 : 0; onActivated: ShellState.run("setting",{key:"osdLayout",value:currentIndex ? "vertical" : "horizontal"}); Accessible.name: "OSD layout" }
        }
        RowLayout {
            LabelText { text: "Output"; Layout.fillWidth: true }
            LiquidComboBox { property var outputs: ["focused","all",...Quickshell.screens.map(s => s.name)]; model: outputs; currentIndex: outputs.indexOf(ShellState.preferences.osdOutput || "focused"); onActivated: ShellState.run("setting",{key:"osdOutput",value:currentText}); Accessible.name: "OSD output" }
        }
        LabelText { text: "Edge distance · " + (ShellState.preferences.osdMargin === undefined ? 24 : ShellState.preferences.osdMargin) + " px" }
        LiquidSlider { Layout.fillWidth: true; from: 0; to: 96; stepSize: 1; value: ShellState.preferences.osdMargin === undefined ? 24 : ShellState.preferences.osdMargin; onMoved: if(!pressed) ShellState.run("setting",{key:"osdMargin",value:Math.round(value)}); onPressedChanged: if(!pressed) ShellState.run("setting",{key:"osdMargin",value:Math.round(value)}); Accessible.name: "OSD edge distance" }
    }
    SettingsCard {
        title: "Settings export and restore"
        description: "Portable presets exclude tasks, location, device IDs and file paths. Private backups include all settings, but not clipboard, notifications or notes. Import validates every field and backs up current settings first."
        ExpressiveField { id: transfer; Layout.fillWidth: true; text: Quickshell.env("HOME") + "/lme-preset.json"; placeholderText: "Absolute JSON file path"; Accessible.name: "Settings transfer path" }
        Flow {
            Layout.fillWidth: true; spacing: 8
            LiquidButton { text: "Export preset"; enabled: !ShellState.demo; onClicked: ShellState.run("settingsExport",{path:transfer.text,kind:"preset"}) }
            LiquidButton { text: "Export private backup"; enabled: !ShellState.demo; onClicked: ShellState.run("settingsExport",{path:transfer.text,kind:"backup"}) }
            LiquidButton { text: "Import and back up current"; enabled: !ShellState.demo; onClicked: ShellState.run("settingsImport",{path:transfer.text}) }
        }
        LabelText { text: "Exports refuse to replace existing files. Choose a new filename. To propose factory defaults, send only the portable preset JSON."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
    SettingsCard {
        title: "Made for your session"
        description: "The settings app and shell share preferences. Changes are saved automatically and appear in the running shell."
        LabelText { text: "Use Super+Comma or the top bar settings button to open this window. You can also start it from your application launcher."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
}
