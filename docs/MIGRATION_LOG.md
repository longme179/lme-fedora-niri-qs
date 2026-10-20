# Migration evidence

Scope: M0 baseline, merged M1/M2 and G3 baseline triage. M3 and later are not started.

## M0 baseline — 2026-10-20

- Production baseline: `main` / `0b9809b8c235c05071fd01bcc160827de68a738f`; confirmed equal to remote `main` with `git ls-remote`.
- Only the new harness was present as untracked files during this run; no production files or existing tests changed.
- Review branch: `refactor/m1-shared-infrastructure`; never update `main` from this work.

### Reproduce and isolation

```bash
./scripts/run-gates.sh --env-file /workspace/.lme-dev/env.sh \
  --pointer-dir /workspace/.lme-dev \
  --output /workspace/.lme-dev/m0-baseline-final --startup-runs 5
```

The optional env file selects the already-installed portable SDK. On a machine with the tools on PATH, omit it. Supply the existing private virtual-pointer helpers (`pointer-click`, `pointer-drag`, `pointer-move`, `pointer-right`); missing required opt-in checks produce a nonzero exit, not a pass. The output directory must be new. No packages are installed.

Each invocation starts its own headless Sway and D-Bus and creates private config/state/cache/data/runtime directories. Each startup sample also has fresh XDG directories. Only the owned compositor/processes are stopped. Real niri, user config and running shell are never addressed.

Common environment (the harness records the full resolved values in each gate JSON):

| Variables | Value |
| --- | --- |
| `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_RUNTIME_DIR` | `$OUT/config`, `state`, `cache`, `data`, `runtime`; directories mode 0700 |
| `DBUS_SESSION_BUS_ADDRESS`, `SWAYSOCK`, `WAYLAND_DISPLAY` | Allocated private D-Bus, owned Sway socket, `wayland-1` |
| `DBUS_SYSTEM_BUS_ADDRESS`, `NIRI_SOCKET` | Nonexistent `$OUT/no-system-bus`, `$OUT/no-niri`; fake niri fixtures override their own environment |
| `QT_QPA_PLATFORM`, `QT_QUICK_BACKEND`, `QSG_RHI_BACKEND`, `LIBGL_ALWAYS_SOFTWARE` | `wayland`, `rhi`, `opengl`, `1` |
| `WLR_BACKENDS`, `WLR_RENDERER`, `WLR_LIBINPUT_NO_DEVICES` | `headless`, `pixman`, `1`; output 1920×1080, scale 1 |
| `LME_SHELL_DEMO` | `1`; native Settings samples explicitly use backend demo data |
| `LME_TEST_POINTER`, `LME_TEST_DRAG`, `LME_TEST_POINTER_RIGHT` | `$POINTER_DIR/pointer-click`, `pointer-drag`, `pointer-right` |
| Qt/tool lookup | `PATH`: portable Quickshell bin + Qt/bin/libexec + inherited toolchain; `LD_LIBRARY_PATH`: SDK lib; `QML_IMPORT_PATH`: Quickshell qml + Qt qml; `QT_PLUGIN_PATH`: SDK plugins; `FONTCONFIG_FILE`: private SDK material.conf |

All inherited `LME_TEST_*` switches are cleared; only the gate-specific switches below are set to `1`. Inherited display/session sockets are cleared before private session startup.

### Gate commands and results

All commands run from the repository root with `PYTHONPATH=tests:scripts`. `U` below means `python3 -m unittest -v`; flags are the complete per-gate opt-ins in addition to the common environment.

| Gate | Command / test classes | Additional flags |
| --- | --- | --- |
| G0 | ./scripts/check.sh | none |
| G1 | U `migration_startup.SmokeCase` `test_settings_startup.NativeSettingsStartupCase` | `LME_TEST_PERSONALIZATION_UI=1` |
| G2 | U `test_settings_startup.NativeSettingsStartupCase` `test_personalization.NativePersonalizationCase` | `LME_TEST_PERSONALIZATION_UI=1` |
| G3 | U `test_control_grid.ControlGridUiCase` `test_upgrade_ui.UpgradeInterfaceCase` `test_bar_gestures.BarGestureQmlCase` | `LME_TEST_UPGRADE_UI=1` |
| G4 | U `test_clipboard.NativeClipboardCase` `test_clipboard.ClipboardInterfaceCase` `test_image_annotation_ui.AnnotationInterfaceCase` | `LME_TEST_CLIPBOARD_NATIVE=1`, `LME_TEST_CLIPBOARD_UI=1`, `LME_TEST_ANNOTATION_UI=1` |
| G5 | U `test_upgrades.DetachedDisplayCase` `test_managed_commands.ManagedCommandsCase` `test_battery_saver` `test_battery_saver_backend` `test_battery_saver_qml` | `LME_TEST_DISPLAY_WATCHDOG=1`, `LME_TEST_UPGRADE_UI=1` |
| G6 | U `test_launchpad.LaunchpadCase` `test_launchpad.LaunchpadQmlCase` `test_polling_ui.NativePollingCase` | `LME_TEST_POLLING_UI=1` |

| Gate | Passed | Failed | Skipped | Test-command wall seconds | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| G0 | 384 | 0 | 87 | 64.907 | completed-with-skips |
| G1 | 3 | 0 | 0 | 11.588 | passed |
| G2 | 4 | 0 | 0 | 38.733 | passed |
| G3 | 7 | 1 | 0 | 68.668 | failed |
| G4 | 5 | 0 | 0 | 16.689 | passed |
| G5 | 52 | 0 | 0 | 30.811 | passed |
| G6 | 7 | 0 | 0 | 21.063 | passed |

G0 also linted all 141 QML files: **0 errors, 67 existing warnings**, 17.359s separately. Command: `qmllint -I <Quickshell qml> -I <Qt qml> <each file>`. Total G0 command + lint wall time: 82.266s. No QML is changed by M1.

