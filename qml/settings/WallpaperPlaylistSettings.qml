pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

SettingsCard {
    id: root
    property string selectedPath: ""
    property var entries: []
    readonly property var playlist: ShellState.preferences.wallpaperPlaylist || []
    readonly property bool busy: !!ShellState.pendingActions.setting || !!ShellState.pendingActions.wallpaperNext || !!ShellState.pendingActions.wallpaper
    title: "Wallpaper playlist"
    description: "Play images in order or shuffle, using the display target above. Missing images are skipped. The main shell runs the timer; closing Settings keeps playback going."
    function save(paths) { ShellState.run("setting", {key:"wallpaperPlaylist", value:paths}); }
    function move(index, delta) {
        const paths=playlist.slice(), next=index+delta;
        if(next<0 || next>=paths.length) return;
        [paths[index],paths[next]]=[paths[next],paths[index]]; save(paths);
    }
    PreferenceSwitch { title: "Enable playlist"; detail: "Disabled until you choose images and turn it on"; preference:"wallpaperPlaylistEnabled" }
    PreferenceSwitch { title: "Shuffle"; detail: "Avoid repeating the current image when alternatives exist"; preference:"wallpaperPlaylistShuffle" }
    RowLayout {
        Layout.fillWidth:true
        LabelText { text:"Interval (seconds)"; Layout.fillWidth:true }
        ExpressiveField {
            id:interval; objectName:"wallpaperPlaylistInterval"; Layout.preferredWidth:110
            text:String(ShellState.preferences.wallpaperPlaylistInterval || 300)
            validator:IntValidator { bottom:30; top:86400 }
            Accessible.name:"Playlist interval in seconds"
            onAccepted:if(acceptableInput && !root.busy) ShellState.run("setting",{key:"wallpaperPlaylistInterval",value:Number(text)})
        }
        LiquidButton { text:"Save"; enabled:interval.acceptableInput && !root.busy; onClicked:ShellState.run("setting",{key:"wallpaperPlaylistInterval",value:Number(interval.text)}) }
    }
    RowLayout {
        Layout.fillWidth:true
        LiquidButton {
            objectName:"wallpaperPlaylistPause"
            text:ShellState.preferences.wallpaperPlaylistPaused ? "Resume" : "Pause"
            enabled:ShellState.preferences.wallpaperPlaylistEnabled === true && !root.busy
            onClicked:ShellState.run("setting",{key:"wallpaperPlaylistPaused",value:!ShellState.preferences.wallpaperPlaylistPaused})
        }
        LiquidButton { objectName:"wallpaperPlaylistNext"; text:"Next image"; enabled:root.playlist.length>0 && !root.busy; onClicked:ShellState.run("wallpaperNext",{output:ShellState.preferences.wallpaperPlaylistOutput || ""}) }
        LabelText { text:root.playlist.length+" images"; color:Theme.muted; Layout.fillWidth:true; horizontalAlignment:Text.AlignRight }
    }
    Flow {
        Layout.fillWidth:true; spacing:8
        LiquidButton { objectName:"wallpaperPlaylistAdd"; text:"Add selected image"; enabled:!!root.selectedPath && !root.playlist.includes(root.selectedPath) && root.playlist.length<500 && !root.busy; onClicked:root.save([...root.playlist,root.selectedPath]) }
        LiquidButton { text:"Add shown images"; enabled:root.entries.length>0 && root.playlist.length<500 && !root.busy; onClicked:root.save([...new Set([...root.playlist,...root.entries.map(e=>e.path)])].slice(0,500)) }
    }
    LabelText { visible:!root.playlist.length; text:"Choose images in the library, then add them here. Up to 500 images; 30 seconds to 24 hours between changes."; color:Theme.muted; Layout.fillWidth:true; wrapMode:Text.Wrap }
    ListView {
        id:list; objectName:"wallpaperPlaylistItems"
        Layout.fillWidth:true; Layout.preferredHeight:Math.min(300,root.playlist.length*52)
        model:root.playlist; clip:true; spacing:4; boundsBehavior:Flickable.StopAtBounds
        ScrollBar.vertical:ScrollBar {}
        delegate:RowLayout {
            id:entry; required property string modelData; required property int index
            width:list.width-14; height:48; spacing:6
            LabelText { text:entry.modelData.split("/").pop(); Layout.fillWidth:true; elide:Text.ElideMiddle; Accessible.name:entry.modelData }
            IconButton { glyph:"↑"; tooltip:"Move image up"; enabled:entry.index>0 && !root.busy; onClicked:root.move(entry.index,-1) }
            IconButton { glyph:"↓"; tooltip:"Move image down"; enabled:entry.index<root.playlist.length-1 && !root.busy; onClicked:root.move(entry.index,1) }
            IconButton { glyph:"×"; tooltip:"Remove image from playlist"; enabled:!root.busy; onClicked:root.save(root.playlist.filter(p=>p!==entry.modelData)) }
        }
    }
}
