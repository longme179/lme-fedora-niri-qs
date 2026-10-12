# Selected shell ports

Each feature has its own commit. Settings are optional and keep the existing Dracula/glass defaults. Sources and licenses are recorded in THIRD_PARTY.md.

## Spring motion

Enable **Appearance → Spring motion**. Open and close the Control Center rapidly, then expand the Island while its content changes. The spring keeps velocity when retargeted, instead of replaying easing. Turning **Animations** off snaps to the final state and releases closed panels.

Validated: native QML retarget/velocity/convergence/reduced-motion regression, qmllint, existing native popup retention and Settings launch checks. GPU/120 Hz performance on the owner's laptop remains unmeasured.