**Baseline is not wholly green.** G3 `test_control_grid.ControlGridUiCase.test_drag_keyboard_resize_visibility_persistence_and_action_isolation` fails at `tests/test_control_grid.py:215`: after switching to 8 columns the row count is 9; the test sends Down in choices `[4,8,9]` and waits for 8. At the final choice, Down leaves 9 selected. Reproduced in both baseline runs. No assertion or production UI was altered; fixing this existing test needs owner approval and is outside M1. M1 uses the approved G0–G2 + G5 set.

First harness attempt (`/workspace/.lme-dev/m0-baseline`) also failed G1 because IPC used the real checkout path after preview was launched through an alias. The new harness was corrected before its commit to use the same alias; final G1 above ran without skips. The first G4 omitted the optional right-click branch; the final run supplies `pointer-right` and covers it. Both attempts retain their raw logs.

Raw evidence on this execution machine: `/workspace/.lme-dev/m0-baseline-final/{G0..G6}.{log,json}`, `qmllint.log`, `machine.json`, `startup.json`, startup logs. These transient absolute paths are not required by production or committed as artifacts.

### Startup baseline (pre-descriptor)

Machine: AMD EPYC 7763, Linux 6.18.55 / Debian 13, 5 visible logical CPUs (4 CPU quota), 32 GiB memory limit; Python 3.12.14, Qt/qmllint 6.8.2, Quickshell 0.3.2 (`4f508be`), Sway 1.10.1. Qt uses RHI/OpenGL with Mesa llvmpipe (LLVM 19.1.7), not a physical GPU.

Method: launch a fresh process with fresh XDG config/state/data/cache/runtime each time; stage a private checkout alias. Measure monotonic time from process launch to the first visible, nonzero mapped Sway window belonging to its PID, polling every 20ms. Five consecutive runs, no discarded warm-up. OS page cache is **not** dropped: this is process/cache-cold startup, not a disk-cold or hardware benchmark. Mapping is the endpoint, not complete asynchronous service initialization.

| Entry | Five samples (seconds) | Median seconds |
| --- | --- | ---: |
| `./scripts/start.sh --preview --config migration-checkout` | 0.889106, 0.902983, 0.895152, 0.904393, 0.905599 | 0.902983 |
| `./scripts/settings.sh --page appearance` | 0.944687, 0.927213, 0.952900, 0.950821, 0.973834 | 0.950821 |

Settings measurement uses the real standalone host (`LME_SHELL_DEMO=0`, `LME_SHELL_BACKEND_DEMO=1`), not settings-demo.qml. G1 separately launches `settings.sh --demo --page appearance`, routes pages, closes and relaunches. Renderer limitations remain needs real-session check; tests that explicitly force Qt software/offscreen keep those original settings.

### G0 skipped tests (87; names and reasons)

G0 runs default discovery with opt-ins off, so it returns success with skips; it is recorded as **completed-with-skips**, never as all tests passed. G1–G6 enable only their documented subsets. Uncovered optional suites remain unverified; a substitute is not claimed.

- Enable only in a private Wayland session (9):
  - `test_activity.ActivityInterfaceCase.test_media_timer_stopwatch_close_reopen_and_motion`
  - `test_clipboard.ClipboardInterfaceCase.test_search_and_keyboard_copy_use_real_clipboard`
  - `test_clipboard.NativeClipboardCase.test_real_text_and_image_capture_copy_pause_and_clear`
  - `test_clipboard.NativeClipboardCase.test_watchers_stop_when_the_service_is_killed_without_cleanup`
  - `test_image_annotation_ui.AnnotationInterfaceCase.test_live_screenshot_toast_launches_editor_with_a_preserved_image_copy`
  - `test_image_annotation_ui.AnnotationInterfaceCase.test_screenshot_notification_opens_annotation_and_ordinary_icons_do_not`
  - `test_upgrade_ui.UpgradeInterfaceCase.test_launcher_hover_and_press_share_the_selected_row_shape`
  - `test_upgrade_ui.UpgradeInterfaceCase.test_motion_overshoot_reduced_motion_and_night_light_controls`
  - `test_upgrade_ui.UpgradeInterfaceCase.test_settings_launcher_wifi_notifications_and_responsive_cards`
- Enable the detached fake-niri preview test explicitly (1):
  - `test_upgrades.DetachedDisplayCase.test_watchdog_restores_after_the_initiating_process_exits`
- Set LME_TEST_AUTHENTICATION_UI=1 inside an isolated Wayland session (6):
  - `test_authentication.AuthenticationDialogCase.test_cancel_button_is_keyboard_reachable`
  - `test_authentication.AuthenticationDialogCase.test_escape_cancels_without_submitting`
  - `test_authentication.AuthenticationDialogCase.test_identity_change_clears_previous_input_and_refocuses`
  - `test_authentication.AuthenticationDialogCase.test_new_conversation_discards_previous_input`
  - `test_authentication.AuthenticationDialogCase.test_visible_challenge_uses_normal_echo`
  - `test_authentication.AuthenticationDialogCase.test_wrong_response_then_enter_success_with_cleared_input`
- opt-in native palette UI (1):
  - `test_palettes.PaletteUiCase.test_preview_does_not_apply_and_dark_light_switch_keeps_override`
- opt-in private Wayland Settings checks (1):
  - `test_shell_identity_ui.ShellIdentityCase.test_rename_from_settings_survives_restart_and_keeps_focus_routing`
- opt-in private Wayland UI (1):
  - `test_mirroring.MirrorUiCase.test_output_pickers_start_stop_and_live_state`
- opt-in private Wayland bar styling (1):
  - `test_bar_styling.BarStylingUiCase.test_presets_independent_corners_height_clamp_color_and_islands`
- opt-in private Wayland indicator checks (1):
  - `test_tab_indicator.TabIndicatorCase.test_nested_offsets_resize_hover_press_and_selection`
