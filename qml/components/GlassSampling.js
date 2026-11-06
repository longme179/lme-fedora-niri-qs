// SPDX-License-Identifier: GPL-3.0-or-later
.pragma library

// Sample-resolution tier for the glass backdrop (Liquid Glass 2.0, gap A2):
// - 1x outputs keep the original half-resolution, 720p-capped sample.
// - Scaled outputs sample at up to a 1440p equivalent so the interior LOD blur
//   does not read blocky at 2x, but never beyond the output's physical
//   resolution (the scale factor is the natural ceiling).
// Battery saver needs no extra gate here: it already disables glass entirely
// (Theme.liquidGlass is false, no backdrop is ever acquired).
function resolution(width, height, scale) {
    if (scale > 1) return Math.min(scale, 2560 / Math.max(1, width), 1440 / Math.max(1, height));
    return Math.min(.5, 1280 / Math.max(1, width), 720 / Math.max(1, height));
}
