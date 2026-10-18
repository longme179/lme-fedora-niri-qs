// SPDX-License-Identifier: GPL-3.0-or-later
.pragma library

// Keep in sync with popup-jelly.vert (including its 16 x 16 triangle mesh).
function vertex(x, y, strain, horizontal, bounded) {
    const along = horizontal ? x : y, across = horizontal ? y : x;
    const stretch = 1 + .7 * Math.abs(strain);
    const bent = along * stretch + strain * .12 * (1 - 4 * across * across);
    const tapered = across / stretch * (1 + 1.3 * strain * along);
    const fit = bounded ? 1 + .94 * Math.abs(strain) : 1;
    return horizontal ? {x: bent / fit, y: tapered / fit} : {x: tapered / fit, y: bent / fit};
}

function warp(p, width, height, strain, horizontal, bounded) {
    const gx = Math.max(0, Math.min(16, p.x / width * 16));
    const gy = Math.max(0, Math.min(16, p.y / height * 16));
    const ix = Math.min(15, Math.floor(gx)), iy = Math.min(15, Math.floor(gy));
    const x = gx - ix, y = gy - iy;
    const a = vertex(ix / 16 - .5, iy / 16 - .5, strain, horizontal, bounded);
    const b = vertex((ix + 1) / 16 - .5, iy / 16 - .5, strain, horizontal, bounded);
    const c = vertex(ix / 16 - .5, (iy + 1) / 16 - .5, strain, horizontal, bounded);
    const d = vertex((ix + 1) / 16 - .5, (iy + 1) / 16 - .5, strain, horizontal, bounded);
    // QQuickGridMesh uses the a-d diagonal of each cell.
    const q = x >= y
        ? {x: a.x + x * (b.x - a.x) + y * (d.x - b.x), y: a.y + x * (b.y - a.y) + y * (d.y - b.y)}
        : {x: a.x + y * (c.x - a.x) + x * (d.x - c.x), y: a.y + y * (c.y - a.y) + x * (d.y - c.y)};
    return {x: (q.x + .5) * width, y: (q.y + .5) * height};
}

function outline(width, height, radii) {
    const points = [], limit = Math.min(width, height) / 2;
    const corners = [[width, 0, -Math.PI / 2], [width, height, 0], [0, height, Math.PI / 2], [0, 0, Math.PI]];
    for (let i = 0; i < 4; ++i) {
        const r = Math.max(0, Math.min(limit, radii[i]));
        const cx = corners[i][0] ? width - r : r, cy = corners[i][1] ? height - r : r;
        const arc = [];
        for (let k = 0; k <= 12; ++k) {
            const angle = corners[i][2] + k / 12 * Math.PI / 2;
            arc.push({x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle)});
        }
        if (points.length) line(points, arc[0]);
        points.push(...arc);
    }
    line(points, points[0]);
    return points;
}

function line(points, end) {
    const start = points[points.length - 1];
    // Sample straight edges too: the mesh bends them between their endpoints.
    for (let i = 1; i < 32; ++i) points.push({x: start.x + (end.x - start.x) * i / 32, y: start.y + (end.y - start.y) * i / 32});
}

function scanlines(points) {
    const edges = [];
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
        let a = points[j], b = points[i];
        if (a.y === b.y) continue;
        if (a.y > b.y) [a, b] = [b, a];
        edges.push({x: a.x, top: a.y, bottom: b.y, slope: (b.x - a.x) / (b.y - a.y)});
    }
    edges.sort((a, b) => a.top - b.top);
    let cursor = 0, active = [];
    // Scan in increasing y: only the edges crossing this row need evaluation.
    return function(y, hits) {
        hits.length = 0;
        while (cursor < edges.length && edges[cursor].top <= y) active.push(edges[cursor++]);
        let count = 0;
        for (let i = 0; i < active.length; ++i) {
            const edge = active[i];
            if (edge.bottom <= y) continue;
            active[count++] = edge;
            hits.push(edge.x + (y - edge.top) * edge.slope);
        }
        active.length = count;
        if (hits.length === 2) {
            if (hits[0] > hits[1]) [hits[0], hits[1]] = [hits[1], hits[0]];
        } else hits.sort((a, b) => a - b);
    };
}

function strips(points, width, height) {
    if (!points.length) return [];
    const result = [], top = Math.max(0, Math.ceil(Math.min(...points.map(p => p.y))));
    const bottom = Math.min(height, Math.floor(Math.max(...points.map(p => p.y))));
    const spans = scanlines(points);
    const topHits = [], middleHits = [], bottomHits = [];
    let previous = [];
    // Inset two-logical-pixel bands stay inside the antialiased silhouette.
    for (let y = top; y < bottom; y += 2) {
        const h = Math.min(2, bottom - y);
        spans(y + .001, topHits);
        spans(y + h / 2, middleHits);
        spans(y + h - .001, bottomHits);
        const current = [];
        let a = 0, b = 0, c = 0;
        while (a + 1 < topHits.length && b + 1 < middleHits.length && c + 1 < bottomHits.length) {
            const end = Math.min(topHits[a + 1], middleHits[b + 1], bottomHits[c + 1]);
            const left = Math.max(0, Math.ceil(Math.max(topHits[a], middleHits[b], bottomHits[c]) + .5));
            const right = Math.min(width, Math.floor(end - .5));
            if (topHits[a + 1] <= end) a += 2;
            if (middleHits[b + 1] <= end) b += 2;
            if (bottomHits[c + 1] <= end) c += 2;
            if (right <= left) continue;
            let match = null;
            for (const band of previous) {
                if (band.x === left && band.width === right - left && band.y + band.height === y) { match = band; break; }
            }
            if (match) { match.height += h; current.push(match); }
            else { const band = {x: left, y: y, width: right - left, height: h}; result.push(band); current.push(band); }
        }
        previous = current;
    }
    return result;
}
