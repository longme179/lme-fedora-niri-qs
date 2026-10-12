# Attribution and licenses

LME Shell is an original Fedora and niri implementation inspired by the desktop
interaction patterns of [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland).
The upstream reference inspected during development was commit
`c4f0582cbf4ad29607dbf3c20337815de8690b34`. Its root license is GNU GPL version 3.
No end-4 source code, wallpapers, bundled fonts, icons, or installation scripts
have been copied into this project. Original project source is distributed
under GPL-3.0-or-later; the motion adaptation below retains GPL-3.0-only.
The full GNU GPL version 3 license is in [LICENSE](LICENSE).

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
These interaction patterns have been implemented independently for LME Shell,
with the compatible motion adaptations described below. No iNiR shaders, bundled
fonts, wallpapers or installation scripts are redistributed.
See [docs/INIR_PORT.md](docs/INIR_PORT.md) for the settings/bar mapping.

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
is original. Those feature implementations do not redistribute upstream source,
assets or binaries. The later shared motion adaptations are described below.
`wl-clipboard` is an external GPL-3.0-or-later runtime dependency.

The desktop upgrade workflows were reviewed against iNiR notification grouping
and persistence, and DankMaterialShell launcher, network and niri display APIs.
Their implementation source was not vendored. The bundled emoji/symbol names
are generated with Python standard-library `unicodedata`; search aliases are
written for this project. The repository also includes the owner-supplied MIT
Ponytail skill, with its original license declaration preserved.

Shared motion now adapts these upstream implementations:

- [Caelestia StateLayer.qml](https://github.com/caelestia-dots/shell/blob/21a75375bb33123e481e796a74965038847c503d/components/StateLayer.qml),
  plus `components/Anim.qml` and `components/controls/ButtonBase.qml`, at
  `21a75375bb33123e481e796a74965038847c503d` (GPL-3.0). Press/hold/release
  sequencing is adapted in `qml/components/LiquidFeedback.qml` under
  GPL-3.0-only. The implementation uses a bounded flat pill ripple and LME's
  controls; it does not require Caelestia's plugin, shapes or assets.
- [DankMaterialShell Anims.qml](https://github.com/AvengeMedia/DankMaterialShell/blob/a1e6f6d6acae5e0688a4f04bd0e584b201ff6f68/quickshell/Common/Anims.qml)
  at `a1e6f6d6acae5e0688a4f04bd0e584b201ff6f68` (MIT). Expressive fast spatial,
  effects and exit Bézier curves are ported into `qml/theme/Theme.qml`; spatial
  overshoot is scaled by LME's existing bounce preference. Copyright (c) 2025
  Avenge Media LLC. The complete permission/copyright notice is preserved in
  [third_party/DankMaterialShell-LICENSE](third_party/DankMaterialShell-LICENSE).
- iNiR `modules/common/widgets/RippleButton.qml` at the revision above (GPL-3.0)
  informs the hue-preserving transparent hover state and shared feedback.

The ports reuse LME's preferences, controls and panel loader. No upstream binary,
plugin, font or wallpaper is bundled. Native blur remains implemented through
Quickshell/niri's existing compositor protocol.

Night Light also references iNiR's niri/wlsunset workflow. `wlsunset` and
`tesseract` are external runtime tools, not bundled binaries. Sunrise/sunset
calculation uses the approximate algorithm from *Almanac for Computers* (1990),
described in Ed Williams' [Sunrise/Sunset Algorithm](https://edwilliams.org/sunrise_sunset_algorithm.htm).
The Python implementation is original; it is not an astronomical ephemeris or
display calibration system.

`SpringMotion.qml` adapts DMS dank-qml-common at `bd90e4b6f2ec36035fc2cb560acdc0e418f669ac` (MIT, Copyright (c) 2025-2026 Avenge Media LLC). Modified for LME theme/loader lifecycle; full notice: [third_party/DankQmlCommon-LICENSE](third_party/DankQmlCommon-LICENSE).

### Geometric morph

Based on iNiR by snowarch (https://github.com/snowarch/inir), revision `48cdcecb0f6089cfbb7019054602eab28e154b3b`. `ShapeCanvas.qml` is modified for LME (GPL-3.0 with retained iNiR notice); rounded-polygon JS is retained under its Apache-2.0 license in `qml/components/shapes/LICENSE`. The library ports Knugel’s rounded-polygon-ts / AndroidX shape geometry, inherited through end-4. See [third_party/iNiR-NOTICE](third_party/iNiR-NOTICE) and [third_party/iNiR-LICENSE](third_party/iNiR-LICENSE). No upstream branding or assets are copied. Earlier no-vendoring descriptions apply only to the earlier feature implementations.

`StretchIndicator.qml` adapts the independent-edge movement of DCommon `DTabBar.qml` at the DCommon revision above; MIT notice retained. Navigation and controls remain LME implementations.
