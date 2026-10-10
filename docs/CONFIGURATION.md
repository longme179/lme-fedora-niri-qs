# User configuration

The source checkout is separate from user preferences. Settings are stored
under `${XDG_CONFIG_HOME:-~/.config}/lme-shell`. The shell creates its settings
file only when a preference is saved; missing configuration uses defaults.

## Settings

Use the Settings panel to change preferences. A typical `settings.json` is:

```json
{
  "language": "en",
  "animations": true,
  "opacity": 0.9,
  "accent": "#9580ff",
  "wallpaper": "",
  "dockAutoHide": true,
  "terminal": "kitty"
}
```

The UI and codebase are intentionally English. The `language` field is fixed to
`en`; it does not change the rest of your Fedora system's locale. Motion can be
disabled, and higher panel opacity improves readability over busy wallpapers.
The configured terminal must be an executable name available on `PATH` that
supports `-e`, such as `kitty`, `foot`, or `alacritty`. This preference applies
to `Terminal=true` desktop entries even when `gio` is installed. Other entries
use `gio` when available, with a tokenized executable fallback otherwise.

Changes made through the Settings panel apply to the running session. If you
edit `settings.json` outside the shell, restart the shell to reload that file.

Select an existing PNG, JPEG, WebP, GIF, or BMP wallpaper from the shell's
Settings panel. Changing a wallpaper requires a running `swww-daemon`:

```bash
swww-daemon
```

Run that daemon once per session, not once per wallpaper change. The startup
wrapper starts it if necessary when restoring a saved wallpaper. The original
SVG in `assets/wallpapers` is editable source artwork; use the PNG version or
another raster image with `swww`.

## Palette

The defaults follow a Dracula Pro-style dark palette. Licensed Pro theme files
are not bundled. If you own a specific Pro variant, add your preferred colors
to `~/.config/lme-shell/palette.json`:

```json
{
  "background": "#22212c",
  "panel": "#2d293d",
  "surface": "#393447",
  "text": "#f8f8f2",
  "muted": "#aaa6c0",
  "purple": "#9580ff",
  "pink": "#ff80bf",
  "cyan": "#80ffea",
  "green": "#8aff80",
  "yellow": "#ffff80",
  "red": "#ff9580",
  "border": "#605975"
}
```

You may override only the keys you need. Use hex colors in this schema. The
shell watches `palette.json` and reloads valid color changes while it is running;
no restart is needed for palette edits. Keep passwords, tokens, and other
credentials out of these files.

The primary accent is also saved in `settings.json`; changing the palette's
`purple` token does not replace an explicitly saved accent. Use the Settings
accent field to change it. The theme prefers Inter and JetBrains Mono when
installed, with the system's available fonts as fallback; the supplied Noto
packages provide a usable baseline without bundling fonts.

## Surface effects

The default appearance uses translucent fills, layered highlights, rounded
corners, and brief animations. It does not depend on background blur, expensive
full-screen effects, or NVIDIA offloading. This makes the default practical for
the laptop's integrated Radeon GPU.

Some newer niri builds expose compositor background effects for layer surfaces.
If your version documents that feature, you can experiment in your own niri
config using the namespaces shown by `niri msg layers`. Keep those optional
rules outside this project's baseline fragment and validate them with
`niri validate`; unsupported blur options can invalidate older niri configs.

## Preferences and permissions

The backend delegates operations to the running user's existing tools. Backlight,
Bluetooth, Wi-Fi, and power-profile access therefore follows Fedora's current
device permissions, service state, and polkit policy. The project does not add
passwordless sudo rules, run privileged background code, or install new polkit
rules. Errors are shown in the shell instead of being treated as success.

Notifications are kept for the running shell session; restarting the shell
clears that history. Do Not Disturb affects shell popups and is not a system-wide
notification policy.
