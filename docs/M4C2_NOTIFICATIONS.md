# Notifications withdrawal (deferred in M4c-2)
This contract is recorded, not implemented or verified as withdrawal on this branch.
- Enabled behavior retains server flags, history, mute/DND, annotation and suppression.
- Withdrawn means no NotificationServer is started in the main shell.
- The Settings page, bar entry, popup, center tab and toasts are unavailable.
- Local notification producers cannot schedule history persistence while withdrawn.
- Existing history and settings bytes remain untouched; schema/IDs remain valid.
- Shared action-error/status UI remains usable independently of NotificationServer.
- Future coverage must use a copied checkout/private bus, including re-enable and annotation.
- Deferred: the catalog cannot encode the existing center tab legacyIndex=4; projection assigns new indices after the legacy maximum. Resolving that while retaining all numeric facades requires a separately scoped compatibility design.
