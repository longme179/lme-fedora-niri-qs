// Role: KeybindsKdl.js (shared layer) — niri KDL tokenizer and node parser (Q4 session
// families).
// REL: scripts/niri_keybinds.py – tokens()/nodes() ported verbatim: the token classes
// (space, line, continuation, comment, block, disabled, raw, string, mark, word) with line
// numbers, raw strings (r#"..."#), block comments, KDL braced Unicode escapes decoded to
// JSON escapes, type annotations skipped by value, disabled (/-) nodes and the 32-level
// depth cap. Errors are thrown as the exact backend strings (KeybindsModel formats them).
// INVARIANT: token boundaries and reported line numbers match the Python module so error
// lines are byte-identical; string values are decoded (JSON escapes + \u{...} + \s).
.pragma library

// The Python TOKEN alternation, numbered by group: space, line, continuation, comment,
// block, disabled, raw (r?#+"), string, mark, word. Sticky so each match starts exactly at
// the cursor; a failed match is the "Invalid KDL near line" case.
var TOKEN = /([^\S\n]+)|(\n)|(\\\r?\n)|(\/\/[^\n]*)|(\/\*)|(\/-)|(r?#+")|(")|([{};=()])|([^\s{};=()"]+)/y;
var KINDS = ["space", "line", "continuation", "comment", "block", "disabled", "raw", "string", "mark", "word"];

function tokens(text) {
    const result = [];
    let offset = 0, line = 1;
    while (offset < text.length) {
        TOKEN.lastIndex = offset;
        const match = TOKEN.exec(text);
        if (!match || match.index !== offset) throw "Invalid KDL near line " + line;
        const begin = line;  // reported line numbers are the token's start line
        let kind = "";
        for (let index = 0; index < KINDS.length; index++)
            if (match[index + 1] !== undefined) { kind = KINDS[index]; break; }
        let value = match[0], end = offset + match[0].length;
        if (kind === "block") {
            let depth = 1, search = end;
            while (depth) {
                const open = text.indexOf("/*", search), close = text.indexOf("*/", search);
                if (close < 0) throw "Unclosed comment at line " + line;
                if (open >= 0 && open < close) { depth += 1; search = open + 2; }
                else { depth -= 1; search = close + 2; }
            }
            end = search;
        } else if (kind === "raw") {
            // The closing delimiter is '"' plus the same number of '#'.
            const closing = '"' + "#".repeat((match[0].match(/#/g) || []).length);
            const finish = text.indexOf(closing, end);
            if (finish < 0) throw "Unclosed raw string at line " + begin;
            value = text.slice(end, finish);
            end = finish + closing.length;
            kind = "rawvalue";
        } else if (kind === "string") {
            let finish = end;
            while (finish < text.length) {
                if (text[finish] === "\\") { finish += 2; continue; }
                if (text[finish] === '"') break;
                finish += 1;
            }
            if (finish >= text.length) throw "Unclosed string at line " + begin;
            value = decodeString(text.slice(offset, finish + 1));
            end = finish + 1;
        }
        line += (text.slice(offset, end).match(/\n/g) || []).length;
        if (["space", "comment", "block", "continuation"].indexOf(kind) < 0)
            result.push([value, kind === "rawvalue" ? "string" : kind, begin]);
        offset = end;
    }
    return result;
}

// KDL uses braced Unicode escapes in addition to JSON-style escapes; \s is a space. Other
// escapes pass through for JSON.parse, which rejects invalid ones exactly like the
// backend's json.loads does (the codepoint is re-escaped through JSON.stringify so quotes
// and backslashes stay quoted inside the literal).
function decodeString(literal) {
    const decoded = literal.replace(/\\u\{([0-9a-fA-F]{1,6})\}|\\s|\\./g, (whole, hex) => {
        if (hex !== undefined) return JSON.stringify(String.fromCodePoint(parseInt(hex, 16))).slice(1, -1);
        if (whole === "\\s") return " ";
        return whole;
    });
    return JSON.parse(decoded);
}

function nodes(text) {
    const stream = tokens(text);
    let index = 0;

    function parse(children, depth) {
        if (depth > 32) throw "KDL nesting is too deep";
        const output = [];
        while (index < stream.length) {
            let value = stream[index][0], kind = stream[index][1], line = stream[index][2];
            if (kind === "line" || value === ";") { index += 1; continue; }
            if (kind === "mark" && value === "}") {
                if (!children) throw "Unexpected closing brace at line " + line;
                index += 1;
                return output;
            }
            const disabled = kind === "disabled";
            if (disabled) {
                index += 1;
                if (index >= stream.length) throw "Missing disabled node";
                value = stream[index][0]; kind = stream[index][1]; line = stream[index][2];
            }
            if (kind !== "word" && kind !== "string") throw "Missing node name at line " + line;
            const node = {name: value, args: [], props: {}, children: [], line: line, disabled: disabled};
            index += 1;
            let skip = false;
            while (index < stream.length) {
                value = stream[index][0]; kind = stream[index][1];
                if (kind === "line" || (kind === "mark" && (value === ";" || value === "}"))) {
                    if (value !== "}") index += 1;
                    break;
                }
                if (kind === "mark" && value === "{") {
                    index += 1;
                    const nested = parse(true, depth + 1);
                    if (!skip) node.children = nested;
                    break;
                }
                if (kind === "disabled") { skip = true; index += 1; continue; }
                if (kind === "mark" && value === "(") {
                    while (index < stream.length && stream[index][0] !== ")") index += 1;
                    if (index >= stream.length) throw "Unclosed type annotation";
                    index += 1;
                    continue;
                }
                if (index + 1 < stream.length && stream[index + 1][0] === "=" && stream[index + 1][1] === "mark") {
                    const key = value;
                    index += 2;
                    if (index >= stream.length || (stream[index][1] !== "word" && stream[index][1] !== "string"))
                        throw "Missing property value";
                    if (!skip) node.props[key] = stream[index][0];
                } else if (!skip) {
                    node.args.push(value);
                }
                skip = false;
                index += 1;
            }
            output.push(node);
        }
        if (children) throw "Unclosed KDL block";
        return output;
    }

    return parse(false, 0);
}
