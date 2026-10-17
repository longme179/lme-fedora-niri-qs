#version 440
// SPDX-License-Identifier: GPL-3.0-or-later
layout(location = 0) in vec4 qt_Vertex;
layout(location = 1) in vec2 qt_MultiTexCoord0;
layout(location = 0) out vec2 qt_TexCoord0;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float strain;
    float horizontal;
    float fit;
    vec2 sizePx;
} u;
void main() {
    qt_TexCoord0 = qt_MultiTexCoord0;
    vec2 p = qt_Vertex.xy / max(u.sizePx, vec2(1.0)) - vec2(0.5);
    float along = mix(p.y, p.x, u.horizontal);
    float across = mix(p.x, p.y, u.horizontal);
    float stretch = 1.0 + 0.7 * abs(u.strain);
    // Taper the trailing side and bow the edges, with bounded positive scale.
    float bent = along * stretch + u.strain * 0.12 * (1.0 - 4.0 * across * across);
    float tapered = across / stretch * (1.0 + 1.3 * u.strain * along);
    vec2 warped = mix(vec2(tapered, bent), vec2(bent, tapered), u.horizontal);
    // Stretch (0.7) plus twice the bow (0.12) bounds displacement in tight surfaces.
    warped /= mix(1.0, 1.0 + 0.94 * abs(u.strain), u.fit);
    vec4 vertex = qt_Vertex;
    vertex.xy += (warped - p) * u.sizePx;
    gl_Position = u.qt_Matrix * vertex;
}
