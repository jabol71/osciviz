#version 410 core
// Nałożenie obrazu warstwy (i jej poświaty) na scenę. Kolory są z premnożoną
// alfą, więc krycie warstwy to po prostu mnożenie całego wektora RGBA.
uniform sampler2D u_image;
uniform sampler2D u_glow;
uniform float u_opacity;
uniform float u_glow_strength;

in vec2 v_uv;
out vec4 f_color;

void main() {
    vec4 c = texture(u_image, v_uv);
    vec4 g = texture(u_glow, v_uv) * u_glow_strength;
    // Poświata dodaje światło: zwiększa RGB i (słabiej) krycie.
    vec4 outc = c + vec4(g.rgb, g.a * 0.5);
    f_color = clamp(outc, 0.0, 64.0) * u_opacity;
}
