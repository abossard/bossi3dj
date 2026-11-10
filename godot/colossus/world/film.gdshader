shader_type canvas_item;
// Film grain and vignette over the output frame (so Syphon carries them too).

uniform sampler2D screen : hint_screen_texture, filter_linear_mipmap;
uniform float grain : hint_range(0.0, 0.2) = 0.06;
uniform float vignette : hint_range(0.0, 1.0) = 0.45;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec3 c = texture(screen, SCREEN_UV).rgb;
	float n = hash(floor(FRAGCOORD.xy) + fract(TIME * 7.13) * 512.0) - 0.5;
	// Grain is strongest in the mid tones, like film.
	float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
	c += n * grain * (1.0 - abs(luma - 0.5) * 1.4);
	vec2 d = SCREEN_UV - 0.5;
	c *= 1.0 - vignette * smoothstep(0.25, 0.85, length(d * vec2(1.0, 0.82)));
	COLOR = vec4(c, 1.0);
}
