# New-tool test adjustment

Optional follow-up, awaiting owner approval; not applied in the prototype.

AGENTS.md: "Never edit an existing assertion without asking."
The new tool's first contract launches settings.sh from the terminal process.
Use the existing Gear IPC route instead, so Settings inherits the running shell's
GPU/environment and executable selection. No existing baseline/runtime API changes.

Proposed adjustment to the new `test_memory_workload.py` test:

```diff
- patch.object(s, 'ipc', side_effect=['false', 'true']),
+ patch.object(s, 'ipc', side_effect=['', 'false', 'true']) as ipc,
- self.assertEqual(launch.call_args.args[0], [str(ROOT/'scripts/settings.sh'), '--page', 'appearance'])
+ self.assertEqual(ipc.call_args_list[0].args, (MAIN, 'shell', 'toggle', 'settings'))
+ launch.assert_not_called()
```

Keep the readiness, no-terminate/no-kill assertions, timeouts and frozen fixtures.