- opt-in private Wayland notes test (1):
  - `test_notes_ui.NotesUiCase.test_closed_editor_saves_and_external_conflict_keeps_buffer`
- opt-in private Wayland notification checks (1):
  - `test_notification_appearance.NativeNotificationsCase.test_wrapping_scroll_limits_positions_idle_lifecycle_and_settings`
- opt-in private Wayland personalization and Settings launch (3):
  - `test_personalization.NativePersonalizationCase.test_launcher_recovers_legacy_hidden_window_and_missing_ipc_handler`
  - `test_personalization.NativePersonalizationCase.test_native_color_font_edit_hover_press_reduced_motion_and_bottom_bar`
  - `test_personalization.NativePersonalizationCase.test_real_shell_under_gpt_symlink_opens_reuses_and_reopens_settings`
- opt-in private Wayland popup checks (2):
  - `test_popup_motion.PopupMotionCase.test_nearest_edge_close_reverse_backdrop_and_stroke`
  - `test_popup_motion.PopupMotionCase.test_real_shell_has_no_idle_ghost_and_seeds_every_fresh_surface`
- opt-in private Wayland screenshot editor/OCR check (2):
  - `test_capture_night.NativeCaptureCase.test_drawing_undo_redo_flattened_redaction_export_clipboard_and_real_ocr`
  - `test_capture_night.NativeCaptureCase.test_shell_capture_opens_independent_editor_and_can_reopen_after_close`
- opt-in private Wayland spectrum check (1):
  - `test_visualizer.VisualizerMotionCase.test_attack_and_release_follow_frame_without_a_second_easing_tail`
- opt-in private Wayland spring checks (1):
  - `test_motion_ports.SpringCase.test_retarget_preserves_velocity_and_reduced_motion_snaps`
- opt-in real portable Matugen (1):
  - `test_palettes.PaletteCase.test_real_multicolor_image_noninteractive_schemes_and_modes`
- private OpenGL button checks (1):
  - `test_button_materials.ButtonMaterialCase.test_power_agenda_calendar_custom_backgrounds_brightness_and_restoration`
- private OpenGL hover checks (3):
  - `test_glass_hover.GlassHoverCase.test_bevel_has_depth_on_bright_apps_and_preserves_clear_body_and_group_opacity`
  - `test_glass_hover.GlassHoverCase.test_pointer_entry_inertia_exit_geometry_input_and_idle_release`
  - `test_glass_hover.GlassHoverCase.test_rendered_glint_moves_across_the_rim_without_washing_out_the_body`
- private OpenGL selection checks (1):
  - `test_selection_lens.LensQmlCase.test_travel_reversal_press_reduced_motion_and_teardown`
- private QML motion checks (1):
  - `test_island_size.IslandSizeQmlCase.test_limits_live_resize_small_viewport_bottom_edge_and_reduced_motion`
- private Wayland Settings startup (1):
  - `test_settings_startup.NativeSettingsStartupCase.test_native_first_frame_and_repeated_gear_requests`
- private Wayland canvas UI (3):
  - `test_control_grid.ControlGridUiCase.test_drag_keyboard_resize_visibility_persistence_and_action_isolation`
  - `test_control_grid.ControlGridUiCase.test_qml_fixed_cells_do_not_reflow_unrelated_controls`
  - `test_control_grid.ControlGridUiCase.test_slider_mute_profile_actions_and_optional_power_bar_module`
- private Wayland geometry checks (1):
  - `test_glass_geometry.GeometryQmlCase.test_native_origin_updates_and_ambiguous_missing_geometry_falls_back`
- private Wayland glass checks (7):
  - `test_liquid_style.LiquidNativeCase.test_gl_shader_has_transparent_center_visible_rim_and_safe_missing_source`
  - `test_liquid_style.LiquidNativeCase.test_glass_tiles_and_tabs_stay_translucent_white_text_and_input_restore_their_colors`
  - `test_liquid_style.LiquidNativeCase.test_real_shell_uses_panel_masks_and_popup_regions_without_blurring_the_screen`
  - `test_liquid_style.LiquidNativeCase.test_separate_windows_do_not_share_textures_and_destroyed_windows_release_them`
  - `test_liquid_style.LiquidNativeCase.test_settings_switch_and_software_fallback_keep_controls_interactive`
  - `test_liquid_style.LiquidNativeCase.test_shared_texture_resize_motion_reversal_hidden_and_repeated_teardown`
  - `test_liquid_style.LiquidNativeCase.test_white_glyphs_render_without_an_outline_and_restore_the_smoked_color`
- private Wayland motion checks (4):
  - `test_jelly_v2.JellyQmlCase.test_blur_and_optics_use_final_transforms_once_before_the_same_frame_sync`
  - `test_jelly_v2.JellyQmlCase.test_native_blur_mask_matches_warped_shader_pixels_and_releases_bands`
  - `test_jelly_v2.JellyQmlCase.test_shader_renders_a_bowed_silhouette_and_fits_tight_native_bounds`
  - `test_jelly_v2.JellyQmlCase.test_software_and_rhi_surface_deform_settle_reverse_and_release_layers`
- private Wayland update controls (1):
  - `test_shell_update.ShellUpdateCase.test_update_buttons_and_worker_survive_the_settings_process_exiting`
- private glass settings controls (2):
  - `test_glass_controls.GlassControlsQmlCase.test_hex_slider_picker_reset_and_smoked_restoration`
  - `test_glass_controls.GlassControlsQmlCase.test_shader_controls_change_pixels_without_dimming_foreground_text`
- private launcher usage checks (1):
  - `test_launcher_history.LauncherUsageUiCase.test_real_launcher_uses_history_then_name_priority_and_click_dispatch`
- private wallpaper Settings checks (3):
  - `test_wallpaper_playback_ui.WallpaperSettingsCase.test_add_reorder_remove_interval_and_pause_use_saved_preferences`
  - `test_wallpaper_playback_ui.WallpaperSettingsCase.test_display_target_transition_duration_and_preview_render`
  - `test_wallpaper_playback_ui.WallpaperSettingsCase.test_rim_texture_follows_its_output_without_replacing_the_shared_image`
