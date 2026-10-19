pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
SettingsCard {
    id:root
    title:"Awww engine"
    description:"Fine-tune image scaling and transition motion. All wallpaper changes use these options, including playlists and Gowall outputs."
    readonly property var daemon:ShellState.snapshot.wallpaperDaemon || ({})
    readonly property bool ready:ShellState.backendReady && !ShellState.pendingActions.setting
    Flow {
        Layout.fillWidth:true; spacing:8
        LiquidButton { text:"Check daemon"; enabled:!ShellState.pendingActions.wallpaperStatus; onClicked:ShellState.run("wallpaperStatus") }
        LiquidButton { text:"Start if needed"; enabled:!ShellState.pendingActions.wallpaperEnsure; onClicked:ShellState.run("wallpaperEnsure") }
    }
    LabelText { text:root.daemon.error || root.daemon.query || "Check the daemon to see its current displays and images."; textFormat:Text.PlainText; Layout.fillWidth:true; wrapMode:Text.Wrap; color:root.daemon.error ? Theme.yellow : Theme.muted; font.pixelSize:12 }
    Repeater {
        model:[{key:"wallpaperTransitionFps",title:"Transition frame rate",min:10,max:240}, {key:"wallpaperTransitionStep",title:"Simple fade step (smaller is smoother)",min:1,max:255}, {key:"wallpaperTransitionAngle",title:"Wipe / wave angle",min:0,max:360}]
        delegate: ColumnLayout {
            id:control; required property var modelData; Layout.fillWidth:true
            LabelText { text:control.modelData.title+" · "+Math.round(slider.value); font.weight:Font.Bold }
            LiquidSlider {
                id:slider; objectName:control.modelData.key; Layout.fillWidth:true; from:control.modelData.min; to:control.modelData.max; stepSize:1; enabled:root.ready
                Accessible.name:control.modelData.title
                onMoved:if(!pressed) ShellState.run("setting",{key:control.modelData.key,value:Math.round(value)})
                onPressedChanged:if(!pressed) ShellState.run("setting",{key:control.modelData.key,value:Math.round(value)})
            }
            Binding { target:slider; property:"value"; value:ShellState.preferences[control.modelData.key]; when:!slider.pressed; restoreMode:Binding.RestoreNone }
        }
    }
    Repeater {
        model:[{key:"wallpaperResize",title:"Image sizing",values:["crop","fit","stretch","no"]}, {key:"wallpaperFilter",title:"Resampling filter",values:["Nearest","Bilinear","CatmullRom","Mitchell","Lanczos3"]}, {key:"wallpaperTransitionPosition",title:"Circle origin",values:["center","top","bottom","left","right","top-left","top-right","bottom-left","bottom-right"]}]
        delegate: RowLayout {
            id:choice; required property var modelData; Layout.fillWidth:true
            LabelText { text:choice.modelData.title; Layout.fillWidth:true; wrapMode:Text.Wrap }
            LiquidComboBox { model:choice.modelData.values; currentIndex:Math.max(0,choice.modelData.values.indexOf(ShellState.preferences[choice.modelData.key])); enabled:root.ready; Accessible.name:choice.modelData.title; onActivated:ShellState.run("setting",{key:choice.modelData.key,value:choice.modelData.values[currentIndex]}) }
        }
    }
    Repeater {
        model:[{key:"wallpaperTransitionBezier",title:"Bezier curve (x1,y1,x2,y2)",hint:".54,0,.34,.99"},{key:"wallpaperTransitionWave",title:"Wave width,height",hint:"20,20"},{key:"wallpaperFillColor",title:"Image padding color",hint:"#000000"}]
        delegate: ColumnLayout {
            id:field; required property var modelData; Layout.fillWidth:true
            LabelText { text:field.modelData.title; font.weight:Font.Bold }
            ExpressiveField { Layout.fillWidth:true; text:ShellState.preferences[field.modelData.key] || field.modelData.hint; maximumLength:80; placeholderText:field.modelData.hint; Accessible.name:field.modelData.title; onEditingFinished:if(root.ready && text!==ShellState.preferences[field.modelData.key]) ShellState.run("setting",{key:field.modelData.key,value:text}) }
        }
    }
    LabelText { text:"Simple ignores duration and uses its step. None and disabled shell animations apply immediately. Bezier values are 0–1; wave values are 1–500. A matching image already on screen has no visible transition."; Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted; font.pixelSize:12 }
}
