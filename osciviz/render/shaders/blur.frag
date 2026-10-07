#version 410 core
// Jeden przebieg rozmycia Gaussa (poziomy albo pionowy — zależnie od u_dir).
// Rozmycie 2D Gaussa jest separowalne: blur(x) potem blur(y) daje to samo co
// pełne jądro 2D, a kosztuje 2·N zamiast N² próbek.
uniform sampler2D u_tex;
uniform vec2 u_dir;    // (1/szerokość, 0) albo (0, 1/wysokość) — krok jednego teksela
uniform float u_sigma; // odchylenie standardowe w tekselach

in vec2 v_uv;
out vec4 f_color;

const int TAPS = 12;

void main() {
    // Próbki rozkładamy co sigma/4 tekseli w zakresie ±3σ.
    float step_px = max(u_sigma / 4.0, 0.5);
    vec4 sum = vec4(0.0);
    float wsum = 0.0;
    for (int i = -TAPS; i <= TAPS; ++i) {
        float x = float(i) * step_px;               // odległość w tekselach
        float w = exp(-0.5 * (x * x) / (u_sigma * u_sigma)); // waga Gaussa
        sum += texture(u_tex, v_uv + u_dir * x) * w;
        wsum += w;
    }
    f_color = sum / wsum;
}
