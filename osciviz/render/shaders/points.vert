#version 410 core
// Cząsteczki: pozycja lokalna warstwy → scena (u_model) → ekran (u_view).
uniform mat3 u_view;
uniform mat3 u_model;
uniform float u_point_size; // średnica w pikselach framebuffera

in vec2 in_pos;
in vec4 in_color;
out vec4 v_color;

void main() {
    vec3 p = u_view * (u_model * vec3(in_pos, 1.0));
    gl_Position = vec4(p.xy, 0.0, 1.0);
    gl_PointSize = u_point_size;
    v_color = in_color;
}
