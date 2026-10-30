"""Read-only niri bind viewer: KDL strings, comments, disabled nodes and includes."""
import json
import os
from pathlib import Path
import re

# shortcut: ordinary niri KDL only; use a full KDL library for v2 multiline strings or custom typed properties.
# Tokens retain line numbers for source links; braces inside strings stay strings.
TOKEN = re.compile(r'(?P<space>[^\S\n]+)|(?P<line>\n)|(?P<continuation>\\\r?\n)|(?P<comment>//[^\n]*)|(?P<block>/\*)|(?P<disabled>/-)|(?P<raw>r?#+"|r")|(?P<string>")|(?P<mark>[{};=()])|(?P<word>[^\s{};=()"]+)')


def tokens(text):
    result, offset, line = [], 0, 1
    while offset < len(text):
        match = TOKEN.match(text, offset)
        if not match: raise ValueError(f'Invalid KDL near line {line}')
        kind, value, begin = match.lastgroup, match.group(), line
        end = match.end()
        if kind == 'block':
            depth = 1
            while depth:
                marker = re.compile(r'/\*|\*/').search(text, end)
                if not marker: raise ValueError(f'Unclosed comment at line {begin}')
                depth += 1 if marker.group() == '/*' else -1
                end = marker.end()
        elif kind == 'raw':
            closing = '"' + ('#' * value.count('#'))
            finish = text.find(closing, end)
            if finish < 0: raise ValueError(f'Unclosed raw string at line {begin}')
            value, end, kind = text[end:finish], finish + len(closing), 'string'
        elif kind == 'string':
            finish = end
            while finish < len(text):
                if text[finish] == '\\': finish += 2; continue
                if text[finish] == '"': break
                finish += 1
            if finish == len(text): raise ValueError(f'Unclosed string at line {begin}')
            literal = text[offset:finish+1]
            # KDL uses braced Unicode escapes in addition to JSON-style escapes.
            literal = re.sub(r'\\(?:u\{([0-9a-fA-F]{1,6})\}|.)', lambda m: json.dumps(chr(int(m[1],16)))[1:-1] if m[1] else ' ' if m[0] == r'\s' else m[0], literal)
            try: value = json.loads(literal)
            except (ValueError, UnicodeError): raise ValueError(f'Invalid string at line {begin}') from None
            end = finish + 1
        line += text[offset:end].count('\n')
        if kind not in {'space', 'comment', 'block', 'continuation'}: result.append((value, kind, begin))
        offset = end
    return result


def nodes(text):
    stream, index = tokens(text), 0
    def parse(children=False, depth=0):
        nonlocal index
        if depth > 32: raise ValueError('KDL nesting is too deep')
        output = []
        while index < len(stream):
            value, kind, line = stream[index]
            if kind == 'line' or value == ';': index += 1; continue
            if kind == 'mark' and value == '}':
                if not children: raise ValueError(f'Unexpected closing brace at line {line}')
                index += 1; return output
            disabled = kind == 'disabled'
            if disabled:
                index += 1
                if index >= len(stream): raise ValueError('Missing disabled node')
                value, kind, line = stream[index]
            if kind not in {'word', 'string'}: raise ValueError(f'Missing node name at line {line}')
            node = {'name': value, 'args': [], 'props': {}, 'children': [], 'line': line, 'disabled': disabled}
            index += 1
            skip = False
            while index < len(stream):
                value, kind, _ = stream[index]
                if kind == 'line' or (kind == 'mark' and value in ';}'):
                    if value != '}': index += 1
                    break
                if kind == 'mark' and value == '{':
                    index += 1; nested = parse(True, depth+1)
                    if not skip: node["children"] = nested
                    break
                if kind == 'disabled': skip = True; index += 1; continue
                if kind == 'mark' and value == '(':
                    while index < len(stream) and stream[index][0] != ')': index += 1
                    if index == len(stream): raise ValueError('Unclosed type annotation')
                    index += 1; continue
                if index+1 < len(stream) and stream[index+1][0:2] == ('=', 'mark'):
                    key = value; index += 2
                    if index >= len(stream) or stream[index][1] not in {'word','string'}: raise ValueError('Missing property value')
                    if not skip: node['props'][key] = stream[index][0]
                elif not skip: node['args'].append(value)
                skip = False; index += 1
            output.append(node)
        if children: raise ValueError('Unclosed KDL block')
        return output
    return parse()


def read_keybinds(raw=''):
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
    root = Path(raw or os.environ.get('NIRI_CONFIG') or config/'niri/config.kdl').expanduser().resolve()
    if not root.is_file(): return {'path': str(root), 'bindings': [], 'errors': ['Niri config not found. Set its path below if you use --config.']}
    bindings, errors, visited = [], [], set()
    total = 0
    def visit(path, depth=0):
        nonlocal total
        path = path.resolve()
        if path in visited: return
        if depth > 12 or len(visited) >= 32: errors.append('Include limit reached (32 files / 12 levels).'); return
        visited.add(path)
        try:
            if path.stat().st_size > 512*1024: raise ValueError('Config exceeds 512 KiB')
            text = path.read_text(); total += len(text)
            if total > 2*1024*1024: raise ValueError('Included configs exceed 2 MiB')
            document = nodes(text)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f'{path.name}: {exc}'); return
        for node in document:
            if node['disabled']: continue
            if node['name'] == 'include' and node['args']:
                included = Path(node['args'][0]).expanduser()
                visit(included if included.is_absolute() else path.parent/included, depth+1)
            elif node['name'] == 'binds':
                for bind in node['children']:
                    if bind['disabled']: continue
                    actions = [n for n in bind['children'] if not n['disabled']]
                    command = '; '.join(n['name'] + (' ' + ' '.join(n['args']) if n['args'] else '') + ''.join(' '+key+'='+value for key,value in n['props'].items()) for n in actions)
                    title = bind['props'].get('hotkey-overlay-title') or command or 'No action'
                    bindings.append({'key': bind['name'], 'title': title, 'action': command,
                                     'source': str(path), 'line': bind['line']})
    visit(root)
    return {'path': str(root), 'bindings': bindings, 'errors': errors}
