#version 410 core
// Persistence (powidok) oscyloskopu XY: poprzednia klatka akumulacji
// przemnożona przez u_decay < 1 — stare ślady stopniowo gasną.
uniform sampler2D u_tex;
uniform float u_decay;

in vec2 v_uv;
out vec4 f_color;

void main() {
    f_color = texture(u_tex, v_uv) * u_decay;
}
