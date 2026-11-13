"""Plan minimal, reversible niri integration; never execute configuration commands.

Callers: scripts/deploy.py. Uses deploy_niri_tree for bounded KDL/include analysis.
INVARIANT: planning stage is non-executing; applied niri edits require staged validation and rollback safety chain.
REL: scripts/deploy_niri_tree.py::graph/validate paths; scripts/deploy_state.py – journal/rollback artifacts.
The managed fragment is RENDERED from config/niri/lme-shell.kdl (the single source):
deploy swaps the startup line for its wrapper, rewrites shell IPC spawns through the
wrapper, and trims the blur section per niri version / existing user blur.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex

from deploy_niri_tree import graph, included, replace

MARKER = '// Managed by LME Shell deploy; edit your main config instead.\n'
SOURCE = 'config/niri/lme-shell.kdl'
AGENTS = {'waybar', 'mako', 'dunst', 'swaync', 'lxqt-policykit-agent', 'polkit-gnome-authentication-agent-1',
          'polkit-kde-authentication-agent-1', 'mate-polkit'}
BASE = '''// Created by LME Shell deploy. Existing user configs are patched instead.
input { touchpad { tap; }; }
layout { gaps 12; }
binds {
    Mod+T { spawn "kitty"; }
    Mod+Q { close-window; }
    Mod+Left { focus-column-left; }
    Mod+Right { focus-column-right; }
    Mod+Up { focus-window-up; }
    Mod+Down { focus-window-down; }
    Mod+Shift+Left { move-column-left; }
    Mod+Shift+Right { move-column-right; }
    Mod+Page_Down { focus-workspace-down; }
    Mod+Page_Up { focus-workspace-up; }
    Mod+Shift+Slash { show-hotkey-overlay; }
    Ctrl+Alt+Delete { quit; }
}
'''
# Byte-exact archives of the removed fragments live in tests/niri_legacy/; a user
# copy matching its digest is pure legacy (content now managed) and gets disabled.
LEGACY_DIGESTS = {
    'lme-shell.kdl': {'582bb1ff98b72b416ab9447aae4c19ab8d6eb48d1fcffd5bf3e0f8c1e44ae77a'},
    'media-keys.kdl': {'a053a448033cf2833407dd0b6257cfef24ed1a0e5f8b30c8df747bdd26bdcff4'},
    'capture-keys.kdl': {'b7bbc3bf19db699549c2b687151dbf7c9d7a0b4e0df2710aee5e7c5eab810acb'},
    'popup-blur.kdl': {'d7fd191a7ab1c820b3c78cf74b417e4798f3f9db7ea9e0cb4b2464d7af0b6b8c'},
}
BLUR_SECTION = '// blur-section:'


def normalized(key, modifier='super'):
    aliases = {'control': 'ctrl', 'mod': modifier}
    parts = key.lower().split('+')
    return tuple(sorted(aliases.get(p, p) for p in parts[:-1]))+(parts[-1],)


def legacy_include(path, repo):
    if path.resolve() == (repo/SOURCE).resolve(): return True
    if path.name not in LEGACY_DIGESTS or not path.is_file(): return False
    # A copy identical to the current source is fully managed; customized copies
    # stay in the graph: preserve their extra binds/blur/options.
    if path.name == 'lme-shell.kdl' and path.read_bytes() == (repo/SOURCE).read_bytes(): return True
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest in LEGACY_DIGESTS[path.name]


def competing(node, repo):
    if not node['args']: return False
    args = node['args']
    if node['name'] == 'spawn-sh-at-startup':
        if len(args) != 1: raise ValueError('Ambiguous shell startup command')
        args = shlex.split(args[0], posix=True)
    if args and args[0] in ('sh', 'bash', '/bin/sh', '/bin/bash') and len(args) >= 3 and args[1] == '-c':
        args = shlex.split(args[2], posix=True)
    known = any(Path(a).name in AGENTS or a.endswith('/quickshell/lme-shell/scripts/start.sh') or
                a == str(repo/'scripts/start.sh') for a in args)
    known |= any(Path(a).name in ('quickshell', 'qs') for a in args) and 'lme-shell' in args
    if known and any(re.search(r'[;&|`\n]|\$\(', a) for a in args):
        raise ValueError('Refusing ambiguous mixed startup command: '+str(node['args']))
    return known


def fragment(repo, wrapper, config, blur, existing_blur):
    """Render the managed fragment from config/niri/lme-shell.kdl."""
    from niri_keybinds import nodes
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    text = (repo/SOURCE).read_text()
    edits = []
    for node in nodes(text, positions=True):
        if node['disabled']: continue
        if node['name'] == 'spawn-sh-at-startup' and node['argument_spans']:
            end = node['argument_spans'][-1][1]
            edits.append((node['offset'], end, 'spawn-at-startup '+quote(wrapper)+' "start"'))
        elif node['name'] == 'binds':
            for bind in node['children']:
                if bind['disabled']: continue
                for action in bind['children']:
                    if action['disabled'] or action['name'] != 'spawn': continue
                    args = action['args']
                    if args[:5] != ['quickshell', '-c', 'lme-shell', 'ipc', 'call'] or not action['argument_spans']:
                        continue  # media keys spawn wpctl/brightnessctl/playerctl directly
                    rest = args[5:]
                    target = [wrapper, 'toggle', rest[2]] if rest[:2] == ['shell', 'toggle'] and len(rest) == 3 \
                        else [wrapper, 'ipc']+rest
                    spans = action['argument_spans']
                    edits.append((spans[0][0], spans[-1][1], ' '.join(quote(a) for a in target)))
    rendered = replace(text, edits)
    if not blur:
        cut = rendered.find(BLUR_SECTION)
        if cut >= 0: rendered = rendered[:cut].rstrip()+'\n'
    else:
        if existing_blur:
            # The user's own blur block owns the budget; the regions still apply.
            cut = rendered.find('\nblur {')
            if cut >= 0: rendered = rendered[:cut].rstrip()+'\n'
        liquid = config/'liquid-blur.kdl'
        if liquid.exists() and (liquid.is_symlink() or not liquid.read_text().startswith('// Generated by LME Shell: liquid glass backdrop blur.\n')):
            raise ValueError(f'Unmanaged liquid blur file; inspect before deployment: {liquid}')
        rendered += f'\ninclude {quote(liquid)} optional=true\n'
    return MARKER+'// Start once at login; current session is never killed.\n'+rendered


def source_keys(repo, modifier):
    """Every bind key the source fragment owns (panels, media, lock, captures)."""
    from niri_keybinds import nodes
    text = (repo/SOURCE).read_text()
    keys = set()
    for node in nodes(text):
        if node['name'] == 'binds' and not node['disabled']:
            for bind in node['children']:
                if not bind['disabled']: keys.add(normalized(bind['name'], modifier))
    return keys


def plan(root, repo, config, wrapper, niri_version):
    root = Path(os.path.abspath(root.expanduser()))
    managed = root.parent/'lme-shell-deploy.kdl'
    if managed.exists() and (managed.is_symlink() or not managed.read_text().startswith(MARKER)):
        raise ValueError(f'Unmanaged deployment fragment already exists: {managed}')
    skip = lambda p: p == managed or legacy_include(p, repo)
    documents = graph(root, skip)
    if not documents:
        from niri_keybinds import nodes
        documents[root.resolve()] = (root, BASE, nodes(BASE, positions=True))
    modifier = 'super'
    for _, _, document in documents.values():
        for node in document:
            if not node['disabled'] and node['name'] == 'input':
                for child in node['children']:
                    if not child['disabled'] and child['name'] == 'mod-key' and child['args']: modifier = child['args'][0].lower()
    keys = source_keys(repo, modifier)
    changes, notes, has_blur, managed_includes = {}, [], False, []
    for actual, (logical, text, document) in documents.items():
        edits = []
        def disable(node, reason):
            edits.append((node['offset'], node['offset'], '/- '))
            notes.append(f'{logical}:{node["line"]}: disable {reason} (original text retained)')
        active = [n for n in document if not n['disabled']]
        for node in active:
            if node['name'] == 'blur': has_blur = True
            elif node['name'] == 'binds':
                for bind in node['children']:
                    if not bind['disabled'] and normalized(bind['name'], modifier) in keys: disable(bind, 'conflicting shortcut '+bind['name'])
            elif node['name'] in ('spawn-at-startup', 'spawn-sh-at-startup') and competing(node, repo):
                disable(node, 'competing startup '+str(node['args']))
            elif node['name'] == 'include' and node['args']:
                child = included(logical, node)
                if child == managed:
                    managed_includes.append((actual, node, active[-1] is node))
                elif legacy_include(child, repo): disable(node, 'old LME include '+str(child))
        updated = replace(text, edits)
        if updated != text or not actual.exists(): changes[actual] = updated.encode()
    if not (len(managed_includes) == 1 and managed_includes[0][0] == root.resolve() and managed_includes[0][2]):
        for actual, node, _ in managed_includes:
            # Offsets refer to originals; combine all insertions before rewriting.
            logical, text, _ = documents[actual]
            from niri_keybinds import nodes
            current = changes.get(actual, text.encode()).decode()
            for candidate in nodes(current, positions=True):
                if not candidate['disabled'] and candidate['name'] == 'include' and candidate['args'] and included(logical, candidate) == managed:
                    current = replace(current, [(candidate['offset'], candidate['offset'], '/- ')])
                    break
            changes[actual] = current.encode()
        current = changes.get(root.resolve(), documents[root.resolve()][1].encode()).decode()
        changes[root.resolve()] = (current+('' if current.endswith('\n') else '\n')+'\n// LME Shell deployment (managed rules last).\ninclude '+json.dumps(str(managed), ensure_ascii=False)+'\n').encode()
        notes.append(f'{root}: include {managed} last')
    rendered = fragment(repo, wrapper, config, niri_version >= (26, 4), has_blur).encode()
    if not managed.exists() or managed.read_bytes() != rendered: changes[managed] = rendered
    for path in changes:
        parent = path.parent
        while not parent.exists(): parent = parent.parent
        if not os.access(parent, os.W_OK) or (path.exists() and not os.access(path, os.W_OK)):
            raise ValueError(f'Niri config is not user-writable; deploy will not sudo-edit it: {path}')
    return changes, notes
