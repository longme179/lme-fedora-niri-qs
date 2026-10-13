// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Avenge Media LLC
// overlap test adapted from DMS Common/GridLayout.js; see THIRD_PARTY.md.
.pragma library

function overlaps(taken, x, y, w) {
    return taken.some(cell => x < cell.col + cell.cols && cell.col < x + w && cell.row === y);
}

// Move one tile or swap two matching footprints; never reflow unrelated controls.
function move(layout, tiles, id, col, row, columns, rows) {
    const widths = {};
    tiles.forEach(tile => widths[tile.id] = tile.cols);
    const origin = layout.find(tile => tile.id === id);
    if (!origin || row < 0 || row >= rows || col < 0 || col + widths[id] > columns) return null;
    const collisions = layout.filter(tile => tile.id !== id
        && overlaps([{col: tile.col, row: tile.row, cols: widths[tile.id]}], col, row, widths[id]));
    const swap = collisions.length === 1 ? collisions[0] : null;
    if (collisions.length && (!swap || widths[swap.id] !== widths[id] || swap.col !== col || swap.row !== row)) return null;
    return layout.map(tile => tile.id === id ? {id: id, col: col, row: row}
        : swap && tile.id === swap.id ? {id: tile.id, col: origin.col, row: origin.row} : tile);
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