- requires PyGObject and a private D-Bus daemon (5):
  - `test_bluetooth_pairing.BluezProtocolCase.test_changing_adapter_cancels_owned_scan_and_pairing`
  - `test_bluetooth_pairing.BluezProtocolCase.test_display_reject_cancel_and_service_reconnect`
  - `test_bluetooth_pairing.BluezProtocolCase.test_pairing_widget_and_device_panel_lifecycle`
  - `test_bluetooth_pairing.BluezProtocolCase.test_scan_and_prompt_timeout`
  - `test_bluetooth_pairing.BluezProtocolCase.test_scan_pair_pin_passkey_confirm_authorize_and_close`
- requires private D-Bus/Wayland session (3):
  - `test_media_controls.MediaControlQmlCase.test_seek_shuffle_repeat_through_real_mpris`
  - `test_media_controls.MediaControlQmlCase.test_track_change_during_drag_does_not_seek_the_new_track`
  - `test_media_controls.MediaControlQmlCase.test_unsupported_player_disables_extended_actions`
- requires private MPRIS/D-Bus session (5):
  - `test_lyrics.LyricsQmlCase.test_embedded_lyrics_follow_seek_pause_track_and_visibility`
  - `test_lyrics_modes.LyricsModesQmlCase.test_cue_boundary_follows_double_speed_without_a_visible_media_timeline`
  - `test_lyrics_modes.LyricsModesQmlCase.test_plain_lyrics_and_players_without_timing_stay_readable`
  - `test_lyrics_modes.LyricsModesQmlCase.test_player_disconnect_and_reconnect_clear_then_reload_the_shared_session`
  - `test_lyrics_modes.LyricsModesQmlCase.test_shared_island_modes_follow_boundary_pause_seek_and_disable`
- requires private Quickshell session (1):
  - `test_laptop_features.NativeIdleCase.test_quickshell_shutdown_does_not_leave_an_idle_daemon`
- requires private Wayland (8):
  - `test_battery_saver_qml.BatterySaverVisualCase.test_canvas_tile_settings_switch_and_brightness_round_trip`
  - `test_desktop_ambient.DesktopAmbientQmlCase.test_native_surfaces_ignore_playback_respect_reduced_motion_and_release`
  - `test_desktop_ambient.DesktopAmbientQmlCase.test_shapes_keep_moving_without_media_during_pause_and_player_reconnect`
  - `test_desktop_ambient.DesktopAmbientQmlCase.test_visual_controls_update_live_shapes_without_replacing_the_surface`
  - `test_desktop_widgets.DesktopWidgetQmlCase.test_canvas_retains_instances_and_layout_through_visibility_and_output_changes`
  - `test_desktop_widgets.DesktopWidgetQmlCase.test_native_widgets_move_resize_clickthrough_and_edit_layer`
  - `test_desktop_widgets.DesktopWidgetQmlCase.test_resize_stays_anchored_and_small_viewports_preserve_valid_saved_sizes`
  - `test_desktop_widgets.DesktopWidgetQmlCase.test_setting_update_does_not_reset_geometry_during_a_pointer_gesture`
- requires private Wayland and D-Bus session (1):
  - `test_polling_ui.NativePollingCase.test_live_protocol_panel_lifecycle_operations_devices_and_reconnect`
- requires private Wayland and virtual pointer (1):
  - `test_popup_entry.BarPopupEntryCase.test_bar_openings_start_outside_the_output_and_island_still_resizes_with_a_spring`
- requires private Wayland idle session (1):
  - `test_laptop_features.NativeIdleCase.test_swayidle_receives_idle_and_resume_without_touching_hardware`

## M1 — A7 shared runner and atomic persistence

### Commits and scope

1. `072300c` — M0 harness only: `scripts/run-gates.sh` (82 lines), `tests/migration_checks.py`, `tests/migration_startup.py`.
2. `ea0f438` — characterization tests only: seven new `test_infrastructure.SharedContractsCase` tests. All passed against unchanged production before committing; no existing test assertion was edited.
3. `ac1982d` — extraction/imports only: seven production files, +178/−154 lines. No QML, config, settings schema, package/tree, dependency or policy changes.
4. Documentation — this migration log and README infrastructure/check instructions.

Smell removed: the display recovery CLI imported the desktop composition root for a generic runner; unrelated domains imported display code for generic persistence.

- `scripts/command_runner.py`: original `CommandError`, `CommandRunner` and exact 33-entry `TOOLS` whitelist.
- `scripts/storage.py`: original `read_json`, `write_json`, `locked`.
- `desktop_backend.py`, `battery_saver.py`, `launcher_history.py`, `lyrics.py`: import the shared implementations; display retains its own mode/apply/confirm/revert logic.
- `display_control.py --watch PATH`: same argv, stdin payload and fork/journal behavior; imports `command_runner`, never `desktop_backend`.

The moved bodies and whitelist were compared byte-for-byte with the characterization baseline. All retained top-level functions/classes in the five consumers were compared with that baseline; the only changed retained body is the watchdog's single import. Preferences' lock/reload/merge/fsync/atomic-write implementation is untouched. LauncherHistory's distinct lock implementation is also untouched.

### Characterization and gates

The new tests pin 0700 new parent directories / 0600 files (including replacing a 0644 file), UTF-8 JSON bytes, fsync before same-directory atomic replace, cleanup and original preservation after serialization/fsync/replace failure, fallback object identity, independent process locks and exception release, exact runner exception type/cause/error text, ANSI removal, secret redaction, 350-character detail bound, stdout fallback and success trimming. A subprocess blocks backend imports while importing the watchdog module and running apply/revert with an injected runner. This last test deliberately characterizes module import, not the old CLI's backend dependency.

