// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Avenge Media LLC
// overlap test adapted from DMS Common/GridLayout.js; see THIRD_PARTY.md.
.pragma library

function overlaps(taken, x, y, w) {
    return taken.some(cell => x < cell.col + cell.cols && cell.col < x + w && cell.row === y);
}

// Bound the search to the selected canvas. Wide controls settle before single toggles.
function move(layout, tiles, id, col, row, columns, rows, preserve = true) {
    const widths = {};
    tiles.forEach(tile => widths[tile.id] = tile.cols);
    if (!layout.some(tile => tile.id === id) || row < 0 || row >= rows || col < 0 || col + widths[id] > columns)
        return null;
    const origin = layout.find(tile => tile.id === id);
    if (origin.col === col && origin.row === row) return layout;
    const taken = [{id: id, col: col, row: row, cols: widths[id]}];
    const others = layout.filter(tile => tile.id !== id).slice().sort((a, b) => widths[b.id] - widths[a.id]);
    for (const tile of others) {
        const w = widths[tile.id];
        let position = preserve && !overlaps(taken, tile.col, tile.row, w) ? {col: tile.col, row: tile.row} : null;
        if (preserve && !position && origin.col + w <= columns && !overlaps(taken, origin.col, origin.row, w))
            position = {col: origin.col, row: origin.row};
        for (let y = 0; !position && y < rows; y++) {
            for (let x = 0; !position && x + w <= columns; x++) {
                if (!overlaps(taken, x, y, w)) position = {col: x, row: y};
            }
        }
        if (!position) return preserve ? move(layout, tiles, id, col, row, columns, rows, false) : null;
        taken.push({id: tile.id, col: position.col, row: position.row, cols: w});
    }
    return layout.map(tile => {
        const place = taken.find(cell => cell.id === tile.id);
        return {id: tile.id, col: place.col, row: place.row};
    });
}

function pack(tiles, columns) {
    const result = [];
    let col = 0, row = 0;
    for (const tile of tiles) {
        if (col + tile.cols > columns) { col = 0; row++; }
        result.push({id: tile.id, col: col, row: row});
        col += tile.cols;
    }
    return result;
}
