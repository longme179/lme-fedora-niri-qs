#!/usr/bin/env python3
"""Static dependency/size ratchet; no runtime imports or third-party dependencies."""
import ast
import json
from pathlib import Path
import re
import sys

SOURCE = {'.py', '.qml', '.js', '.sh', '.frag', '.vert', '.json'}
TOKENS = re.compile(r'''//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''', re.S | re.X)
IMPORT = re.compile(r'^\s*\.?import\s+["\x27]([^"\x27]+)["\x27](?:\s+as\s+(\w+))?', re.M)


def files(root):
    return sorted(p for base in ('qml', 'scripts', 'tests', 'config')
                  for p in (root/base).rglob('*') if p.is_file() and p.suffix in SOURCE) + sorted(root.glob('*.qml'))


def local(root, path):
    path = path.resolve()
    return path.relative_to(root).as_posix() if path.is_relative_to(root) and path.is_file() else None


def resource(root, source, value):
    if not isinstance(value, str) or not re.search(r'\.(?:qml|js|py)$', value): return None
    value = value.removeprefix('root:/')
    for base in (source.parent, root):
        found = local(root, base/value)
        if found: return found
    return None


def dependencies(root, source):
    text = source.read_text(encoding='utf-8'); edges = set()
    if source.suffix == '.py':
        tree = ast.parse(text, filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module or '']
                if isinstance(node, ast.ImportFrom): modules += ['.'.join(filter(None, (node.module, x.name))) for x in node.names]
                bases = [source.parent, root, root/'scripts', root/'tests']
                if getattr(node, 'level', 0): bases = [source.parents[node.level-1]]
                for module in modules:
                    for base in bases:
                        path = base/module.replace('.', '/')
                        found = next((f for p in (path.with_suffix('.py'), path/'__init__.py') if (f := local(root, p))), None)
                        if found: edges.add(found); break
    elif source.suffix in ('.qml', '.js'):
        clean = TOKENS.sub(lambda m: ' ' if m[0].startswith(('//', '/*')) else m[0], text)
        body = TOKENS.sub(' ', clean)
        folders = [(source.parent, '')]
        for value, alias in IMPORT.findall(clean):
            path = source.parent/value
            if path.is_dir():
                folders.append((path, alias))
                relative = path.resolve().relative_to(root).as_posix()+'/'
                if re.match(r'(?:qml|scripts)/features/[^/]+/', relative): edges.add(relative)
            elif found := resource(root, source, value): edges.add(found)
        for folder, alias in folders:
            types = {p.stem: p for p in folder.glob('*.qml')}
            qmldir = folder/'qmldir'
            if qmldir.is_file():
                for name, value in re.findall(r'^(?:singleton\s+)?(\w+)\s+\S+\s+(\S+\.qml)\s*$', qmldir.read_text(), re.M):
                    types[name] = folder/value
            for name, path in types.items():
                symbol = re.escape((alias+'.' if alias else '')+name)
                if re.search(r'\b'+symbol+r'\s*(?:\{|\.)', body) and (found := local(root, path)): edges.add(found)
        if source.suffix == '.js':
            for value in re.findall(r"""\b(?:import|export)\s+[^;\n]*?\bfrom\s*["']([^"']+)["']""", clean):
                if found := resource(root, source, value): edges.add(found)
        urls = re.findall(r"""(?:\b(?:source|entry)\s*:|Qt\.(?:resolvedUrl|createComponent)\s*\()\s*["']([^"']+)["']""", clean)
        urls += re.findall(r"""Quickshell\.shellPath\s*\(\s*["']([^"']+\.py)["']""", clean)
        for value in urls:
            if found := resource(root, source, value): edges.add(found)
    elif source.suffix == '.json':
        def visit(value):
            if isinstance(value, dict):
                for v in value.values(): visit(v)
            elif isinstance(value, list):
                for v in value: visit(v)
            elif found := resource(root, source, value): edges.add(found)
        visit(json.loads(text))
    return edges


