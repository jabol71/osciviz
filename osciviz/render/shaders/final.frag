#version 410 core
// Ostatni przebieg: scena (premnożona alfa) → ekran/plik. Delikatne
// mapowanie tonów „Reinhard” na nadmiarze jasności, żeby silna poświata
// nie przepalała się w płaskie białe plamy.
uniform sampler2D u_image;
in vec2 v_uv;
out vec4 f_color;

void main() {
    vec4 c = texture(u_image, v_uv);
    vec3 rgb = c.rgb;
    float peak = max(max(rgb.r, rgb.g), rgb.b);
    if (peak > 1.0) {
        rgb *= (1.0 + (peak - 1.0) / (1.0 + (peak - 1.0))) / peak;
    }
    f_color = vec4(rgb, clamp(c.a, 0.0, 1.0));
}
