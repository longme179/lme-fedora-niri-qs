// SPDX-License-Identifier: MIT
// Copyright (c) 2025-2026 Avenge Media LLC
// Adapted from DCommon wave_progress.frag at 50ca5ccb; no seek preview, inset endpoints.
#version 450

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float widthPx;
    float heightPx;
    float value;
    float phase;
    float ampPx;
    float wavelengthPx;
    float lineWidthPx;
    vec4 fillColor;
    vec4 trackColor;
} ubuf;

const float TAU = 6.28318530718;
const float AA = 0.75;

float sdRoundBar(vec2 p, vec2 halfSize, float r) {
    vec2 q = abs(p) - halfSize + vec2(r);
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

vec4 blendOver(vec4 dst, vec3 rgb, float a) {
    return vec4(rgb * a + dst.rgb * (1.0 - a), a + dst.a * (1.0 - a));
}

void main() {
    vec2 px = qt_TexCoord0 * vec2(ubuf.widthPx, ubuf.heightPx);
    float mid = ubuf.heightPx * 0.5;
    float halfW = ubuf.lineWidthPx * 0.5;
    float k = TAU / max(ubuf.wavelengthPx, 1e-3);
    // Keep the full playhead visible at both 0% and 100%.
    float startX = 4.0;
    float endX = max(startX, ubuf.widthPx - 4.0);
    float playX = mix(startX, endX, clamp(ubuf.value, 0.0, 1.0));
    float ang = k * px.x + ubuf.phase;
    float wy = mid + ubuf.ampPx * sin(ang);
    float slope = ubuf.ampPx * k * cos(ang);
    float dWave = abs(px.y - wy) / sqrt(1.0 + slope * slope);
    float waveStroke = 1.0 - smoothstep(halfW - AA, halfW + AA, dWave);
    float lineStroke = 1.0 - smoothstep(halfW - AA, halfW + AA, abs(px.y - mid));
    vec4 col = vec4(0.0);

    float trackMask = lineStroke * step(playX, px.x) * step(px.x, endX);
    col = blendOver(col, ubuf.trackColor.rgb, ubuf.trackColor.a * trackMask);
    if (playX > startX) {
        float m = waveStroke * step(startX, px.x) * step(px.x, playX);
        float capS = length(px - vec2(startX, mid + ubuf.ampPx * sin(k * startX + ubuf.phase))) - halfW;
        m = max(m, 1.0 - smoothstep(-AA, AA, capS));
        col = blendOver(col, ubuf.fillColor.rgb, ubuf.fillColor.a * m);
    }

    float phW = 3.5;
    float phH = max(ubuf.lineWidthPx + 12.0, 16.0);
    float d = sdRoundBar(px - vec2(playX, mid), vec2(phW * 0.5, phH * 0.5), phW * 0.5);
    col = blendOver(col, ubuf.fillColor.rgb, ubuf.fillColor.a * (1.0 - smoothstep(-AA, AA, d)));
    fragColor = col * ubuf.qt_Opacity;
}
