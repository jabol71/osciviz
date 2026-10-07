#version 410 core
// Okrągły punkt z miękką krawędzią. gl_PointCoord to współrzędne wewnątrz
// kwadratu punktu w [0,1]; odległość od środka > 0.5 = poza kołem.
uniform float u_brightness;
uniform float u_opacity;

in vec4 v_color;
out vec4 f_color;

void main() {
    float d = length(gl_PointCoord - vec2(0.5)) * 2.0; // 0 w środku, 1 na brzegu
    float a = (1.0 - smoothstep(0.55, 1.0, d)) * v_color.a * u_opacity;
    if (a <= 0.001) discard;
    f_color = vec4(v_color.rgb * u_brightness * a, a);
}
