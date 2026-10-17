pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    id: root
    spacing: 20
    readonly property var palette: ShellState.snapshot.palettePreview || {colors:{},path:""}
    readonly property string palettePath: selectedPath || ShellState.preferences.wallpaper || ""
    readonly property var schemes: Theme.paletteSchemes
    readonly property bool previewMatches: palette.path === palettePath && ["paletteScheme", "paletteMode", "paletteContrast"].every(key => palette[key] === ShellState.preferences[key])
    property string query: ""
    property string selectedPath: ""
    readonly property var library: ShellState.snapshot.wallpaperLibrary || {entries: []}
    readonly property var entries: (library.entries || []).filter(e => e.name.toLowerCase().includes(query.toLowerCase()))
    function scan(path) {
        if (!path.trim()) return;
        ShellState.run("setting", {key: "wallpaperFolder", value: path});
        ShellState.run("wallpaperScan", {folder: path});
    }
    function initialize() { if (ShellState.backendReady && (ShellState.preferences.wallpaperFolder || ShellState.demo)) ShellState.run("wallpaperScan", {folder: ShellState.preferences.wallpaperFolder}); }
    Component.onCompleted: initialize()
    Connections { target: ShellState; function onBackendReadyChanged() { if (ShellState.backendReady) root.initialize(); } }
    FolderDialog {
        id: folderChooser; title: "Choose a wallpaper folder"
        onAccepted: { const url = selectedFolder.toString(); if (url.startsWith("file://")) { folder.text = decodeURIComponent(url.substring(7)); root.scan(folder.text); } }
    }
    FileDialog {
        id: chooser; title: "Choose a wallpaper"
        nameFilters: ["Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"]
        fileMode: FileDialog.OpenFile
        onAccepted: { const url = selectedFile.toString(); if (url.startsWith("file://")) root.selectedPath = decodeURIComponent(url.substring(7)); }
    }
    SettingsCard {
        title: "Wallpaper library"
        description: "Browse a folder and search image names. awww applies the selected image."
        RowLayout {
            Layout.fillWidth: true
            ExpressiveField { id: folder; Layout.fillWidth: true; text: ShellState.preferences.wallpaperFolder || ""; placeholderText: "Wallpaper folder path"; Accessible.name: "Wallpaper folder"; onAccepted: root.scan(text) }
            LiquidButton { text: "Browse…"; onClicked: folderChooser.open() }
        }
        RowLayout {
            Layout.fillWidth: true
            ExpressiveField { Layout.fillWidth: true; placeholderText: "Search images"; Accessible.name: "Search wallpapers"; onTextChanged: root.query = text }
            LiquidButton { text: ShellState.pendingActions.wallpaperScan ? "Scanning…" : "Scan"; enabled: !ShellState.pendingActions.wallpaperScan && folder.text.trim().length > 0; onClicked: root.scan(folder.text) }
        }
        LabelText { visible: !!root.library.error || !!root.library.truncated; text: root.library.error || "Showing up to 500 images from 10,000 paths. Choose a smaller folder to see the rest."; color: Theme.yellow; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: root.entries.length ? 390 : 100
            GridView {
                id: gallery; anchors.fill: parent; clip: true
                cellWidth: width / Math.max(1, Math.floor(width / 180)); cellHeight: 150
                model: root.entries; boundsBehavior: Flickable.StopAtBounds; ScrollBar.vertical: ScrollBar {}
                delegate: Item {
                    id: thumb; required property var modelData; width: gallery.cellWidth; height: gallery.cellHeight
                    Rectangle {
                        anchors.fill: parent; anchors.margins: 5; radius: 16; color: Theme.surface
                        border.width: root.selectedPath === thumb.modelData.path ? 2 : 0; border.color: Theme.accent
                        Image { anchors.fill: parent; anchors.margins: 3; anchors.bottomMargin: 34; source: thumb.modelData.url; sourceSize.width: 300; sourceSize.height: 180; asynchronous: true; fillMode: Image.PreserveAspectCrop; clip: true }
                        LiquidButton { anchors.fill: parent; flat: true; cornerRadius: parent.radius; Accessible.name: "Preview " + thumb.modelData.name; background: Item {}  contentItem: Item {}  onClicked: root.selectedPath = thumb.modelData.path }
                        LabelText { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10; text: thumb.modelData.name; font.pixelSize: 12; elide: Text.ElideRight }
                    }
                }
            }
            LabelText { anchors.centerIn: parent; width: parent.width - 20; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; visible: !root.entries.length; text: ShellState.pendingActions.wallpaperScan ? "Scanning images…" : root.query ? "No matching images" : "Choose a folder to browse your wallpapers."; color: Theme.muted }
        }
    }
    SettingsCard {
        title: "Material palette from wallpaper"
        enabled: !Theme.liquidGlass
        description: Theme.liquidGlass ? "Liquid glass uses neutral colors. Switch it off in Appearance to preview and apply Material palettes; your saved palette is preserved."
            : "Choose a Material scheme, dark/light mode and contrast, then preview before applying. Dracula remains the default. Glass opacity and manual element overrides are preserved; no external app themes are changed. Requires matugen."
        RowLayout {
            Layout.fillWidth: true
            LiquidComboBox { objectName: "paletteScheme"; Layout.fillWidth: true; model: root.schemes.map(s => Theme.tokenTitle(s.replace(/-/g, " "))); currentIndex: root.schemes.indexOf(ShellState.preferences.paletteScheme || "tonal-spot"); Accessible.name: "Material color scheme"; onActivated: ShellState.run("setting", {key:"paletteScheme",value:root.schemes[currentIndex]}) }
            LiquidComboBox { model: ["Dark", "Light"]; currentIndex: ShellState.preferences.paletteMode === "light" ? 1 : 0; Accessible.name: "Material color mode"; onActivated: ShellState.run("setting", {key:"paletteMode",value:currentIndex ? "light" : "dark"}) }
        }
        LabelText { text: "Contrast · " + materialContrast.value.toFixed(1) + " (0 = standard)"; font.weight: Font.Bold }
        LiquidSlider {
            id: materialContrast; Layout.fillWidth: true; from: -1; to: 1; stepSize: .1
            Accessible.name: "Material palette contrast"
            onMoved: if (!pressed) ShellState.run("setting", {key:"paletteContrast",value:Math.round(value*10)/10})
            onPressedChanged: if (!pressed) ShellState.run("setting", {key:"paletteContrast",value:Math.round(value*10)/10})
        }
        Binding { target: materialContrast; property: "value"; value: ShellState.preferences.paletteContrast || 0; when: !materialContrast.pressed; restoreMode: Binding.RestoreNone }
        RowLayout {
            LiquidButton { text: ShellState.pendingActions.palettePreview ? "Generating…" : "Preview palette"; enabled: !ShellState.demo && !!root.palettePath && !ShellState.pendingActions.palettePreview; onClicked: ShellState.run("palettePreview",{path:root.palettePath}) }
            LiquidButton { text: "Apply palette"; enabled: !ShellState.demo && root.previewMatches && !!root.palette.colors.accent; onClicked: ShellState.run("paletteApply",{path:root.palettePath}) }
            LiquidButton { text: "Use Dracula"; onClicked: ShellState.run("paletteReset") }
        }
        Flow {
            Layout.fillWidth: true; spacing: 8
            Repeater {
                model: Object.keys(root.palette.colors || {})
                delegate: Rectangle { required property string modelData; width: 50; height: 42; radius: 12; color: root.palette.colors[modelData]; ToolTip.visible: hovered.hovered; ToolTip.text: Theme.tokenTitle(modelData); HoverHandler { id: hovered } }
            }
        }
        LabelText { text: "Current source: " + (ShellState.preferences.paletteSource || "dracula"); color: Theme.muted }
    }
    SettingsCard {
        title: "Your backdrop"
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 240; radius: 20; color: Theme.surfaceContainer; clip: true
            Image { anchors.fill: parent; source: root.selectedPath ? "file://" + encodeURI(root.selectedPath).replace(/#/g, "%23").replace(/\?/g, "%3F") : ShellState.preferences.wallpaper ? "file://" + encodeURI(ShellState.preferences.wallpaper).replace(/#/g, "%23").replace(/\?/g, "%3F") : "../../assets/wallpapers/liquid-dracula.png"; sourceSize.width: 900; asynchronous: true; fillMode: Image.PreserveAspectCrop }
        }
        LabelText { text: root.selectedPath || ShellState.preferences.wallpaper || "Bundled Dracula wallpaper"; color: Theme.muted; Layout.fillWidth: true; elide: Text.ElideMiddle }
        RowLayout {
            LiquidButton { text: ShellState.pendingActions.wallpaper ? "Applying…" : "Apply wallpaper"; enabled: root.selectedPath.length > 0 && ShellState.backendReady && !ShellState.pendingActions.wallpaper; onClicked: ShellState.run("wallpaper", {path: root.selectedPath}) }
            LiquidButton { text: "Choose an image…"; onClicked: chooser.open() }
        }
    }
}
