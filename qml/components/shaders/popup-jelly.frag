#version 440
// SPDX-License-Identifier: GPL-3.0-or-later
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float strain;
    float horizontal;
    float fit;
    vec2 sizePx;
} u;
layout(binding = 1) uniform sampler2D source;
void main() { fragColor = texture(source, qt_TexCoord0) * u.qt_Opacity; }
