---
name: modularity
description: >
  Apply Vlad Khononov's Balanced Coupling model pragmatically to LME Shell alongside
  Ponytail: module boundaries, shared infrastructure, small refactors, extensibility
  and an aggregate 400-500 MB shell memory target. Use during shell development;
  read the deeper upstream review/design references only when the task needs them.
license: CC-BY-NC-SA-4.0
---

# LME Modularity + Ponytail

LME adaptation of [vladikk/modularity](https://github.com/vladikk/modularity),
by Vlad Khononov; provenance and the separate documentation license are in
[UPSTREAM.md](UPSTREAM.md). Use together with [Ponytail](../ponytail/SKILL.md).
Modularity chooses a useful boundary; Ponytail keeps its implementation small.
These are development instructions, never a shell runtime service or dependency.

## Local policy takes precedence

The owner requested proportionate use on 2026-10-23. Follow the user's authorized
scope, AGENTS.md and docs/STATE.md before upstream workflow templates.
Do not inherit upstream's mandatory step approvals, repeated domain questions,
whole-repository scans or Markdown-plus-HTML reports for routine work. Do not
read docs/archive/ unless answering a specific historical question. Ask only
when the current task/STATE requires it; do not restart approved design phases.
No automatic sub-agents, tools, package installs or separate orchestration layer.
Use available tools and plain rg/Python instead of requiring Claude-only tools.

## Apply to the change at hand

1. Read actual callers, state ownership and contracts before suggesting a split.
   For a small change, a short mental check is enough; do not generate paperwork.
2. Consider all three dimensions of [Balanced Coupling](https://coupling.dev):
   shared knowledge, cost of changing both sides, and likelihood of that change.
   Same feature/domain rules belong together. Separate features use small explicit
   service contracts; do not pass DesktopBackend or copy its private rules.
3. Fix expensive cascading changes in areas that evolve. Accept stable legacy
   seams when changing them would cost more than the benefit. Do not split files,
   introduce interfaces or isolate processes just to satisfy a design label.
4. Reuse the catalog, schema fragments, action registry, shared services, scheduler
   and completion emitter. Keep one source for rules/defaults and domain-owned
   validation. An added feature should mostly touch its own files and index entry.
5. Preserve behavior, public IPC/CLI/JSON, Settings persistence, worker lifecycle,
   preview/standalone Settings and existing dependency guardrails. Async preflight,
   cancellation and completion contracts must be understood before extraction.
6. Characterize observable behavior before refactoring; test the affected contract.
   Follow STATE gates; this skill adds no extra test suites or approval gates.
   Review the diff for knowledge leaks, unnecessary layers and resource ownership.

## Memory is a whole-shell budget

Aim for <=400 MB in steady use and <=500 MB during ordinary interactive use.
These are engineering targets, not a new OS limit or a guarantee for every workload.
Count the main Quickshell, Python backend, owned persistent workers and standalone
Settings/backends while open. Count all LME instances, not only the main PID tree.
Prefer aggregate PSS from /proc/PID/smaps_rollup to avoid double-counting shared Qt
pages; if only summed RSS is available, label that limitation. Do not quietly omit
helper processes. Report heavy temporary editor/recording/upscale job peaks
separately from the steady-state total, with their scope stated explicitly.
Use existing runtime sanity samples when available; no continuous profiler or
new monitoring process. Separate-instance RSS samples do not prove this budget.

Reuse shared models, images, backdrop textures and existing worker pools. When
authorized, load expensive UI on demand, bound caches and release unused resources.
Do not add a backend/process/timer per widget for architectural separation. Never
change A6 polling/cache/power policy, feature behavior or visuals in a refactor
merely to chase this target. If the target is missed, identify measured owners and
propose the smallest scoped correction; do not claim a saving without evidence.

## Optional depth

- [Balanced Coupling reference](upstream/skills/balanced-coupling/SKILL.md): model details.
- [Review](upstream/skills/review/SKILL.md): for a requested coupling audit of a specific area.
- [Design](upstream/skills/design/SKILL.md): when a new boundary or contract is actually needed.
- [Document](upstream/skills/document/SKILL.md): only for explicitly requested formal reports;
  its [HTML template](upstream/skills/document/assets/template.html) is bundled unchanged.

Load only the references needed by the current task. Keep findings brief and
concrete: what changes together, which boundary helps, its runtime/memory cost,
and what is deliberately left alone. End with what remains unverified, as Ponytail requires.
