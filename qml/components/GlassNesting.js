// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Illia Miroshnichenko
// Adapted for LME hybrid glass; source and changes: third_party/Serpantinum-NOTICE.
.pragma library

function nestLevel(item, stopAt, countBackdrops) {
    let count = 0;
    // LME: the carrier is the child of this stratum that contains the walker.
    // A marked glass container counts through its own embedded layer, never as
    // itself, so content inside a glass panel is not counted twice.
    let carrier = item;
    let a = item.parent;
    let depth = 0;
    while (a && a !== stopAt && depth < 48) {
        const kids = a.children;
        if (kids) {
            for (let i = 0; i < kids.length; i++) {
                const k = kids[i];
                if (k && k !== carrier && ((countBackdrops && k.isGlassBackdrop === true && k.standalone !== true) || (k.isGlassFill === true && k.allowed === true))) {
                    count++;
                    break;
                }
            }
        }
        carrier = a;
        a = a.parent;
        depth++;
    }
    return count;
}
