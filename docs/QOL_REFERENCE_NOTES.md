# QoL reference notes

2026-11-01. Source inspection only; no upstream shell was benchmarked or run.
Pins identify researched snapshots, not recommended dependency versions. The
owner's existing LME roadmap/RAM acceptance remains closed. Feature IDs refer to
[the proposed roadmap](QOL_ROADMAP.md).

## Inspected repositories

| Repository | Pinned commit | Inspected mechanism |
| --- | --- | --- |
| [end4-pC](https://github.com/pctrade/end4-pC) | `8840bd0be8b433af5cdab26944415a09d4858252` | Launcher Settings results, configurable timer |
| [Serpantinum](https://github.com/ilyamiro/serpantinum) | `fc0c3eca9f34dbad735d47f4fcae3700ce49f728` | Niri XKB subscription/cycle |
| [Caelestia](https://github.com/caelestia-dots/shell) | `b51fdb35ca7a14ac5a49e0d94fc5de2d79756aed` | PipeWire output cycling |
| [Noctalia](https://github.com/noctalia-dev/noctalia-shell) | `5d5cda62e972469fea595cbe9a08da4be538fec2` | Desktop actions, XKB, history policy, audio/Bluetooth/capture |
| [DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell) | `d70d35316da1cfb6569af66415b1612fc8089a5d` | App actions, expiry predicate, audio profiles, display/VPN |
| [GNOME Shell](https://github.com/GNOME/gnome-shell) | `9a753aa969709d351632dbefd23333681cc5b3c2` | Saved-file handoff, saved VPN filtering |
| [KDE Plasma audio](https://github.com/KDE/plasma-pa) | `0f0a88f8a89dedca1ee89357f1fe8022fc443645` | Stream labels, destination actions |
| [COSMIC applets](https://github.com/pop-os/cosmic-applets) | `582281f9f76cb22b64bdec89bf979aba744d0b6d` | Notification app-group dismissal |
| [Cinnamon](https://github.com/linuxmint/cinnamon) | `4f0f8ed5442874d7a0cca45c17e5249b05d50caa` | Avoiding competing keyboard indicators |

Noctalia's inspected snapshot is C++ `src/`, not its former QML tree. DMS also
uses Go; GNOME uses native GObject/libnm; Plasma private Pulse models; COSMIC
Rust. Their native APIs do not become available merely because LME also has a
menu. Borrow user flows and domain boundaries, not these runtime stacks.

## R1 — Settings inside Launcher: Q01

end4-pC [LauncherSearch.qml, lines 399–415](https://github.com/pctrade/end4-pC/blob/8840bd0be8b433af5cdab26944415a09d4858252/services/LauncherSearch.qml#L399-L415)
bounds Settings results to eight and activates a page/section reference;
[lines 479–484](https://github.com/pctrade/end4-pC/blob/8840bd0be8b433af5cdab26944415a09d4858252/services/LauncherSearch.qml#L479-L484)
places them after apps. Its [search index, lines 56–87](https://github.com/pctrade/end4-pC/blob/8840bd0be8b433af5cdab26944415a09d4858252/services/SettingsSearchIndex.qml#L56-L87)
matches tokens, but [lines 103–109](https://github.com/pctrade/end4-pC/blob/8840bd0be8b433af5cdab26944415a09d4858252/services/SettingsSearchIndex.qml#L103-L109)
read QML page sources to build metadata. LME should use existing SettingsRegistry
metadata instead: no source scraping, page instantiation or competing index.

## R2 — App secondary actions: Q04

Noctalia [app_provider.cpp, lines 286–312](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/launcher/app_provider.cpp#L286-L312)
bounds action search and [lines 318–337](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/launcher/app_provider.cpp#L318-L337)
re-resolve the action before launch. DMS builds a
[context menu](https://github.com/AvengeMedia/DankMaterialShell/blob/d70d35316da1cfb6569af66415b1612fc8089a5d/quickshell/Modals/DLauncherV2/LauncherContextMenu.qml#L74-L84)
and [dispatches its selected action](https://github.com/AvengeMedia/DankMaterialShell/blob/d70d35316da1cfb6569af66415b1612fc8089a5d/quickshell/Modals/DLauncherV2/LauncherContextMenu.qml#L248-L253).
LME should retain its literal-argv, terminal and launch-history contracts.
The inspected Quickshell reference `4f508be500dea6e5732cc3d50382a0048b17e7b1`
documents [execute() ignoring Terminal/field codes](https://github.com/quickshell-mirror/quickshell/blob/4f508be500dea6e5732cc3d50382a0048b17e7b1/src/core/desktopentry.hpp#L96-L109),
including the DesktopAction overload. Do not blindly call it or raw `execString`.

## R3 — Keyboard layout authority: Q11

Serpantinum [KeyboardLayout.qml, lines 20–45](https://github.com/ilyamiro/serpantinum/blob/fc0c3eca9f34dbad735d47f4fcae3700ce49f728/src/quickshell/singletons/system/KeyboardLayout.qml#L20-L45)
reference-counts subscriptions; [lines 57–80](https://github.com/ilyamiro/serpantinum/blob/fc0c3eca9f34dbad735d47f4fcae3700ce49f728/src/quickshell/singletons/system/KeyboardLayout.qml#L57-L80)
use shared niri state and `switch-layout next`. Noctalia's
[niri backend](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/compositors/niri/niri_keyboard_backend.cpp#L52-L97)
uses KeyboardLayouts/SwitchLayout, filters event names and validates the current
layout index. Cinnamon
[yields indicator authority to Fcitx](https://github.com/linuxmint/cinnamon/blob/4f0f8ed5442874d7a0cca45c17e5249b05d50caa/files/usr/share/cinnamon/applets/keyboard%40cinnamon.org/applet.js#L62-L70).
LME reuses one niri stream; an XKB layout label must not claim to be an IBus/Fcitx
Vietnamese engine switch. Reject Bash/jq fallback or another watcher per module.

## R4 — Notification group/history boundaries: Q08–Q09

COSMIC [groups notifications and replaces matching IDs](https://github.com/pop-os/cosmic-applets/blob/582281f9f76cb22b64bdec89bf979aba744d0b6d/cosmic-applet-notifications/src/lib.rs#L187-L211)
and [clears one selected app group](https://github.com/pop-os/cosmic-applets/blob/582281f9f76cb22b64bdec89bf979aba744d0b6d/cosmic-applet-notifications/src/lib.rs#L252-L269).
Noctalia [separates native close, history retention and unread state](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/notification/notification_manager.cpp#L611-L652).
These are evidence for group-clear/history policy, **not an upstream Undo claim**.
History-only restore is LME's proposed composition. No native action resurrection,
new toasts/unread burst, retained QObjects or additional image textures.

## R5 — Timed app mute: Q10

DMS [NotificationRuleExpiry.js](https://github.com/AvengeMedia/DankMaterialShell/blob/d70d35316da1cfb6569af66415b1612fc8089a5d/quickshell/Common/NotificationRuleExpiry.js#L1-L27)
provides a pure expiry predicate. Borrow that separation, not its additional
60-second sweeper. LME evaluates absolute expiry at admission/open/mutation and
can use its existing visible-center clock; A6 cadence remains unchanged.

## R6 — Capture handoff: Q05

GNOME's [screenshot Show in Files](https://github.com/GNOME/gnome-shell/blob/9a753aa969709d351632dbefd23333681cc5b3c2/js/ui/screenshot.js#L2757-L2777)
and [video equivalent](https://github.com/GNOME/gnome-shell/blob/9a753aa969709d351632dbefd23333681cc5b3c2/js/ui/screenshot.js#L2532-L2551)
exist only after successful save and handle a missing directory handler.
Noctalia [resolves configured/XDG capture destinations](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/capture/screenshot_service.cpp#L2246-L2258).
LME already has a save-folder field; the proposal is successful-export handoff,
not another screenshot editor. Folder-open fallback must not promise file selection.

## R7 — Audio identity and capability: Q03, Q13–Q14

Caelestia [cycles current sinks and sets preferredDefaultAudioSink](https://github.com/caelestia-dots/shell/blob/b51fdb35ca7a14ac5a49e0d94fc5de2d79756aed/services/Audio.qml#L64-L78).
LME adds actual-default read-back and stale-node checks. Plasma
[supports stream drag/mute](https://github.com/KDE/plasma-pa/blob/0f0a88f8a89dedca1ee89357f1fe8022fc443645/applet/ListItemBase.qml#L78-L104),
[destination changes](https://github.com/KDE/plasma-pa/blob/0f0a88f8a89dedca1ee89357f1fe8022fc443645/applet/ListItemBase.qml#L384-L390)
and [useful app/media labels](https://github.com/KDE/plasma-pa/blob/0f0a88f8a89dedca1ee89357f1fe8022fc443645/applet/StreamListItem.qml#L20-L36).
Noctalia's [stream route menu](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/shell/control_center/tabs/audio_tab.cpp#L1553-L1606)
uses a native move/clear-route API. Quickshell's inspected
[link properties are read-only](https://github.com/quickshell-mirror/quickshell/blob/4f508be500dea6e5732cc3d50382a0048b17e7b1/src/services/pipewire/qml.hpp#L355-L413).
Do not invent `wpctl set-target`, equate PW IDs with Pulse indexes or promise
persistent Follow default from a one-shot move. DMS
[ports](https://github.com/AvengeMedia/DankMaterialShell/blob/d70d35316da1cfb6569af66415b1612fc8089a5d/quickshell/Services/AudioService.qml#L287-L315)
and [profile read-back](https://github.com/AvengeMedia/DankMaterialShell/blob/d70d35316da1cfb6569af66415b1612fc8089a5d/quickshell/Services/AudioService.qml#L644-L660)
are useful patterns; their large multi-platform service is not a template to copy.

## R8 — Bluetooth management: Q12

Noctalia offers [Forget for paired devices](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/shell/control_center/tabs/bluetooth_tab.cpp#L249-L261)
and [a trust-backed reconnect setting](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/shell/control_center/tabs/bluetooth_tab.cpp#L279-L297).
Its [serial reconnect pass](https://github.com/noctalia-dev/noctalia-shell/blob/5d5cda62e972469fea595cbe9a08da4be538fec2/src/dbus/bluetooth/bluetooth_service.cpp#L967-L998)
checks current state/generation. LME already connects paired devices. Proposed
Rename/Forget must preserve adapter identity and pending conflicts; no trust
mutation, reconnect sweep or battery-pin data deletion is included. BlueZ Alias
write support still needs a bounded capability check before implementation.

## R9 — Timer customization: Q06

end4-pC [TimerService.qml configuration](https://github.com/pctrade/end4-pC/blob/8840bd0be8b433af5cdab26944415a09d4858252/services/TimerService.qml#L17-L27)
defines configurable focus/break durations and persisted run state;
[deadline-derived countdown](https://github.com/pctrade/end4-pC/blob/8840bd0be8b433af5cdab26944415a09d4858252/services/TimerService.qml#L63-L91)
is the useful boundary. A named preset list is LME's own composition, not verified
upstream functionality. Do not copy its 200 ms timer/10 ms stopwatch cadence;
LME keeps its existing 250 ms active-only ticker and restart-reset contract.

## R10 — Manual display profiles: Q15

DMS [DisplayProfilesWidget](https://github.com/AvengeMedia/DankMaterialShell/blob/d70d35316da1cfb6569af66415b1612fc8089a5d/quickshell/Modules/ControlCenter/BuiltinPlugins/DisplayProfilesWidget.qml#L13-L60)
provides manual profiles/cycling, alongside an autoMode we explicitly exclude.
Its [preview state checks](https://github.com/AvengeMedia/DankMaterialShell/blob/d70d35316da1cfb6569af66415b1612fc8089a5d/quickshell/Modules/Settings/DisplayConfig/DisplayConfigState.qml#L94-L144)
support session/topology validation. LME must reuse its existing DisplayControl
watchdog and Saver admission, without adding another restore path.

## R11 — Saved VPN controls: Q16

GNOME [observes saved/active connections](https://github.com/GNOME/gnome-shell/blob/9a753aa969709d351632dbefd23333681cc5b3c2/js/ui/status/network.js#L1554-L1585)
and [filters VPN/WireGuard rather than slave profiles](https://github.com/GNOME/gnome-shell/blob/9a753aa969709d351632dbefd23333681cc5b3c2/js/ui/status/network.js#L1588-L1601).
DMS's [broader VPN service](https://github.com/AvengeMedia/DankMaterialShell/blob/d70d35316da1cfb6569af66415b1612fc8089a5d/quickshell/Services/VPNService.qml#L35-L109)
also handles plugins/import; those are excluded. Reuse NM/keyring, no credentials
in shell settings, new monitor or automatic connection policy.

## Evidence limits

Q02 combines LME's already-tested move action with keyboard access; Q07 is an
LME clipboard composition proposal. No inspected citation is presented as proof
of an identical upstream implementation. No cross-shell RAM/latency claim,
GPU test, plugin license clearance or runtime compatibility proof is made.
Prefer original implementation; any copied source later needs license review
and attribution under existing third-party policy. Protocol/hardware checks
listed in the feature cards remain future work, not passed tests.
