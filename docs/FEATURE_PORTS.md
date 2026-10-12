# Selected shell ports

Each feature has its own commit. Settings are optional and keep the existing Dracula/glass defaults. Sources and licenses are recorded in THIRD_PARTY.md.

## Spring motion

Enable **Appearance → Spring motion**. Open and close the Control Center rapidly, then expand the Island while its content changes. The spring keeps velocity when retargeted, instead of replaying easing. Turning **Animations** off snaps to the final state and releases closed panels.

Validated: native QML retarget/velocity/convergence/reduced-motion regression, qmllint, existing native popup retention and Settings launch checks. GPU/120 Hz performance on the owner's laptop remains unmeasured.

## Geometric morph

Enable **Appearance → Geometric shape morph**, then hover/press a gear or another icon button. Its silhouette interpolates rounded polygon cubic paths. Animations off keeps a static circle. Source math is Apache-2.0, adapted Canvas retains iNiR GPL/NOTICE credits. Paint work is limited to interaction, resize and color changes; laptop CPU/GPU cost remains unmeasured.

## Moving tab indicator

**Appearance → Moving tab indicator** controls stretching selection in Control Center tabs and the Settings sidebar. Try mouse selection, Ctrl+Tab in Control Center, and filtered Settings navigation; reduced motion snaps. It adapts DMS independent leading/trailing edges to LME grid and vertical layouts.
