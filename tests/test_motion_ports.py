"""Native spring physics regression, independent of display frame rate."""
import json, os, subprocess, tempfile, time, unittest
from pathlib import Path

@unittest.skipUnless(os.environ.get('LME_TEST_MOTION_UI') == '1', 'opt-in private Wayland spring checks')
class SpringCase(unittest.TestCase):
    def test_retarget_preserves_velocity_and_reduced_motion_snaps(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            entry=Path(temporary)/'shell.qml'
            (Path(temporary)/'qml').symlink_to(repo/'qml',target_is_directory=True)
            entry.write_text("""//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/components"
import "qml/services"
import "qml/theme"
import "qml/components/shapes/Polygons.js" as Polygons
import "qml/components/shapes/shapes/morph.js" as Morph
ShellRoot {
    id: fixture
    property real nextTarget: 0
    SpringMotion { id: boundSpring; target: fixture.nextTarget; driver.running: false; onTargetChanged: retarget(target) }
    Component.onCompleted: Quickshell.watchFiles = false
    OSDWindow { id: osd; screenInfo: Quickshell.screens[0] }
    SpringMotion { id: spring; driver.running: false }
    MotionValue { id: follow; target: fixture.nextTarget; driver.running: false }
    IpcHandler {
        target: "test"
        function check(): string {
            spring.snapTo(0); spring.retarget(1);
            for (let i=0;i<10;i++) spring.advance(1/120);
            const value=spring.value, velocity=spring.velocity;
            spring.retarget(-1);
            const preserved=spring.value===value && spring.velocity===velocity && velocity>0;
            for (let i=0;i<1800 && spring.running;i++) spring.advance(1/120);
            const converged=spring.value===-1 && spring.velocity===0 && spring.settled;
            spring.retarget(2); spring.advance(1/120); spring.reducedMotion=true;
            const reduced=spring.value===2 && spring.velocity===0 && spring.settled;
            const morph=new Morph.Morph(Polygons.shape("circle"),Polygons.shape("flower"));
            let finite=true;
            for (const progress of [0,.25,.5,.75,1,1.1]) {
                const cubics=morph.asCubics(progress);
                finite=finite && cubics.length>0 && cubics.every(c => [c.anchor0X,c.anchor0Y,c.control0X,c.control0Y,c.control1X,c.control1Y,c.anchor1X,c.anchor1Y].every(Number.isFinite));
            }
            ShellState.snapshot=Object.assign({},ShellState.snapshot,{preferences:{dndUntil:-1,dndWhileSharing:true}});
            PrivacyState.event({CastsChanged:{casts:[{stream_id:4,is_active:true}]}});
            const sharing=Notifications.sharingDnd && Notifications.dnd;
            PrivacyState.event({CastStopped:{stream_id:4}});
            const privacy=sharing && !Notifications.sharingDnd && Notifications.dnd;
            OSDManager.show("Volume",42);
            const first=OSDManager.entries[Quickshell.screens[0].name];
            OSDManager.show("Brightness",86);
            const second=OSDManager.entries[Quickshell.screens[0].name];
            const output=first && second && first.sequence<second.sequence && second.value===86 && osd.open;
            fixture.nextTarget=1;
            for(let i=0;i<10;i++) follow.advance(1/120);
            const followingValue=follow.value, followingVelocity=follow.velocity;
            const began=boundSpring.running;
            for(let i=0;i<1800 && boundSpring.running;i++) boundSpring.advance(1/120);
            fixture.nextTarget=-1;
            const following=follow.value===followingValue && follow.velocity===followingVelocity && followingVelocity>0;
            for(let i=0;i<1800 && follow.running;i++) follow.advance(1/120);
            const followingSettled=follow.value===-1 && !follow.running;
            const bound=began && boundSpring.running && boundSpring.value===1;
            const profileEqual=Theme.settingsEqual({font:{body:"Roboto",bar:"Mono"}},{font:{bar:"Mono",body:"Roboto"}}) && !Theme.settingsEqual({motion:1},{motion:2});
            return JSON.stringify({preserved,converged,reduced,finite,privacy,output,bound,profileEqual,following,followingSettled});
        }
    }
}""")
            with tempfile.TemporaryFile(mode='w+') as log:
                process=subprocess.Popen(['quickshell','-p',str(entry)],stdout=log,stderr=log)
                try:
                    result=None
                    for _ in range(50):
                        reply=subprocess.run(['quickshell','-p',str(entry),'ipc','call','test','check'],capture_output=True,text=True)
                        try: result=json.loads(reply.stdout)
                        except ValueError: time.sleep(.1); continue
                        break
                    log.seek(0)
                    self.assertEqual(result,{'preserved':True,'converged':True,'reduced':True,'finite':True,'privacy':True,'output':True,'bound':True,'profileEqual':True,'following':True,'followingSettled':True},log.read())
                finally: process.terminate();process.wait(timeout=5)