def owners(root, policy):
    result = {path: name for name, paths in policy['legacyFeatures'].items() for path in paths}
    index = json.loads((root/'config/features.json').read_text())
    for record in index['features']:
        descriptor = json.loads((root/record['descriptor']).read_text())
        paths = [record['descriptor'], *descriptor.get('sources', [])]
        paths += [v['entry'] for v in descriptor.values() if isinstance(v, dict) and 'entry' in v]
        for path in paths:
            if path in result and result[path] != record['id']: raise ValueError('Conflicting owner: '+path)
            result[path] = record['id']
    return result


def owner(path, ownership):
    match = re.match(r'(?:qml|scripts)/features/([^/]+)/', path)
    return ownership.get(path, match[1] if match else None)


def shared(path, policy):
    return any(path.startswith(prefix) for prefix in policy['sharedPrefixes']) or path in policy['sharedFiles']


def graph(root):
    return {p.relative_to(root).as_posix(): dependencies(root, p) for p in files(root)}


def cyclic_edges(edges):
    # An edge participates in a cycle iff its target can reach its source.
    result = set()
    for source, targets in edges.items():
        for target in targets:
            pending = [target]; visited = set()
            while pending:
                node = pending.pop()
                if node == source: result.add((source, target)); break
                if node not in visited:
                    visited.add(node); pending.extend(edges.get(node, ()))
    return result


def check(root):
    root = Path(root).resolve(); policy = json.loads((root/'config/architecture.json').read_text())
    if policy.get('version') != 1: raise ValueError('Unsupported architecture policy version')
    ownership = owners(root, policy); edges = graph(root); errors = []
    allowed = {(a, b): why for a, b, why in policy['legacyEdges']}
    cycles = {(a, b): why for a, b, why in policy['cycleEdges']}
    if len(allowed) != len(policy['legacyEdges']) or len(cycles) != len(policy['cycleEdges']):
        errors.append('Duplicate architecture exception')
    violations = set()
    for source, targets in edges.items():
        feature = owner(source, ownership)
        if source.endswith(('.py', '.qml', '.js')) and not feature and not shared(source, policy) and not source.startswith('tests/') and source not in policy['hosts']:
            errors.append('Unclassified source (declare descriptor ownership or shared/host role): '+source)
        for target in targets:
            other = owner(target, ownership)
            if feature and other != feature and not shared(target, policy):
                violations.add((source, target))
                if (source, target) not in allowed: errors.append('Forbidden dependency: '+source+' -> '+target)
    current_cycles = cyclic_edges(edges)
    for edge in sorted(current_cycles - cycles.keys()): errors.append('New cycle edge: '+' -> '.join(edge))
    for label, recorded, current in [('legacy', allowed, violations), ('cycle', cycles, current_cycles)]:
        for edge, reason in recorded.items():
            if not reason.strip(): errors.append('Missing '+label+' reason: '+' -> '.join(edge))
            if edge not in current: errors.append('Stale '+label+' exception (remove it): '+' -> '.join(edge))
    for path in files(root):
        if path.suffix not in SOURCE: continue
        relative = path.relative_to(root).as_posix(); count = sum(bool(line.strip()) for line in path.read_text().splitlines())
        limit = policy['largeFiles'].get(relative, 250)
        if count > limit: errors.append(f'Size cap: {relative}: {count} > {limit} nonblank lines')
        if relative in policy['largeFiles'] and count < limit: errors.append(f'Ratchet size ceiling to {count}: {relative}')
    return errors


if __name__ == '__main__':
    try: problems = check(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, SyntaxError) as error: problems = [str(error)]
    for problem in problems: print('Architecture: '+problem, file=sys.stderr)
    if not problems: print('Architecture: dependency, cycle and source-size checks passed')
    sys.exit(bool(problems))
