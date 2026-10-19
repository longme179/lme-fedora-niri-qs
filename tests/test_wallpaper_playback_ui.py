"""Settings edits the real playlist model without launching wallpaper commands in preview."""
import os
import unittest
import test_local_qml as qml_tests


@unittest.skipUnless(os.environ.get('LME_TEST_PERSONALIZATION_UI')=='1','private wallpaper Settings checks')
class WallpaperSettingsCase(unittest.TestCase):
    run_qml=qml_tests.LocalQmlCase.run_qml

    def test_rim_texture_follows_its_output_without_replacing_the_shared_image(self):
        result=self.run_qml('import "qml/components"\nimport "qml/services"','''
    property int phase:0
    property int ticks:0
    property var original:null
    FloatingWindow { id:window;implicitWidth:600;implicitHeight:400;GlassPanel { anchors.fill:parent } }
    Timer { interval:40;repeat:true;running:true;onTriggered: {
        if(++fixture.ticks>180) { fixture.finish({timeout:fixture.phase});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting || ShellState.pendingActions.wallpaper) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"surfaceStyle",value:"liquid"});fixture.phase++; }
        else if(fixture.phase===1 && GlassState.backdrops.length) {
            fixture.original=GlassState.backdrops[0];
            ShellState.run("wallpaper",{path:Quickshell.shellPath("assets/wallpapers/liquid-dracula.png"),output:window.screen.name});fixture.phase++;
        } else if(fixture.phase===2 && ShellState.preferences.wallpaperOutputs[window.screen.name]) {
            if(fixture.original.wallpaperPath!==ShellState.preferences.wallpaperOutputs[window.screen.name]) { fixture.finish({wrongSource:true});return; }
            ShellState.run("setting",{key:"wallpaperOutputs",value:{}});fixture.phase++;
        } else if(fixture.phase===3 && !Object.keys(ShellState.preferences.wallpaperOutputs).length) {
            fixture.finish({shared:ShellState.preferences.wallpaper==="",sameTexture:GlassState.backdrops[0]===fixture.original,
                restored:fixture.original.wallpaperPath===""});
        }
    }}
''',{'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
        self.assertEqual(result,dict(shared=True,sameTexture=True,restored=True))

    def test_add_reorder_remove_interval_and_pause_use_saved_preferences(self):
        result=self.run_qml('import QtTest\nimport "qml/settings"\nimport "qml/services"','''
    property int phase:0
    property int ticks:0
    property var checks:({})
    FloatingWindow { fullscreen:true
        WallpaperPlaylistSettings { id:card;width:650;x:100;y:20;selectedPath:"/pictures/one.png";entries:[{path:"/pictures/two.png"}] }
        TestCase { id:mouse;when:false }
    }
    Timer { interval:50;repeat:true;running:true;onTriggered: {
        if(++fixture.ticks>180) { fixture.finish({timeout:fixture.phase,checks:fixture.checks});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        const p=ShellState.preferences;
        if(fixture.phase===0) { mouse.mouseClick(mouse.findChild(card,"wallpaperPlaylistAdd"));fixture.phase++; }
        else if(fixture.phase===1 && p.wallpaperPlaylist.length===1) {
            fixture.checks.add=p.wallpaperPlaylist[0]==="/pictures/one.png";
            card.save([...p.wallpaperPlaylist,"/pictures/two.png"]);fixture.phase++;
        } else if(fixture.phase===2 && p.wallpaperPlaylist.length===2) { card.move(1,-1);fixture.phase++; }
        else if(fixture.phase===3 && p.wallpaperPlaylist[0]==="/pictures/two.png") {
            fixture.checks.reordered=true;card.save([p.wallpaperPlaylist[1]]);fixture.phase++;
        } else if(fixture.phase===4 && p.wallpaperPlaylist.length===1) {
            fixture.checks.removed=p.wallpaperPlaylist[0]==="/pictures/one.png";
            const field=mouse.findChild(card,"wallpaperPlaylistInterval");field.text="45";field.accepted();fixture.phase++;
        } else if(fixture.phase===5 && p.wallpaperPlaylistInterval===45) {
            fixture.checks.interval=true;ShellState.run("setting",{key:"wallpaperPlaylistEnabled",value:true});fixture.phase++;
        } else if(fixture.phase===6 && p.wallpaperPlaylistEnabled) { mouse.mouseClick(mouse.findChild(card,"wallpaperPlaylistPause"));fixture.phase++; }
        else if(fixture.phase===7 && p.wallpaperPlaylistPaused) {
            fixture.checks.pause=true;mouse.mouseClick(mouse.findChild(card,"wallpaperPlaylistPause"));fixture.phase++;
        } else if(fixture.phase===8 && !p.wallpaperPlaylistPaused) {
            fixture.checks.resume=true;fixture.finish(fixture.checks);
        }
    }}
''',{'QT_QPA_PLATFORM':'wayland'})
        self.assertEqual(result,dict(add=True,reordered=True,removed=True,interval=True,pause=True,resume=True))

    def test_display_target_transition_duration_and_preview_render(self):
        result=self.run_qml('import QtTest\nimport "qml/settings"\nimport "qml/services"','''
    property int phase:0
    property int ticks:0
    property var checks:({})
    FloatingWindow { implicitWidth:1000;implicitHeight:900
        Flickable { anchors.fill:parent;contentHeight:page.implicitHeight
            WallpaperPage { id:page;width:parent.width }
        }
        TestCase { id:mouse;when:false }
    }
    Timer { interval:60;repeat:true;running:true;onTriggered: {
        if(++fixture.ticks>180) { fixture.finish({timeout:fixture.phase,checks:fixture.checks});return; }
        if(!ShellState.backendReady || ShellState.pendingActions.setting) return;
        if(fixture.phase===0) { ShellState.run("setting",{key:"wallpaperOutputs",value:{"DP-3":"/pictures/display.png"}});fixture.phase++; }
        else if(fixture.phase===1 && page.outputs.includes("DP-3")) {
            const target=mouse.findChild(page,"wallpaperOutput");target.currentIndex=page.outputs.indexOf("DP-3");target.activated(target.currentIndex);fixture.phase++;
        } else if(fixture.phase===2 && page.targetOutput==="DP-3") {
            fixture.checks.target=page.currentWallpaper==="/pictures/display.png";
            const transition=mouse.findChild(page,"wallpaperTransition");transition.currentIndex=page.transitions.indexOf("wave");transition.activated(transition.currentIndex);fixture.phase++;
        } else if(fixture.phase===3 && ShellState.preferences.wallpaperTransition==="wave") {
            fixture.checks.transition=true;const slider=mouse.findChild(page,"wallpaperDuration");slider.value=1.7;slider.moved();fixture.phase++;
        } else if(fixture.phase===4 && Math.abs(ShellState.preferences.wallpaperTransitionDuration-1.7)<.01) {
            fixture.checks.duration=true;ShellState.run("wallpaperResetOutput",{output:"DP-3"});fixture.phase++;
        } else if(fixture.phase===5 && !(ShellState.preferences.wallpaperOutputs || {})["DP-3"]) {
            fixture.checks.reset=true;fixture.finish(fixture.checks);
        }
    }}
''',{'QT_QPA_PLATFORM':'wayland','QT_QUICK_BACKEND':'rhi','QSG_RHI_BACKEND':'opengl'})
        self.assertEqual(result,dict(target=True,transition=True,duration=True,reset=True))
