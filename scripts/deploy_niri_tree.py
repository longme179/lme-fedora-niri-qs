"""Bounded KDL include graph and staged niri validation, preserving logical bases."""
import os
from pathlib import Path
import subprocess
import tempfile

from niri_keybinds import nodes


def included(path, node):
    value = Path(node['args'][0]).expanduser()
    return Path(os.path.abspath(value if value.is_absolute() else path.parent/value))


def graph(root, skip=lambda path: False):
    documents, bases = {}, {}
    total = 0
    def visit(path, depth=0):
        nonlocal total
        resolved = path.resolve()
        if resolved in documents:
            if bases[resolved] != path.parent: raise ValueError(f'Ambiguous relative include base: {path}')
            return
        if depth > 12 or len(documents) >= 32: raise ValueError('Niri include limit reached')
        text = path.read_bytes().decode('utf-8')
        total += len(text.encode())
        if len(text.encode()) > 512*1024 or total > 2*1024*1024: raise ValueError('Niri config exceeds size limit')
        document = nodes(text, positions=True)
        documents[resolved] = (path, text, document); bases[resolved] = path.parent
        for node in document:
            if node['disabled'] or node['name'] != 'include' or not node['args']: continue
            child = included(path, node)
            if skip(child): continue
            if not child.exists() and node['props'].get('optional') == 'true': continue
            visit(child, depth+1)
    if root.exists(): visit(root)
    return documents


def replace(text, edits):
    for start, end, value in sorted(edits, reverse=True): text = text[:start]+value+text[end:]
    return text


def validate(root, changes, binary='niri'):
    """Adjacent staging preserves other relative paths (e.g. xkb files)."""
    temporary, documents = {}, {}
    def visit(path, depth=0):
        key = path.resolve()
        if key in documents: return
        if depth > 12 or len(documents) >= 32: raise ValueError('Niri staged include limit reached')
        text = changes[key].decode() if key in changes else path.read_bytes().decode('utf-8')
        document = nodes(text, positions=True)
        documents[key] = (path, text, document)
        for node in document:
            if node['disabled'] or node['name'] != 'include' or not node['args']: continue
            child = included(path, node)
            if child.resolve() not in changes and not child.exists() and node['props'].get('optional') == 'true': continue
            visit(child, depth+1)
    import json
    try:
        visit(root)
        for key, (path, _, _) in documents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, raw = tempfile.mkstemp(prefix='.lme-validate-', suffix='.kdl', dir=path.parent)
            os.close(fd); temporary[key] = Path(raw)
        for key, (path, text, document) in documents.items():
            edits = []
            for node in document:
                if node['disabled'] or node['name'] != 'include' or not node['args']: continue
                child = included(path, node).resolve()
                if child in temporary:
                    begin, end = node['argument_spans'][0]
                    edits.append((begin, end, json.dumps(str(temporary[child]))))
            temporary[key].write_text(replace(text, edits))
        result = subprocess.run([str(binary), 'validate', '--config', str(temporary[root.resolve()])],
                                capture_output=True, text=True, timeout=30)
        if result.returncode: raise ValueError('Staged niri validation failed:\n'+result.stdout+result.stderr)
    finally:
        for path in temporary.values(): path.unlink(missing_ok=True)
