pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../services"
import "../theme"
SettingsCard {
    id: root
    objectName:"gowallStudio"
    title:"Gowall image studio"
    description:"Recolor wallpapers, upscale or extract colors. Originals stay untouched. Preview first, then save or apply with awww. Requires gowall."
    property var paths:[]
    property int selectedImage:0
    readonly property string currentWallpaper:(ShellState.preferences.wallpaperOutputs || {})[ShellState.preferences.wallpaperPlaylistOutput] || ShellState.preferences.wallpaper || ""
    readonly property var result:ShellState.snapshot.imageUtilities || {themes:[],images:[],colors:[]}
    readonly property bool busy:Object.keys(ShellState.pendingActions).some(key=>key.startsWith("gowall"))
    readonly property var operations:["palette","upscale","extract","brightness","contrast","saturation","grayscale","invert","pixelate","resize"]
    readonly property string operation:operations[operationBox.currentIndex]
    readonly property var themes:(result.themes || []).filter(name=>name.toLowerCase().includes(themeSearch.text.toLowerCase()))
    readonly property var preview:(result.images || [])[selectedImage] || ({})
    function generate() {
        ShellState.run("gowallGenerate",{paths:paths,operation:operation,options:{theme:themeBox.currentText,scale:scaleBox.currentIndex+2,colors:Math.round(colorCount.value),amount:Number(amount.text),dimensions:dimensions.text}});
    }
    FileDialog {
        id:inputs; title:"Choose images for gowall"; fileMode:FileDialog.OpenFiles
        nameFilters:["Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"]
        onAccepted:root.paths=selectedFiles.map(url=>decodeURIComponent(url.toString().replace(/^file:\/\//,"")))
    }
    FileDialog {
        id:saveDialog; title:"Save processed PNG"; fileMode:FileDialog.SaveFile; nameFilters:["PNG image (*.png)"]; defaultSuffix:"png"
        onAccepted:ShellState.run("gowallSave",{path:root.preview.path,destination:decodeURIComponent(selectedFile.toString().replace(/^file:\/\//,""))})
    }
    Flow {
        Layout.fillWidth:true; spacing:8
        LiquidButton { objectName:"gowallChoose"; text:"Choose images…"; enabled:!root.busy; onClicked:inputs.open() }
        LiquidButton { text:"Use current wallpaper"; enabled:!root.busy && !!root.currentWallpaper; onClicked:root.paths=[root.currentWallpaper] }
        LiquidButton { objectName:"gowallLoadThemes"; text:"Load themes"; enabled:!root.busy; onClicked:ShellState.run("gowallThemes") }
    }
    LabelText { text:root.paths.length ? root.paths.length+" image(s) · "+root.paths.join(" · ") : "Choose up to 24 images"; Layout.fillWidth:true; wrapMode:Text.Wrap; maximumLineCount:3; elide:Text.ElideMiddle; color:Theme.muted; font.pixelSize:12 }
    LiquidComboBox { id:operationBox; objectName:"gowallOperation"; Layout.fillWidth:true; model:["Change palette","Upscale","Extract palette","Brightness","Contrast","Saturation","Grayscale","Invert","Pixelate","Resize"]; Accessible.name:"Gowall operation"; onActivated:{ amount.text=root.operation==="brightness" ? "1.1" : root.operation==="pixelate" ? "15" : "0"; } }
    RowLayout {
        visible:root.operation==="palette"; Layout.fillWidth:true
        ExpressiveField { id:themeSearch; Layout.fillWidth:true; placeholderText:"Search gowall themes"; Accessible.name:"Search gowall themes" }
        LiquidComboBox { id:themeBox; objectName:"gowallTheme"; Layout.fillWidth:true; model:root.themes; displayText:currentText || "Load themes first"; Accessible.name:"Gowall theme" }
    }
    ColumnLayout {
        visible:root.operation==="upscale"; Layout.fillWidth:true
        LiquidComboBox { id:scaleBox; model:["2×","3×","4×"]; Accessible.name:"Upscale factor" }
        LabelText { text:"Upscale uses gowall's Vulkan model. First run: use Setup in terminal and answer gowall's download prompt, then Generate preview here. This may take several minutes."; Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted; font.pixelSize:12 }
        LiquidButton { text:"Setup in terminal…"; enabled:!ShellState.demo && !root.busy && root.paths.length>0; onClicked:ShellState.run("gowallSetup",{path:root.paths[0]}) }
    }
    ColumnLayout {
        visible:root.operation==="extract"; Layout.fillWidth:true
        LabelText { text:"Colors · "+Math.round(colorCount.value) }
        LiquidSlider { id:colorCount; Layout.fillWidth:true; from:2; to:16; stepSize:1; value:8; Accessible.name:"Number of extracted colors" }
    }
    ExpressiveField {
        id:amount; visible:["brightness","contrast","saturation","pixelate"].includes(root.operation); Layout.fillWidth:true; text:"1.1"
        placeholderText:root.operation==="brightness" ? "Brightness multiplier (0.1–10)" : root.operation==="pixelate" ? "Pixelation scale (1–25)" : "Amount (-99–99)"; Accessible.name:placeholderText
    }
    ExpressiveField { id:dimensions; visible:root.operation==="resize"; Layout.fillWidth:true; text:"1920x1080"; placeholderText:"Width × height, e.g. 1920x1080"; Accessible.name:"Resize dimensions" }
    LiquidButton { objectName:"gowallGenerate"; text:root.busy ? "Working…" : "Generate preview"; enabled:!ShellState.demo && !root.busy && root.paths.length>0 && (root.operation!=="palette" || !!themeBox.currentText); onClicked:root.generate() }
    Rectangle {
        visible:!!root.preview.url; Layout.fillWidth:true; Layout.preferredHeight:260; radius:16; color:Theme.surface; clip:true
        Image { anchors.fill:parent; anchors.margins:4; source:root.preview.url || ""; asynchronous:true; fillMode:Image.PreserveAspectFit; sourceSize.width:1000; sourceSize.height:600 }
    }
    LiquidComboBox { visible:(root.result.images || []).length>1; Layout.fillWidth:true; model:(root.result.images || []).map(item=>item.name); currentIndex:root.selectedImage; Accessible.name:"Processed image"; onActivated:root.selectedImage=currentIndex }
    Flow {
        Layout.fillWidth:true; spacing:8
        Repeater {
            model:root.result.colors || []
            delegate: Item { required property string modelData; width:80; height:64
                Rectangle { anchors.top:parent.top; width:80; height:38; radius:12; color:parent.modelData }
                LabelText { anchors.horizontalCenter:parent.horizontalCenter; anchors.bottom:parent.bottom; text:parent.modelData; font.pixelSize:11 }
            }
        }
    }
    Flow {
        visible:!!root.preview.path; Layout.fillWidth:true; spacing:8
        LiquidButton { text:"Save PNG…"; enabled:!root.busy; onClicked:saveDialog.open() }
        LiquidButton { text:"Use as wallpaper"; enabled:!root.busy && !ShellState.pendingActions.wallpaper; onClicked:ShellState.run("gowallApply",{path:root.preview.path,output:ShellState.preferences.wallpaperPlaylistOutput || ""}) }
    }
    LabelText { visible:!!root.preview.path; text:"Wallpaper target: "+(ShellState.preferences.wallpaperPlaylistOutput || "Shared background")+". Change target and transitions in Wallpaper settings."; Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted; font.pixelSize:12 }
    LabelText { visible:!!root.result.log; text:root.result.log || ""; textFormat:Text.PlainText; Layout.fillWidth:true; wrapMode:Text.Wrap; maximumLineCount:8; elide:Text.ElideRight; color:Theme.muted; font.pixelSize:12 }
    Connections { target:ShellState; function onLastResultChanged() { if(ShellState.lastResult && ShellState.lastResult.action==="gowallGenerate" && ShellState.lastResult.ok && !ShellState.lastResult.pending) root.selectedImage=0; } }
}