Before extraction, run from the harness-only commit with the new test file present and production byte-identical to `main`:

```bash
./scripts/run-gates.sh --env-file /workspace/.lme-dev/env.sh \
  --pointer-dir /workspace/.lme-dev --output /workspace/.lme-dev/m1-before \
  --gates G0,G1,G2,G5
```

After extraction, at `ac1982d`:

```bash
./scripts/run-gates.sh --env-file /workspace/.lme-dev/env.sh \
  --pointer-dir /workspace/.lme-dev --output /workspace/.lme-dev/m1-after \
  --gates G0,G1,G2,G5 --startup-runs 5
```

Commands/flags/isolation are the same as the M0 gate matrix above, with the fresh output prefix substituted. Each command returned 0. No required opt-in test was skipped; G0 retains the same 87 default skips listed above.

| Gate | Before pass/fail/skip | After pass/fail/skip | Before test wall s | After test wall s |
| --- | --- | --- | ---: | ---: |
| G0 | 391/0/87 | 391/0/87 | 64.722 | 64.870 |
| G1 | 3/0/0 | 3/0/0 | 11.189 | 10.978 |
| G2 | 4/0/0 | 4/0/0 | 39.433 | 38.499 |
| G5 | 52/0/0 | 52/0/0 | 30.804 | 30.968 |

G0 additionally ran qmllint for all 141 QML files both times: 0 errors / 67 existing warnings. Lint wall time: 16.878s before / 16.986s after; total G0 command + lint: 81.600s / 81.856s. These warnings were not cleaned up in this refactor.

G1 exercised preview clipboard/control/activity/power open-close and standalone demo Settings page routing/relaunch, plus native Settings host startup. G2 exercised Gear reuse, native close/reopen and first-frame saved appearance. G5 includes **DetachedDisplayCase**, managed tool cancellation, detached-job isolation and saver backend/QML round trips. These runs use real private Wayland/D-Bus with fake hardware, not real niri modes or backlight.

G3/G4/G6 are M0 evidence only; they were not rerun for M1 because its approved gate set is G0–G2 + G5. The existing G3 failure remains unresolved and is not a passed gate. No required M1 gate failed, so the extraction commit did not need reverting.

### Additional dependency check

Post-extraction CLI probe: `python3 /workspace/.lme-dev/m1-watchdog-probe.py`, using the still-live harness's private environment. Copy only display_control/command_runner/storage into a temporary directory, add a poison desktop_backend.py that raises ImportError and records any attempted import, and supply a private fake niri. Invoke `python3 display_control.py --watch PATH` with the unchanged stdin payload, wait for pending after the initiator exits 0, request revert under the journal lock, and observe reverted. Six expected mode/scale/position commands were recorded: 60.003 Hz apply then 120.002 Hz restore; the poison import marker was absent. Result: passed, 0.339s; evidence `m1-after/watchdog-cli-probe.json`.

The first extra probe used captured stdout/stderr, which remain inherited by the detached child, and timed out. The corrected probe uses DEVNULL, matching DisplayControl.start's existing invocation; no production change was made in response. G5's independent initiator-exit/deadline test also passed.

A separate import-identity check confirmed backend's runner/error/TOOLS aliases and all old persistence aliases reference the exact shared objects. Definition ownership (`__module__`) and traceback filenames now identify command_runner/storage; this is the observable introspection difference from moving definitions. No action, error message, settings/journal format, permission, lock or visible behavior difference was found in the exercised paths.

### Compatibility adapters and retirement conditions

| Existing import facade | Shared target | Exact retirement condition |
| --- | --- | --- |
| `desktop_backend.CommandRunner`, `.CommandError`, `.TOOLS` | `command_runner` | Keep throughout the approved migration (D3). Retire only after explicit owner approval of a breaking public-import change, zero repository/fixture callers, and migration of documented external consumers. |
| `desktop_backend.read_json`, `.write_json` | `storage` | Same D3 condition; current backend use remains, and external import compatibility is retained. |
| `display_control.read_json`, `.write_json`, `.locked` | `storage` | Same D3 condition; display still uses these names and existing tests intentionally import the facade. Zero new internal consumers alone does not authorize removal. |

These are direct re-exports, not wrappers or alternate implementations. Existing imported helper names in saver/history/lyrics still point to the same objects. The public watchdog CLI, settings/preview entry points and environment variables remain permanent facades; no retirement is planned. No data migration is required.

Rollback: `git revert ac1982d`; keep the tests/harness. The original imports, journal format and watchdog argv are restored together without changing user data. M2+ are not started; A6 polling/cache/power-policy work remains excluded.

### Test changes and remaining limits

Added only `test_infrastructure.py`, `migration_checks.py`, `migration_startup.py` and the gate shell harness. Existing test files/assertions were not changed. M0 and before/after logs are retained outside the checkout under `/workspace/.lme-dev/`; the reproducible commands, counts, skip names/reasons and timings are recorded here.

Optional post-M1 startup samples, using the same method/machine (no descriptor work yet):

| Entry | Five samples (seconds) | Median seconds |
| --- | --- | ---: |
| preview | 0.907676, 0.886890, 0.881781, 0.932479, 0.932051 | 0.907676 |
| settings | 0.967165, 0.938902, 0.926777, 0.939372, 0.914844 | 0.938902 |

The small timing variation is not a performance claim. M4 must compare its Clipboard-only descriptor load with the recorded M0 baseline and stop for approval.

### Laptop acceptance checklist (needs real-session check)

1. Record current display mode/refresh, scale, position, brightness, power profile and appearance; keep a terminal available.
2. In Settings → Displays, apply another supported mode; confirm it and verify it stays after reopening Settings.
3. Apply a second mode; choose Revert and verify the confirmed mode/scale/position return.
4. Apply again and do not confirm; verify timeout restoration, including after closing Settings.
5. Enable battery saver; verify its supported display limit, brightness/profile and opaque, motion-free appearance.
6. Change brightness while saver is active; disable saver and verify the original mode, brightness, profile and appearance return.
7. Repeat saver on/off across Settings close/reopen; confirm there is no stuck “changing settings” state.
8. After saver restoration completes, start/stop a short recording and verify playback/audio and absence of a saver-busy error.

