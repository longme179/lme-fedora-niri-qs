#!/usr/bin/env python3
"""Patch scenarios.py + run.py in the repo checkout (e5ef1b1 anchors) for the eyes.

Run on the host: python3 eyes_patch_repo.py   (from scripts/perf of the repo).
"""
import ast

# scenarios.py -------------------------------------------------------------------
src = open("scenarios.py").read()
if "import eyes" not in src:
    a = "from probe import ProbeError  # noqa: E402"
    assert a in src, "probe import anchor"
    src = src.replace(a, a + "\nimport eyes  # noqa: E402  (screenshot eyes; off unless ctx.eyes is set)", 1)
if "self.eyes = None" not in src:
    a = "        self.box = None             # top-left of the Settings window on the output"
    assert a in src, "box anchor"
    src = src.replace(a, a + "\n        self.eyes = None            # eyes.Eyes when a run wants a screenshot per click", 1)
if "self.eyes.look" not in src:
    a = '    def click_at(self, x, y):\n        return self.shot(self.inj.click_at(x, y))\n'
    assert a in src, "click_at anchor"
    b = ('    def click_at(self, x, y):\n'
         '        at = self.shot(self.inj.click_at(x, y))\n'
         '        if self.eyes is not None:\n'
         '            try:\n'
         '                self.eyes.look((x, y), tag=f"click-{x:.0f}-{y:.0f}")\n'
         '            except Exception:  # noqa: BLE001  (the eyes never fail a run)\n'
         '                pass\n'
         '        return at\n')
    src = src.replace(a, b, 1)
open("scenarios.py", "w").write(src)
ast.parse(src)
print("scenarios.py patched")

# run.py -------------------------------------------------------------------------
src = open("run.py").read()
if '"--eyes"' not in src:
    a = '    ap.add_argument("--no-notice", action="store_true", help="no desktop notification at the swap")'
    assert a in src, "flag anchor"
    src = src.replace(a, a + '\n    ap.add_argument("--eyes", action="store_true", '
                     'help="screenshot the screen around every click (eyes/ under the run dir)")', 1)
if "import eyes" not in src:
    a = "import scenarios  # noqa: E402\n"
    assert src.count(a) == 1, "import anchor"
    src = src.replace(a, a + "import eyes  # noqa: E402  (screenshot eyes, active only with --eyes)\n", 1)
if "ctx.eyes = eyes.Eyes" not in src:
    a = ('        ctx = scenarios.Ctx(inj, probe, deadline_ms=time.time() * 1000.0 + args.budget * 1000.0,\n'
         '                            width=screen["width"], height=screen["height"])')
    assert a in src, "ctx anchor"
    src = src.replace(a, a + '\n        if args.eyes:\n            ctx.eyes = eyes.Eyes(out, screen["width"], screen["height"])', 1)
if 'ctx.meta["eyes"]' not in src:
    a = '            ctx.meta["ended"] = failure or "finished"'
    assert a in src, "dump anchor"
    src = src.replace(a, a + '\n            if ctx.eyes is not None:\n                ctx.meta["eyes"] = len(ctx.eyes.dump())', 1)
open("run.py", "w").write(src)
ast.parse(src)
print("run.py patched")
