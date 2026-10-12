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
            return JSON.stringify({preserved,converged,reduced});
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
                    self.assertEqual(result,{'preserved':True,'converged':True,'reduced':True},log.read())
                finally: process.terminate();process.wait(timeout=5)