Physical GPU/glass/Jelly rendering, real display modes/hotplug, backlight, Bluetooth and suspend were not verified here. These remain **needs real-session check**. Stop after M1 for owner review.

## M2 — A7 shared content contracts — 2026-10-20

Baseline: merged `main` at `a962cf255af21446150e146e8ca36d0f8d8493d8`. Review branch: `refactor/m2-shared-content`. M2 only; M3 remains blocked by the unresolved G3 baseline failure unless the owner explicitly accepts it.

### Commits, scope and characterization

1. `e760d3a` — tests only: add five `test_infrastructure.ContentContractsCase` tests and extend the G4 harness to include the requested `test_capture_night` module with native opt-in enabled. All five new tests and the required gates passed on unchanged production before this commit. Existing assertions were not edited; M1's SharedContractsCase remains byte-identical.
2. `7fea618` — extraction only: four production files, +18/−13 lines. Move the exact MAX_TEXT assignment and image_type function from clipboard.py to flat scripts/content_types.py; redirect backend and capture imports. Keep clipboard.py's old names as direct compatibility exports.
3. Documentation — this log and README's shared-infrastructure paths.

Characterization covers:

- Exact 1,048,576-byte text limit: ASCII and multibyte UTF-8 accepted at the boundary, rejected at +1 byte; stored content and revision remain unchanged on rejection. Backend copyText also retains empty-text handling, type rejection, exact error text and wl-copy argv/stdin.
- PNG, JPEG, GIF87a/GIF89a, BMP and WebP MIME/suffix recognition, including minimal accepted headers and trailing payloads. Properly truncated/unsupported headers retain the exact `Unsupported clipboard image format` ValueError, without inserting history or exporting files.
- Annotation uses the same classifier, suffix, copy bytes, source preservation and launch message; malformed PNG still yields `Expected a PNG image` before export. Non-PNG fixtures characterize signature sniffing, not successful decoding in a real external editor.

Moved function/assignment source and every retained top-level class/function in clipboard.py, desktop_backend.py and screen_capture.py were checked against the passing characterization baseline. The bodies are byte-identical. The new module retains `from __future__ import annotations`, so annotation strings/signatures also remain unchanged. MAX_IMAGE and capture-specific limits stay with their features.

### Before / after gates

Use the existing isolated harness, unchanged except for the explicitly expanded G4 test list:

```bash
./scripts/run-gates.sh --env-file /workspace/.lme-dev/env.sh \
  --pointer-dir /workspace/.lme-dev --output /workspace/.lme-dev/m2-before \
  --gates G0,G1,G2,G4
./scripts/run-gates.sh --env-file /workspace/.lme-dev/env.sh \
  --pointer-dir /workspace/.lme-dev --output /workspace/.lme-dev/m2-after \
  --gates G0,G1,G2,G4
```

Before: main production plus the new tests/harness tuple. After: `7fea618`. Both commands returned 0. Each invocation uses a fresh private Sway/Wayland, private D-Bus and disposable XDG config/state/data/cache/runtime, as described in M0; no real niri config or running shell is touched. Qt RHI/OpenGL uses Mesa software rendering, not a physical GPU. SDK/machine details remain as recorded in M0; OCR uses Tesseract 5.5.0 with eng.

G0/G1/G2 commands and opt-ins are unchanged from the M0 matrix. M2 G4 runs `python3 -m unittest -v test_clipboard.NativeClipboardCase test_clipboard.ClipboardInterfaceCase test_image_annotation_ui.AnnotationInterfaceCase test_capture_night`, setting `LME_TEST_CLIPBOARD_NATIVE=1`, `LME_TEST_CLIPBOARD_UI=1`, `LME_TEST_ANNOTATION_UI=1`, **`LME_TEST_CAPTURE_UI=1`**, with the private click/drag/right-click helpers. Thus the extra capture tests run in the same session sequentially, without silently skipping their native cases. Historical M0/M1 G4 counts above remain evidence for their original narrower command.

| Gate | Before pass/fail/skip | After pass/fail/skip | Before test wall s | After test wall s |
| --- | --- | --- | ---: | ---: |
| G0 | 396/0/87 | 396/0/87 | 99.631 | 79.739 |
| G1 | 3/0/0 | 3/0/0 | 14.632 | 15.156 |
| G2 | 4/0/0 | 4/0/0 | 74.933 | 55.306 |
| G4 | 23/0/0 | 23/0/0 | 43.110 | 39.172 |

G0 is **completed-with-skips**, not all tests passed: its 87 skipped names/reasons are exactly the M0 list above, confirmed before and after. G1/G2/G4 have **zero skips**. Both G0 lint runs covered 141 QML files: 0 errors / 67 existing warnings. Lint wall time: 32.986s before / 27.437s after; total G0 command + lint: 132.617s / 107.176s. Timings are observations, not a performance claim.

G4's 23 passes comprise 5 native/UI Clipboard/annotation tests plus **18 test_capture_night tests (16 unit + 2 native)**, before and after. Native coverage includes drawing, undo/redo, flattened redaction, PNG export, real clipboard round trips, real OCR, editor close/reopen and screenshot-to-annotation routing. External Satty/Swappy launchers and niri screenshot acquisition use fixtures/fakes; this does not verify those applications or a real niri capture session. G1/G2 also ran preview open/close and standalone Settings/Gear/first-visible-frame checks.

Evidence: `/workspace/.lme-dev/m2-{before,after}/{G0,G1,G2,G4}.{log,json}`, `summary.json`, `machine.json`, `qmllint.log`. Recorded per-gate JSON contains the exact resolved commands and environment. Production unchanged for the before run; no required gate failed after extraction, so no revert was needed.

