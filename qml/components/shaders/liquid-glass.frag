#version 440
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Illia Miroshnichenko
// Adapted for LME simple glass; source and changes: third_party/Serpantinum-NOTICE.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 itemSize;
    vec4 radii;
    vec4 tintColor;
    float bezel;
    float rim;
    float tintAmount;
    float glassPad;
    float shadowAmt;
    float nest;
    vec4 fillet;
    vec4 box;
    float filletInset;
    float panelOpacity;
    float grain;
};

const vec2 lightDir = vec2(-0.55, -0.83);

float sdRoundBox(vec2 p, vec2 b, vec4 r) {
    float rad = p.x > 0.0 ? (p.y > 0.0 ? r.z : r.y) : (p.y > 0.0 ? r.w : r.x);
    rad = min(rad, min(b.x, b.y));
    vec2 q = abs(p) - b + rad;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - rad;
}

vec2 boxHalf() {
    return box.z > 0.0 ? box.zw : itemSize * 0.5;
}

float sdfCard(vec2 p) {
    return sdRoundBox(p - box.xy, boxHalf() - glassPad, radii);
}

float sdfPlane(vec2 p) {
    vec2 h = boxHalf();
    return abs(fillet.x) * h.x + abs(fillet.y) * h.y - dot(p - box.xy, fillet.xy) - filletInset;
}

float sdf(vec2 p) {
    float a = sdfCard(p);
    if (fillet.z <= 0.0) return a;
    float b = sdfPlane(p);
    float r = fillet.z;
    vec2 u = max(vec2(r - a, r - b), vec2(0.0));
    return max(r, min(a, b)) - length(u);
}

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void main() {
    vec2 p = qt_TexCoord0 * itemSize - itemSize * 0.5;
    float dist = sdf(p);
    if (fillet.w > 0.5 && (sdfCard(p) < 0.0 || sdfPlane(p) < 0.0)) {
        fragColor = vec4(0.0);
        return;
    }
    float coverage = clamp(0.5 - dist, 0.0, 1.0);
    float shadow = 0.13 * shadowAmt * (1.0 - smoothstep(-2.0, 9.0, sdf(p - vec2(0.0, 3.0))));
    if (dist > 1.0) {
        fragColor = vec4(0.0, 0.0, 0.0, shadow) * qt_Opacity;
        return;
    }

    float t = max(-dist, 0.0);
    float bz = max(bezel, 1.0) * 1.45;
    vec2 g = vec2(0.0, -1.0);
    if (t < bz + 2.0) {
        const vec2 e = vec2(0.75, 0.0);
        vec2 grad = vec2(sdf(p + e.xy) - sdf(p - e.xy), sdf(p + e.yx) - sdf(p - e.yx));
        if (length(grad) > 0.0001) g = normalize(grad);
    }

    vec2 L = normalize(lightDir);
    float facing = dot(g, L);
    float spec = pow(max(facing, 0.0), 1.6) + 0.55 * pow(max(-facing, 0.0), 2.2);
    float hair = exp(-t / 1.1);
    float wide = exp(-t / 5.0);
    float edgeHi = (hair * (0.18 + 0.78 * spec) + wide * 0.10 * (0.30 + spec)) * rim * (1.0 - 0.35 * nest);
    float broad = exp(-t / (bz * 0.45)) * pow(max(facing, 0.0), 2.0) * 0.2 * rim * (1.0 - 0.35 * nest);
    float mx = (t - bz * 0.5) / (bz * 0.2 + 1.0);
    float men = exp(-mx * mx) * 0.07 * (0.35 + spec) * rim;
    vec3 light = vec3(edgeHi + men + broad);

    vec3 tcol = tintColor.rgb;
    float B = clamp(tintAmount * 0.85, 0.0, 0.15);
    float A = clamp(B + panelOpacity * 0.75, 0.0, 0.92);
    vec3 premul = tcol * A + light;

    float gn = hash12(gl_FragCoord.xy) + hash12(gl_FragCoord.xy * 1.7 + 17.0) - 1.0;
    premul += vec3(gn * grain * (1.0 - 0.7 * nest)) * A;

    float a = coverage * qt_Opacity;
    float outA = clamp(A + dot(light, vec3(0.3333)), 0.0, 1.0) * coverage + shadow * (1.0 - coverage);
    fragColor = vec4(clamp(premul, 0.0, 1.0) * a, clamp(outA, 0.0, 1.0) * qt_Opacity);
}
