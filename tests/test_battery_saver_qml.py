"""Battery saver applies a temporary visual policy without changing customization."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import test_local_qml as qml_tests


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is required')
class BatterySaverVisualCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_spectrum_resumes_after_fast_saver_reversals_without_spurious_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'cava'
            binary.write_text('''#!/usr/bin/python3
import signal, sys, time
def stop(*_):
    time.sleep(.08)
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
while True:
    print(';'.join(['75'] * 16) + ';', flush=True)
    time.sleep(.016)
''')
            binary.chmod(0o755)
            result = self.run_qml('import "qml/components"\nimport "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property int rounds: 0
    property int settleTicks: 0
    property var failures: []
    FloatingWindow {
        implicitWidth: 500; implicitHeight: 160
        AudioVisualizer { id: spectrum; width: 450; height: 40; playing: true }
    }
    Connections {
        target: VisualizerState
        function onFailedChanged() { if (VisualizerState.failed) fixture.failures.push(VisualizerState.error); }
    }
    function policy(active) {
        ShellState.snapshot = Object.assign({}, ShellState.snapshot, {batterySaver: {active},
            preferences: Object.assign({}, ShellState.preferences, {audioVisualizer: true})});
    }
    Timer { interval: 15; running: true; repeat: true; onTriggered: {
        if (++fixture.ticks > 600) { fixture.finish({timeout: fixture.phase, rounds: fixture.rounds, failures: fixture.failures,
            refs: VisualizerState.refs, wanted: VisualizerState.wanted, stopping: VisualizerState.stopping,
            spectrumWanted: spectrum.wanted, subscribed: spectrum.subscribed, bars: VisualizerState.bars}); return; }
        if (fixture.phase === 0 && ShellState.backendReady) {
            ShellState.run("setting", {key: "audioVisualizer", value: true}); fixture.phase++;
        }
        else if (fixture.phase === 1 && VisualizerState.bars[0] > .5) { fixture.policy(true); fixture.phase++; }
        else if (fixture.phase === 2) { fixture.policy(false); fixture.phase++; }
        else if (fixture.phase === 3 && !VisualizerState.stopping && VisualizerState.bars[0] > .5) {
            if (++fixture.rounds === 20) fixture.phase++;
            else { fixture.policy(true); fixture.phase = 2; }
        } else if (fixture.phase === 4 && ++fixture.settleTicks > 15) {
            fixture.finish({rounds: fixture.rounds, healthy: !VisualizerState.failed && !VisualizerState.error
                && !VisualizerState.stopping && VisualizerState.bars[0] > .5 && VisualizerState.refs === 1,
                failures: fixture.failures});
        }
    } }
''', {'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1',
      'PATH': directory + os.pathsep + os.environ.get('PATH', '')})
        self.assertEqual(result, dict(rounds=20, healthy=True, failures=[]))

    def test_blur_regions_are_disabled_in_both_styles_and_restore_saved_flags(self):
        result = self.run_qml('import "qml/services"', '''
    Timer { interval: 80; running: true; repeat: true; onTriggered: {
        if (!ShellState.backendReady) return;
        const saved = Object.assign({}, ShellState.preferences, {popupBlur: true, barBlur: true});
        function apply(style, active) {
            ShellState.snapshot = Object.assign({}, ShellState.snapshot, {platform: {popupBlurSupported: true},
                preferences: Object.assign({}, saved, {surfaceStyle: style}), batterySaver: {active}});
            return [ShellState.popupBlurEnabled, ShellState.liquidBlurEnabled, ShellState.barBlurEnabled];
        }
        fixture.finish({smoked: apply("smoked", false), smokedSaver: apply("smoked", true),
            liquidSaver: apply("liquid", true), liquid: apply("liquid", false), restored: apply("smoked", false)});
    } }
''', {'LME_SHELL_DEMO': '0', 'LME_SHELL_BACKEND_DEMO': '1'})
        self.assertEqual(result, dict(smoked=[True, False, True], smokedSaver=[False] * 3,
                                     liquidSaver=[False] * 3, liquid=[False, True, True],
                                     restored=[True, False, True]))

    def test_visual_policy_is_opaque_stops_motion_and_restores_saved_preferences(self):
        result = self.run_qml('import "qml/bar"\nimport "qml/components"\nimport "qml/services"\nimport "qml/theme"', '''
    property int phase: 0
    property var saved: null
    property string before: ""
    property var checks: ({})
    FloatingWindow {
        implicitWidth: 700; implicitHeight: 650
        GlassPanel { id: panel; width: 400; height: 120 }
        BarSurface { id: bar; y: 140; width: 400; height: 42; zone: "left" }
        NotificationCard { id: notification; y: 200; width: 400; entry: ({appName: "Test", summary: "Message", body: "Body", actions: []}) }
        MediaAmbient { id: ambient; y: 350; width: 400; height: 140; playing: true }
        AudioVisualizer { id: spectrum; y: 510; width: 400; playing: true }
    }
    function policy(active) {
        ShellState.snapshot = Object.assign({}, ShellState.snapshot,
            {preferences: fixture.saved, batterySaver: {active}, platform: {popupBlurSupported: true}});
    }
    Timer {
        interval: 80; running: true; repeat: true
        onTriggered: {
            if (fixture.phase === 0) {
                if (!ShellState.backendReady) return;
                ShellState.backend.running = false;
                fixture.saved = Object.assign({}, ShellState.preferences, {
                    surfaceStyle: "liquid", animations: true, opacity: .81, notificationOpacity: .62,
                    barBlur: true, popupBlur: true, audioVisualizer: true, mediaShapes: true,
                    themeOverrides: {panelFill: "#40234567", cardFill: "#30234567", barFill: "#50234567", text: "#90ffeedd"},
                    barIslandStyles: {left: {fillColor: "#20224466"}}
                });
                fixture.before = JSON.stringify(fixture.saved);
                fixture.policy(false); fixture.phase++;
            } else if (fixture.phase === 1) {
                fixture.checks.before = Theme.liquidGlass && Theme.animations && ambient.animating
                    && spectrum.spectrumEnabled && panel.color.a < 1;
                fixture.policy(true); fixture.phase++;
            } else if (fixture.phase === 2) {
                fixture.checks.saver = ShellState.batterySaverActive && !Theme.liquidGlass && !Theme.animations
                    && Theme.panelOpacity === 1 && Theme.notificationOpacity === 1;
                fixture.checks.opaque = panel.color.a === 1 && bar.color.a === 1 && notification.color.a === 1
                    && Theme.cardFill.a === 1;
                fixture.checks.noBlur = !ShellState.popupBlurEnabled && !ShellState.liquidBlurEnabled && !ShellState.barBlurEnabled;
                fixture.checks.noFrames = !ambient.animating && !spectrum.spectrumEnabled && !spectrum.wanted && spectrum.implicitHeight === 0;
                fixture.checks.rawPreserved = JSON.stringify(ShellState.preferences) === fixture.before && Theme.text.a < 1;
                fixture.policy(false); fixture.phase++;
            } else {
                fixture.checks.restored = Theme.liquidGlass && Theme.animations && ambient.animating
                    && spectrum.spectrumEnabled && Theme.panelOpacity === .65 && Theme.notificationOpacity === .65
                    && JSON.stringify(ShellState.preferences) === fixture.before;
                fixture.finish(fixture.checks);
            }
        }
    }
''')
        self.assertEqual(result, dict(before=True, saver=True, opaque=True, noBlur=True,
                                     noFrames=True, rawPreserved=True, restored=True))

    @unittest.skipUnless(os.environ.get('LME_TEST_UPGRADE_UI') == '1', 'requires private Wayland')
    def test_canvas_tile_settings_switch_and_brightness_round_trip(self):
        result = self.run_qml('import QtTest\nimport QtQuick.Controls\nimport QtQuick.Layouts\nimport "qml/panels"\nimport "qml/settings"\nimport "qml/services"\nimport "qml/theme"', '''
    property int phase: 0
    property int ticks: 0
    property bool showSettings: false
    property var checks: ({})
    DesktopAmbient { id: desktop }
    FloatingWindow {
        implicitWidth: 920; implicitHeight: 1050
        StackLayout {
            anchors.fill: parent; currentIndex: fixture.showSettings ? 1 : 0
            ControlDashboard { id: dashboard }
            ScrollView {
                id: settingsScroll; contentWidth: availableWidth
                BehaviorPage { id: page; width: settingsScroll.availableWidth }
            }
        }
        TestCase { id: pointer; when: false }
    }
    function findScroll(item) {
        if (item.contentY !== undefined) return item;
        for (const child of item.children || []) { const found = findScroll(child); if (found) return found; }
        return null;
    }
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            if (++fixture.ticks > 110) { fixture.finish({timeout: fixture.phase, checks: fixture.checks, state: ShellState.snapshot.batterySaver, result: ShellState.lastResult}); return; }
            if (!ShellState.backendReady || ShellState.pendingActions.setting || ShellState.pendingActions.batterySaver) return;
            const tile = pointer.findChild(dashboard, "batterySaverTile");
            const toggle = pointer.findChild(page, "batterySaverSwitch");
            if (fixture.phase === 0) {
                ShellState.run("setting", {key: "desktopShapes", value: true}); fixture.phase++;
            } else if (fixture.phase === 1 && desktop.instances.length === Quickshell.screens.length) {
                fixture.checks.desktopBefore = desktop.instances.length > 0;
                ShellState.run("setting", {key: "surfaceStyle", value: "liquid"}); fixture.phase++;
            } else if (fixture.phase === 2 && Theme.liquidGlass && tile) {
                fixture.checks.tile = tile.width > 0 && !tile.active && tile.enabled;
                const scroll = fixture.findScroll(dashboard);
                const point = tile.mapToItem(scroll.contentItem, 0, 0);
                scroll.contentY = Math.max(0, Math.min(scroll.contentHeight - scroll.height, point.y - 24));
                fixture.phase++;
                pointer.mouseClick(tile, tile.width / 2, tile.height / 2);
            } else if (fixture.phase === 3 && ShellState.batterySaverActive) {
                fixture.checks.active = tile.active && !Theme.liquidGlass && !Theme.animations && Theme.panelOpacity === 1
                    && ShellState.preferences.surfaceStyle === "liquid" && ShellState.preferences.animations;
                fixture.checks.desktopReleased = desktop.instances.length === 0 && ShellState.preferences.desktopShapes;
                fixture.showSettings = true; fixture.phase++;
            } else if (fixture.phase === 4 && toggle.checked && toggle.enabled) {
                fixture.checks.switch = true;
                const slider = pointer.findChild(page, "batterySaverBrightness");
                fixture.phase++;
                pointer.mouseClick(slider, slider.width * .83, slider.height / 2);
            } else if (fixture.phase === 5 && ShellState.preferences.batterySaverBrightness !== 70) {
                fixture.checks.brightness = ShellState.batterySaverActive && ShellState.preferences.batterySaverBrightness > 75
                    && ShellState.preferences.batterySaverBrightness < 90;
                fixture.phase++;
                pointer.mouseClick(toggle, toggle.width / 2, toggle.height / 2);
            } else if (fixture.phase === 6 && !ShellState.batterySaverActive) {
                fixture.checks.restored = !toggle.checked && Theme.liquidGlass && Theme.animations
                    && ShellState.preferences.surfaceStyle === "liquid";
                fixture.checks.desktopRestored = desktop.instances.length === Quickshell.screens.length;
                fixture.showSettings = false; fixture.phase++;
            } else if (fixture.phase === 7 && tile.enabled) {
                fixture.checks.reopened = !tile.active;
                fixture.finish(fixture.checks);
            }
        }
    }
''', {'QT_QPA_PLATFORM': 'wayland'})
        self.assertEqual(result, dict(desktopBefore=True, tile=True, active=True, desktopReleased=True,
                                     switch=True, brightness=True, restored=True, desktopRestored=True, reopened=True))