### Dependency check, adapters and retirement

An additional isolated subprocess used the live harness's private environment, blocked imports of both clipboard and sqlite3, then imported desktop_backend, screen_capture and content_types successfully. It checked the bound, image classification and postponed annotations; after removing the import blocker, it checked identity of all Clipboard/backend/capture aliases. Result: passed; `m2-after/content-dependency-probe.log`. Backend and screenshot no longer depend on Clipboard's implementation or load its SQLite dependency merely to access shared content helpers.

| Existing import facade | Target | Retirement condition |
| --- | --- | --- |
| `clipboard.MAX_TEXT`, `clipboard.image_type` | `content_types.MAX_TEXT`, `.image_type` | Keep for current worker globals, tests and external callers. Removal requires owner approval of a public import API change (D3) and migration of all repository/fixture/external references, including Clipboard's own uses. Zero new consumers alone is insufficient. |
| `desktop_backend.MAX_TEXT` | `content_types.MAX_TEXT` | Retain the existing public name (D3); retire only with owner approval and migration of all internal/fixture/external references. |
| `screen_capture.image_type` | `content_types.image_type` | Same D3 approval and zero-reference condition; current annotation code still uses this name. |

These are direct aliases with exact object identity, not wrappers. Legacy facade imports in test_clipboard/test_ports and the characterization suite deliberately remain exercised. The only observed introspection difference is image_type's defining module/traceback location changing from clipboard to content_types. No exercised action, rejection/message, settings, history format, byte limit, capture/editor behavior or UI behavior changed. No external dependencies, QML, schema, polling/cache/power policy or directory reorganization changed. Installer/fixture consumers already link/copy the complete scripts directory, so no packaging change was necessary.

Rollback: `git revert 7fea618`; keep the characterization tests and expanded G4 harness, which also passed before extraction. This restores old imports and helper ownership together without data migration. No M3 work or G3 assertion changes were made. M3 requires a separate authorization after G3 is resolved or explicitly accepted.

Physical GPU/glass/Jelly appearance, real niri capture, real external annotation applications and laptop hardware remain **needs real-session check**. Stop after M2 for review.

## Known baseline failures — G3 triage — 2026-10-20

**Status: G3 remains red, pending approval of a test-input correction. The owner has not accepted this failure. M3 remains unauthorized.** No production, harness, test or assertion changes were made during triage; the branch records documentation/evidence only.

Baseline: merged `main` at `054862690bb666fffa78cb2085c3ab44b502f74c` (M2 merge). Branch: `fix/g3-baseline`. All five attempts ran sequentially against that unchanged commit, before documentation edits. HEAD and a clean diff against main were checked before each attempt.

### Command, environment and repeated results

```bash
for attempt in 1 2 3 4 5
do
  ./scripts/run-gates.sh --env-file /workspace/.lme-dev/env.sh \
    --pointer-dir /workspace/.lme-dev \
    --output "/workspace/.lme-dev/g3-triage-main-$attempt" --gates G3
done
```

The resolved command is `python3 -m unittest -v test_control_grid.ControlGridUiCase test_upgrade_ui.UpgradeInterfaceCase test_bar_gestures.BarGestureQmlCase`, with `PYTHONPATH=tests:scripts` and `LME_TEST_UPGRADE_UI=1`. Each attempt starts a fresh owned Sway/D-Bus with disposable XDG directories and nonexistent system-bus/niri sockets; the M0 isolation/environment table applies. No real session or config is used. Required click/drag/right-click helpers and wtype are present. No test was skipped and no substitute gate was used.

Current machine: Intel Xeon Platinum 8573C, 5 visible logical CPUs, Linux 6.18.55 / Debian 13; Quickshell 0.3.2 (`4f508be`), Qt 6.8.2, Sway 1.10.1. This CPU differs from the historical M0 machine. Sway uses headless/pixman at 1920×1080 scale 1; Qt uses RHI/OpenGL with Mesa llvmpipe. `BarGestureQmlCase` explicitly overrides Qt to offscreen/software through `LocalQmlCase.run_qml`; its input is QtTest injection, not the native pointer helper. Those tests ran, but do not establish physical-GPU or native Wayland bar-input correctness.

| Attempt | Passed | Failed | Skipped | Gate command wall s | Harness wall s | Exit | Full unedited output |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 7 | 1 | 0 | 71.406 | 71.630 | 1 | [run-1.txt](evidence/g3-baseline/run-1.txt) |
| 2 | 7 | 1 | 0 | 75.112 | 75.299 | 1 | [run-2.txt](evidence/g3-baseline/run-2.txt) |
| 3 | 7 | 1 | 0 | 69.526 | 69.731 | 1 | [run-3.txt](evidence/g3-baseline/run-3.txt) |
| 4 | 7 | 1 | 0 | 65.891 | 66.035 | 1 | [run-4.txt](evidence/g3-baseline/run-4.txt) |
| 5 | 7 | 1 | 0 | 65.824 | 66.003 | 1 | [run-5.txt](evidence/g3-baseline/run-5.txt) |

Gate wall time is the harness measurement around the unittest subprocess, not the shorter unittest-reported duration. Harness wall includes session bootstrap/cleanup. [runs.json](evidence/g3-baseline/runs.json) retains the resolved per-attempt command/environment, baseline SHA, counts, durations and SHA-256 hashes of the byte-identical copied outputs.

Across 40 test executions: **35 passed, 5 failed, 0 skipped**. The same test failed 5/5 times; all other seven tests passed 5/5. This is repeatable in this environment, with no observed flakiness in these five samples; it is not a claim about every renderer/session.

