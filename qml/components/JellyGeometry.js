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

function spans(points, y) {
    const hits = [];
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
        const a = points[j], b = points[i];
        if ((a.y <= y && b.y > y) || (b.y <= y && a.y > y)) hits.push(a.x + (y - a.y) / (b.y - a.y) * (b.x - a.x));
    }
    hits.sort((a, b) => a - b);
    const result = [];
    for (let i = 0; i + 1 < hits.length; i += 2) result.push([hits[i], hits[i + 1]]);
    return result;
}

function intersect(a, b) {
    const result = [];
    for (const x of a) for (const y of b) {
        const left = Math.max(x[0], y[0]), right = Math.min(x[1], y[1]);
        if (right > left) result.push([left, right]);
    }
    return result;
}

function strips(points, width, height) {
    if (!points.length) return [];
    const result = [], top = Math.max(0, Math.ceil(Math.min(...points.map(p => p.y))));
    const bottom = Math.min(height, Math.floor(Math.max(...points.map(p => p.y))));
    // Inset two-logical-pixel bands stay inside the antialiased silhouette.
    for (let y = top; y < bottom; y += 2) {
        const h = Math.min(2, bottom - y);
        let row = intersect(spans(points, y + .001), spans(points, y + h - .001));
        row = intersect(row, spans(points, y + h / 2));
        for (const span of row) {
            const left = Math.max(0, Math.ceil(span[0] + .5)), right = Math.min(width, Math.floor(span[1] - .5));
            if (right > left) result.push({x: left, y: y, width: right - left, height: h});
        }
    }
    return result;
}
