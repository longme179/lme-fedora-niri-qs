# Notification appearance

Open **Settings → Notifications**, or run:

```bash
./scripts/settings.sh --page notifications
```

The preview uses the same card as desktop popups and notification history.
**Send test notification** shows a real popup, unless Do Not Disturb is active.

- **Placement:** follow the bar or choose one of six screen positions; adjust
  width and screen margin. Popups enter and leave through the same screen edge.
- **Shape:** change corner radius, padding, border width and surface opacity.
- **Typography:** set title/body sizes. Font families follow **Elements and
  fonts**: headings for titles, body for message text, buttons for actions.
- **Colors:** select fill, title, body, accent or border to open the HSV/alpha/hex
  picker. Hex uses `#RRGGBB` or `#AARRGGBB` (alpha first). These overrides are also
  available under **Elements and fonts → Notifications** and in Appearance profiles.
- **Idle motion:** a soft, six-lobed outline rotates around a stationary bell.
  Choose a 6–40 second rotation period or switch it off. Disabling shell
  animations stops it too. Hidden cards and history icons do not rotate.

Cards measure their wrapped text instead of using a fixed height or a three-line
cutoff. Long words wrap, and action buttons flow onto additional rows. When the
popup stack reaches the output's available height, each card gets a scrollable
message area; its app heading and dismiss button remain accessible. History
keeps the full message in its scrolling list. Critical notifications keep a red
outline and icon.

Shell status messages use the same appearance, remain bottom-center, and grow
up to 60% of the output height. Longer status messages can be scrolled or dismissed.
Screenshot notifications still open annotation when their card is clicked.

Changes save automatically in the existing settings file. Notification options
are included in settings exports and backups; color overrides are also included
in Appearance profiles. No additional package is required.
