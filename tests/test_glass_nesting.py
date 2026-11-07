"""Glass-on-glass nesting levels follow tree events only, never frames."""
import shutil
import unittest
import test_local_qml as qml_tests


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class GlassNestingCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_levels_follow_tree_events_not_frames(self):
        result = self.run_qml('import QtTest\nimport "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property int frames: 0
    property int idleBase: 0
    property int framesBase: 0
    property int coalesceBase: 0
    property real pumpBase: 0
    property var checks: ({})
    FloatingWindow {
        id: win
        implicitWidth: 800; implicitHeight: 600
        Item {
            id: host; anchors.fill: parent
            GlassPanel {
                id: panel; anchors.fill: parent; role: "panelFill"
                Item { id: nestProbe }
                Item {
                    id: card; x: 40; y: 40; width: 420; height: 300
                    GlassMaterial { id: cardGlass; anchors.fill: parent; radius: 24 }
                    Item {
                        id: knob; x: 24; y: 24; width: 180; height: 64
                        GlassMaterial { id: knobGlass; anchors.fill: parent; radius: 14 }
                    }
                }
            }
            Item {
                id: overlay; x: 480; y: 60; width: 260; height: 120
                GlassMaterial { id: overlayGlass; anchors.fill: parent; radius: 18 }
            }
            TestCase { id: probe; when: false }
        }
    }
    function toggleProbe() { nestProbe.parent = nestProbe.parent === panel ? host : panel; }
    // Frame evidence, quickshell 0.3.2-proof: count real window frames through the
    // same object GlassMaterial itself connects to (renderWindow = Window.window —
    // the FloatingWindow wrapper exposes no afterAnimating), and keep a property-
    // animation pump as liveness proof even on runtimes without the signal.
    Connections { target: cardGlass.renderWindow; function onAfterAnimating() { fixture.frames++ } }
    QtObject { id: pump; property real value: 0 }
    NumberAnimation { target: card; property: "x"; from: 40; to: 64; duration: 700; loops: Animation.Infinite; running: true }
    NumberAnimation { target: pump; property: "value"; from: 0; to: 100; duration: 100000; loops: 1; running: true }
    Timer {
        interval: 60; running: true; repeat: true
        onTriggered: {
            if (++fixture.ticks > 220) { fixture.finish({timeout: fixture.phase, checks: fixture.checks}); return; }
            if (fixture.phase === 0) {
                if ((fixture.frames >= 5 || pump.value >= .5) && cardGlass.nestLevel === 1 && knobGlass.nestLevel === 2 && overlayGlass.nestLevel === 1) {
                    fixture.checks.levels = true;
                    fixture.checks.nest = Math.abs(cardGlass.nest - .5) < 1e-9 && knobGlass.nest === 1;
                    fixture.idleBase = cardGlass.nestWalks;
                    fixture.framesBase = fixture.frames;
                    fixture.pumpBase = pump.value;
                    fixture.phase = 1;
                }
            } else if (fixture.phase === 1) {
                if (fixture.frames >= fixture.framesBase + 5 || pump.value >= fixture.pumpBase + .5) {
                    fixture.checks.idleNoWalks = cardGlass.nestWalks === fixture.idleBase;
                    fixture.checks.framesPumped = fixture.frames >= fixture.framesBase + 5 || pump.value >= fixture.pumpBase + .5;
                    fixture.coalesceBase = cardGlass.nestWalks;
                    fixture.phase = 2;
                }
            } else if (fixture.phase === 2) {
                Qt.createQmlObject('import QtQuick; Item { objectName: "nestA" }', panel, "probe");
                Qt.createQmlObject('import QtQuick; Item { objectName: "nestB" }', panel, "probe");
                fixture.phase = 3;
            } else if (fixture.phase === 3) {
                fixture.checks.coalesced = cardGlass.nestWalks === fixture.coalesceBase + 1 && cardGlass.nestLevel === 1;
                card.parent = win.contentItem;
                fixture.phase = 4;
            } else if (fixture.phase === 4) {
                fixture.checks.reparentOut = cardGlass.nestLevel === 0 && knobGlass.nestLevel === 1;
                card.parent = panel;
                fixture.phase = 5;
            } else if (fixture.phase === 5) {
                fixture.checks.reparentIn = cardGlass.nestLevel === 1 && knobGlass.nestLevel === 2;
                probe.findChild(panel, "glassMaterial").allowed = false;
                toggleProbe();
                fixture.phase = 6;
            } else if (fixture.phase === 6) {
                fixture.checks.gateChrome = cardGlass.nestLevel === 0 && knobGlass.nestLevel === 1 && overlayGlass.nestLevel === 1;
                probe.findChild(panel, "glassMaterial").allowed = true;
                toggleProbe();
                fixture.phase = 7;
            } else if (fixture.phase === 7) {
                fixture.checks.gateRestore = cardGlass.nestLevel === 1 && knobGlass.nestLevel === 2;
                panel.allowed = false;
                toggleProbe();
                fixture.phase = 8;
            } else if (fixture.phase === 8) {
                fixture.checks.gatePanel = overlayGlass.nestLevel === 0 && cardGlass.nestLevel === 1;
                panel.allowed = true;
                toggleProbe();
                fixture.phase = 9;
            } else if (fixture.phase === 9) {
                fixture.checks.gatePanelRestore = overlayGlass.nestLevel === 1;
                fixture.finish(fixture.checks);
            }
        }
    }
''')
        self.assertEqual(result, dict(levels=True, nest=True, framesPumped=True, idleNoWalks=True,
            coalesced=True, reparentOut=True, reparentIn=True, gateChrome=True, gateRestore=True,
            gatePanel=True, gatePanelRestore=True))
