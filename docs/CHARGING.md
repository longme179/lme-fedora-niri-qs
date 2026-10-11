# Lenovo IdeaPad charging

The two modes are available in Control Center → Controls → Battery charging.
The implementation reads real kernel interfaces instead of saving an on/off
preference that could disagree with the laptop.

| Kernel interface | Conservation request | Maximum charge request |
| --- | --- | --- |
| `/sys/class/power_supply/BAT*/charge_control_end_threshold` | Set and verify 85 | Set and verify 100 |
| `/sys/class/power_supply/BAT*/charge_types` with Standard/Long Life | Select and verify `Long Life` | Select and verify `Standard` |
| `/sys/bus/platform/devices/VPC2004:*/conservation_mode` | Write and verify 1 | Write and verify 0 |
| No supported interface | Disabled, with an explanation | Disabled |

Numeric thresholds take priority. If the battery's start threshold is above or
equal to the requested stop threshold, the helper lowers it by five points
before changing the stop threshold. A separate active Long Life mode is cleared
and verified before setting a numeric limit. Rejected changes attempt to restore
any already changed values.

Modern Linux exposes Lenovo's fixed conservation setting through `charge_types`;
the legacy platform attribute is deprecated. The kernel prints the active choice
in brackets, for example `[Standard] Long Life` or `Standard [Long Life]`.
The writable values include the space in **Long Life**.

The IdeaPad Gaming 3 15ARH7 may expose only the fixed firmware conservation mode.
Its cutoff can differ by firmware, commonly around 60–80%; that interface cannot
set an exact 85%. The UI labels it **Conservation** and explains the firmware
limit. It only displays **Conservation · 85%** when a numeric threshold exists.
Maximum mode removes the conservation cap; it does not force immediate charging
if the battery is already full or the driver applies charging hysteresis.

## One-time setup on Fedora

Charge sysfs attributes are normally writable only by root. Install the narrowly
scoped helper on the laptop:

```bash
./scripts/install-charge-helper.sh --dry-run
sudo ./scripts/install-charge-helper.sh --install
```

The installer copies `scripts/charge_control.py` to
`/usr/local/libexec/lme-shell-charge`, owned by root with mode 0755, and backs up
an existing helper. It refuses symlink targets and unsafe writable parents.
The shell checks ownership and permissions before requesting privileges.
The helper accepts only `85`, `100` or read-only `status`, discovers paths under
`/sys` itself, and accepts no caller-supplied file path or shell command.

Install `polkit` if `pkexec` is unavailable. LME Shell includes its own
authentication agent: selecting a charge mode opens a centered password popup,
even when started by niri without a terminal. Enter the displayed account's
password and press Enter or **Authenticate**; an incorrect response can be
retried. **Cancel** or Escape dismisses the request. See
[AUTHENTICATION.md](AUTHENTICATION.md) if the popup does not appear.
The shell invokes:

```bash
pkexec --disable-internal-agent /usr/bin/python3 -I /usr/local/libexec/lme-shell-charge 85
```

The system's normal administrator prompt authorizes that individual change.
Python isolated mode avoids loading modules from a user-controlled environment.
There is no passwordless sudo rule, custom permissive Polkit policy or privileged
background shell. The desktop UI remains responsive while authentication runs;
the request times out after 90 seconds. A cancelled prompt is shown as an error.

Read capability/status without root:

```bash
python3 scripts/charge_control.py status
```

If the interface is missing, inspect the installed `ideapad_laptop` driver,
Fedora kernel and Lenovo BIOS support. This project does not load experimental
EC drivers or simulate a charge cap by periodically changing AC power state.
Firmware/driver settings can reset on reboot; the shell reads the actual limit
and does not silently reapply privileged changes.

## Validate on the target machine

Choose conservation while on AC and verify the kernel reports the selected
mode/threshold. Switch to maximum and verify it returns to Standard/100/0.
Charging behavior should then be observed over time; an already charged battery
is not discharged down to the cap by this setting.
Cloud fixtures validate path discovery, values, rollback and readback, but cannot
establish your laptop's physical cutoff or BIOS behavior.

To remove the helper, inspect `/usr/local/libexec/lme-shell-charge`, then remove
that exact installed file with administrator privileges. Retained backup files
can be restored or removed individually after inspection.
