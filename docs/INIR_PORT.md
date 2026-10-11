# iNiR references and Material glass

Reference: [snowarch/iNiR](https://github.com/snowarch/iNiR), commit
`48cdcecb0f6089cfbb7019054602eab28e154b3b`, inspected on 2026-10-10.
This project implements the relevant patterns with original QML and a Fedora
backend; it does not vendor the upstream dependency graph or Arch scripts.

| iNiR pattern inspected | LME implementation |
| --- | --- |
| Independent `settings.qml` and shared settings page registry | Separate Settings window, shared `SettingsView`, searchable page metadata, Ctrl+F, Enter to open a search result, Alt+Left history, Escape to close |
| Configurable bar groups and widget layout | 15 whitelisted modules; Left, Center and Right zones; add/remove, drag/drop, arrow ordering and position menus; live JSON preferences |
| Material bar and appearance controls | Tonal color roles derived from the existing Dracula palette, flat translucent surfaces, rounded selection containers, expressive switch/slider handles and pressed shape changes |
| Capsule bar groups | Connected glass pill by default, optional three islands, unchanged 42 px height and 8 px top margin |

## Settings scope

Appearance changes accent, opacity and motion. Top bar configures modules,
shape and text size. Wallpaper selects a local image through Qt's file dialog.
Weather controls automatic location, city search and temperature units.
Clipboard controls capture, images and retention; Top bar also enables Activity.
Behavior sets the default terminal. About links to the project and credits.
The app opens without the shell and uses a preference/wallpaper backend with explicit location lookup actions.
It does not scan installed apps or own notifications. Display Settings reads
niri output information only when its page or a display preview is active.

Both clients reload preferences and serialize atomic writes with a shared file
lock. Updating an accent in Settings preserves the shell's saved tasks. Public
settings demo uses a different QML entry point from the real app; changes stay
in memory and wallpaper/system commands remain disabled.

## Visual rules

- Roboto: 14 px body, 12–13 px supporting text, bold 18 px card headings and
  32 px page headings. The bar uses one shared Medium weight and 13 px by default.
- Color roles keep the user's palette: primary/secondary/tertiary containers,
  two surface-container levels and a subdued outline. The roles are deliberate
  blends, rather than Google's HCT/dynamic wallpaper-color implementation.
- The glass layer remains translucent. Cards use flat tonal fills; bar and panel
  surfaces contain no gradient definitions. The wallpaper itself is independent.
- Large rounded cards group related controls. Selected tiles change shape;
  buttons shorten their corner radius when pressed. Sliders use a thick track
  and a vertical handle; switches use a pill track with a changing thumb size.
- Existing OutExpo slides remain, and disabling motion removes shape/color
  transition durations. No extra fullscreen shader or mandatory blur is added.
  Stock niri background blur is not assumed.

## Other candidates

Dynamic wallpaper colors,
per-application audio shortcuts and more settings pages are suitable follow-up
features. iNiR's AI integrations, lock screen, shader effects and complete theme
engine are outside this change. Copying those wholesale would introduce unrelated
services and require separate Fedora integration and hardware validation.

The existing niri overview, workspace drag/drop, notifications, Bluetooth
controls, audio mixer and agenda remain available. Upstream and dependency
licensing is documented in [THIRD_PARTY.md](../THIRD_PARTY.md).

Clipboard and the Activity island are now implemented; see [CLIPBOARD_ACTIVITY.md](CLIPBOARD_ACTIVITY.md).

The wallpaper browser, appearance profiles, modular controls and related desktop
features are now implemented; see [Desktop upgrades](DESKTOP_UPGRADES.md). Display
Settings reads niri outputs on demand and while its page/preview is active.
