# Attribution and licenses

LME Shell is an original Fedora and niri implementation inspired by the desktop
interaction patterns of [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland).
The upstream reference inspected during development was commit
`c4f0582cbf4ad29607dbf3c20337815de8690b34`. Its root license is GNU GPL version 3.
No upstream shell source code, wallpapers, bundled fonts, icons, or installation
scripts have been copied into this project. This project's source is distributed
under GPL-3.0-or-later; the full license is in [LICENSE](LICENSE).

Quickshell, Qt, niri, and the desktop utilities are external runtime dependencies
with their own licenses. Installing this project does not redistribute them.

The color system follows Dracula Pro's dark, purple-led visual direction. It does
not include purchased Dracula Pro files, wallpapers, fonts, or branding assets.
Palette values are editable locally; users who own a preferred Pro variant can
enter their own color values. The project is unaffiliated with Dracula Pro.

The included wallpaper and UI shapes are original vector artwork. Application
icons are resolved from the user's installed icon theme, and are not bundled.

The modular bar, searchable settings registry and Material design direction also
reference [snowarch/iNiR](https://github.com/snowarch/iNiR), inspected at commit
`48cdcecb0f6089cfbb7019054602eab28e154b3b` (root license: GNU GPL version 3).
These interaction patterns have been implemented independently for LME Shell.
No iNiR source files, shaders, bundled fonts, wallpapers or installation scripts
are redistributed. See [docs/INIR_PORT.md](docs/INIR_PORT.md) for the mapping.

Roboto is installed through Fedora's `google-roboto-fonts` package. The project
references it by family name and does not distribute the font files. Small shell
icons are original Canvas drawings; Material Symbols font assets are not bundled.


Wallpaper rendering uses the external [awww](https://codeberg.org/LGFae/awww.git)
client and daemon. No upstream binary or source is bundled. The CLI integration
was checked against release 0.12.1 at
`f66e12a76dbc4c669b2f1375f78bce49f5b19d66` (GNU GPL version 3).

Weather and city search are provided by [Open-Meteo](https://open-meteo.com/),
whose weather data requires attribution under CC BY 4.0. The widget displays
that attribution. Approximate automatic location uses [IPwho.is](https://ipwho.is/).
These are external network services; no provider dataset or assets are bundled.
The implementation uses the providers' public endpoints without an API key.

Clipboard history and the expandable Activity island also reference
[AvengeMedia/DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell),
inspected at `f372777829212f0db41dc623e7e495e63c8e4341` (MIT), and iNiR at the
revision above. All delivered history, storage, Activity and protocol-test code
is original. No upstream source, assets or binaries are redistributed.
`wl-clipboard` is an external GPL-3.0-or-later runtime dependency.
