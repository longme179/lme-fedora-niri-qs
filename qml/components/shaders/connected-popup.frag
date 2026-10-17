#version 440
// SPDX-License-Identifier: GPL-3.0-only
// Rounded-box SDF and circular smin adapted from Caelestia Blobs/blob.frag (a3a8fe59).
// Modified for two LME surfaces, a temporary connecting neck and theme borders.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 viewport;
    vec4 origin;
    vec4 popup;
    vec4 fillColor;
    vec4 borderColor;
    float popupRadius;
    float neckRadius;
    float smoothing;
};
float sdRoundedBox(vec2 p, vec2 center, vec2 halfSize, float radius) {
    vec2 d = abs(p - center) - halfSize + vec2(radius);
    return length(max(d, vec2(0.0))) + min(max(d.x, d.y), 0.0) - radius;
}
float smin(float a, float b, float k) {
    return max(k, min(a, b)) - length(max(vec2(k) - vec2(a, b), vec2(0.0)));
}
void main() {
    vec2 p = qt_TexCoord0 * viewport;
    float d = sdRoundedBox(p, popup.xy, max(popup.zw, vec2(0.1)), min(popupRadius,min(popup.z,popup.w)));
    if (neckRadius > 0.1) {
        float source = sdRoundedBox(p,origin.xy,max(origin.zw,vec2(0.1)),min(origin.z,origin.w));
        vec2 direction = popup.xy-origin.xy;
        float t = clamp(dot(p-origin.xy,direction)/max(dot(direction,direction),0.001),0.0,1.0);
        float neck = length(p-origin.xy-direction*t)-neckRadius;
        d = smin(smin(d,source,smoothing),neck,smoothing);
    }
    float aa = max(fwidth(d),0.65);
    float coverage = 1.0-smoothstep(-aa,aa,d);
    float edge = smoothstep(-1.6,-0.4,d);
    vec4 color = mix(fillColor,borderColor,edge*borderColor.a);
    float alpha = color.a*coverage*qt_Opacity;
    fragColor=vec4(color.rgb*alpha,alpha);
}
