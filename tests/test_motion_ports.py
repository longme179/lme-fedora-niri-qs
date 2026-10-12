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
import "qml/components/shapes/Polygons.js" as Polygons
import "qml/components/shapes/shapes/morph.js" as Morph
ShellRoot {
    Component.onCompleted: Quickshell.watchFiles = false
    SpringMotion { id: spring; driver.running: false }
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
            return JSON.stringify({preserved,converged,reduced,finite});
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
                    self.assertEqual(result,{'preserved':True,'converged':True,'reduced':True,'finite':True},log.read())
                finally: process.terminate();process.wait(timeout=5)
