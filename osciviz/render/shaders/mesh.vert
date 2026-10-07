#version 410 core
// Wierzchołek siatki linii/słupków. Pozycja jest już w układzie sceny
// (transformację warstwy policzył CPU), więc mnożymy tylko przez macierz
// widoku: scena → współrzędne znormalizowane ekranu (NDC).
uniform mat3 u_view;

in vec2 in_pos;    // pozycja w układzie sceny
in vec2 in_uv;     // u: położenie wzdłuż linii [0,1] (gradient), v: strona paska [-1,1]
in float in_alpha; // krycie wierzchołka (np. kopie fali, zanikający ślad XY)

out vec2 v_uv;
out float v_alpha;

void main() {
    vec3 p = u_view * vec3(in_pos, 1.0);
    gl_Position = vec4(p.xy, 0.0, 1.0);
    v_uv = in_uv;
    v_alpha = in_alpha;
}
