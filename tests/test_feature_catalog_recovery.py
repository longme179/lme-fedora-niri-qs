"""Catalog failures recover on a clean backend verdict; feature availability is independent."""
import shutil
import unittest

import test_local_qml as qml_tests


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class CatalogRecoveryCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_clean_backend_verdict_retries_a_latched_catalog_failure(self):
        result = self.run_qml('import "qml/services"', '''
    property int phase: 0
    Timer {
        interval: 50; repeat: true; running: true
        onTriggered: {
            if (phase === 0 && FeatureCatalog.ready) {
                FeatureCatalog.retryDelayMs = 0;
                FeatureCatalog.fail("fixture failure");
                phase = FeatureCatalog.error ? 1 : 3;
            } else if (phase === 1 && FeatureCatalog.ready && !FeatureCatalog.error) {
                phase = 2;
                fixture.finish({recovered: true, error: FeatureCatalog.error, bars: FeatureCatalog.data.bar.length});
            } else if (phase === 3) {
                fixture.finish({recovered: false, error: FeatureCatalog.error});
            }
        }
    }
    Timer { interval: 8000; running: true; onTriggered: fixture.finish({recovered: false, phase: phase, error: FeatureCatalog.error}) }
''')
        self.assertTrue(result["recovered"], result)
        self.assertEqual(result["error"], "")
        self.assertGreater(result["bars"], 0)

    def test_notification_availability_survives_catalog_publication_failure(self):
        result = self.run_qml('import "qml/services"', '''
    property int phase: 0
    Timer {
        interval: 50; repeat: true; running: true
        onTriggered: {
            if (phase === 0 && FeatureCatalog.ready) {
                ShellState.accept(JSON.stringify(ShellState.snapshot));
                FeatureCatalog.retryDelayMs = 60000;
                FeatureCatalog.fail("availability failure");
                phase = 1;
            } else if (phase === 1 && ShellState.backendReady) {
                fixture.finish({enabled: Notifications.enabled,
                    page: ShellState.settingsPageAvailable("notifications"),
                    feature: FeatureCatalog.featureEnabled("notifications"),
                    error: FeatureCatalog.error});
            }
        }
    }
    Timer { interval: 8000; running: true; onTriggered: fixture.finish({enabled: Notifications.enabled, phase: phase}) }
''')
        self.assertTrue(result["feature"], result)
        self.assertFalse(result["page"], result)
        self.assertTrue(result["enabled"], result)