Supplementary documentation check: the same harness with `--output /workspace/.lme-dev/g3-triage-docs-check --gates G0` ran `./scripts/check.sh`: **396 passed / 0 failed / 87 skipped**, 64.808s, exit 0, **completed-with-skips**. All 87 skipped names/reasons exactly match the M2-after list and the M0 inventory above. qmllint checked 141 files: 0 errors / 67 existing warnings, 17.014s. G0 leaves the native grid/UI opt-ins off, so its skipped tests do not resolve or replace G3. Raw G0 command/env/skip evidence remains at that output path; no additional gate was claimed green.

### Exact failure and classification: (b) test defect

Only failing test:
`test_control_grid.ControlGridUiCase.test_drag_keyboard_resize_visibility_persistence_and_action_isolation`.
`UpgradeInterfaceCase` (3 tests) and `BarGestureQmlCase` (2 tests) have no failures. The other two `ControlGridUiCase` tests also pass.

At this baseline's `tests/test_control_grid.py:213–215`, the test opens the row selector, always sends **Down, Return**, then waits for `s.get('ready') and s.get('rows') == 8`. After ten seconds the wait helper at line 179 raises `AssertionError(str(current) + '\n' + log.read())`. This is the failing assertion; the later `assertEqual(value['rows'], 8)` at line 222 is never reached. Every failure records `ready=True`, `columns=8`, `rows=9`, `saved.rows=9`; the complete state, traceback and QML log are preserved in each output above.

Evidence for a test-input error rather than an environment limitation or product defect:

- `scripts/desktop_features.py:28` derives the default rows from the tile catalog. `config/control-grid.json:167–172` places Battery saver at zero-based row 8, so the default is nine rows at four columns; expanding to eight columns preserves the saved nine-row height (`ControlGrid.qml:70–73`).
- `qml/panels/ControlCenter.qml:79–85` sorts the row choices and selects the saved row count. At this point they are `[4, 8, 9]`, with index 2 selected. Down at the last entry cannot select 8; Up selects the preceding entry.
- Before the timeout, the unchanged test successfully performs pointer drag/swap, invalid-drop rejection, keyboard Right movement and keyboard selection of eight columns. The backend is ready and the saved state agrees with the UI.
- A separate inspection used a temporary copy of the existing demo fixture with a read-only IPC accessor for the real row selector. In a fresh private Sway/D-Bus, Down/Return retained 9; Up/Return selected and saved 8; restarting the fixture retained eight columns/eight rows. The real QML components/backend were unchanged. The same `unknown keymap format: 0` warnings occurred while input succeeded; these warnings do not explain this timeout.

The inspection is **diagnostic evidence, not a passing G3 run**: it did not execute the remainder of the failing test. [row-probe.json](evidence/g3-baseline/row-probe.json) contains before/after/restart state; [row-probe-qml.txt](evidence/g3-baseline/row-probe-qml.txt) includes the renderer and complete QML log. [row-probe.py.txt](evidence/g3-baseline/row-probe.py.txt) preserves the external inspection script; it is not an installed test/helper or production code.

### Proposed remedy — NOT applied, awaiting owner approval

Only change the navigation input so it moves toward 8 in the sorted choices, including a saved count below 8. Do not change assertions, timeouts, defaults, product behavior or skips; do not mark this test expected-failure.

```diff
--- a/tests/test_control_grid.py
+++ b/tests/test_control_grid.py
@@
                 if large['rows'] != 8:
-                    click('controlGridRows');subprocess.run(['wtype','-s','200','-k','Down','-k','Return'],env=env,check=True)
+                    direction = 'Up' if large['rows'] > 8 else 'Down'
+                    click('controlGridRows');subprocess.run(['wtype','-s','200','-k',direction,'-k','Return'],env=env,check=True)
                 wait(lambda s:s.get('ready') and s.get('rows')==8)
```

After approval, apply this test-only diff and rerun the complete G3 set with the same isolation/flags, including all statements after the former timeout. No corrected-test gate has run yet, and no green result is inferred from the diagnostic. If a later assertion then fails, triage it separately before any further change.

### Overlap with M3 and remaining protection

**There is overlap through ControlCenter/ControlDashboard composition**, although the failing operation is grid-height selection, not tab routing. M3 will replace positional routing in ControlCenter, Agenda, BarGestures and ControlDashboard. File/line references below are verified at `0548626`.

| Area | Coverage while G3 is red |
| --- | --- |
| Aborted grid test | Steps/assertions at 216–238 and 242–244 never execute: keyboard movement to rows 4–7 and legal bounds; positive scroll at 220; reset retains eight rows at 221–222; card reorder/size does not move tiles at 228; hiding Wi-Fi preserves layout at 231–232; Done re-enables DND actions at 233–234; close/reopen retains layout/visibility and clears edit mode at 235–238; final QML error checks at 242–244. These would no longer guard a composition/lifecycle regression during M3. Earlier drag/focus/action-isolation checks and finally cleanup at 239–241 still execute. |
| ControlCenter tab routing | The independent `UpgradeInterfaceCase.test_settings_launcher_wifi_notifications_and_responsive_cards` still passes: `tests/test_upgrade_ui.py:124–126` selects System, verifies three process records and search filtering, then returns to Controls and verifies the monitor state clears. This protection is not lost to the grid test's failure. |
| BarGestures | Both QML tests still pass for defaults/overrides, mute/DND/scroll, primary opening and suppression. They do **not** assert the exact destination for the explicit `audio/devices/agenda/system` mapping at `qml/bar/BarGestures.qml:52–54`. This is a pre-existing coverage gap, not an assertion bypassed by the grid timeout. |
| Dashboard monitor shortcut | G3 does **not** click the separate `System monitor` button at `qml/panels/ControlDashboard.qml:320` and assert its destination index. Selecting the System tab is a different path. This is also a pre-existing gap. |

M3's planned new `test_navigation.TabContractCase` / `NativeTabCase` must cover those destination/order/hook contracts when separately authorized. They were not added here. No polling, power policy, production, assertion, harness or dependency changes were made. **STOP: awaiting test-diff approval; M3 stays unauthorized.**
