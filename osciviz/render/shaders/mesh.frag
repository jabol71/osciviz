#version 410 core
// Kolor linii: gradient między color1 i color2 wzdłuż u, miękka krawędź
// w poprzek paska (v = ±1 to brzegi) — linia wygląda gładko nawet bez MSAA.
uniform vec4 u_color1;
uniform vec4 u_color2;
uniform float u_feather; // 0 = ostre krawędzie (słupki), >0 = szerokość wygładzenia

in vec2 v_uv;
in float v_alpha;
out vec4 f_color;

void main() {
    vec4 c = mix(u_color1, u_color2, clamp(v_uv.x, 0.0, 1.0));
    float edge = 1.0;
    if (u_feather > 0.0) {
        edge = 1.0 - smoothstep(1.0 - u_feather, 1.0, abs(v_uv.y));
    }
    float a = c.a * v_alpha * edge;
    f_color = vec4(c.rgb * a, a); // kolor z premnożoną alfą
}
