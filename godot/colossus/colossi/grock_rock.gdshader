shader_type spatial;
// Grock's own albedo, normal map and roughness, with rock detail on top that holds at any distance:
// a tiling rock normal map projected from the three axes of the model (so it needs no UV and
// does not stretch on the back or the head) and a slow rock colour variation. Both fade out far
// away (the mips already lose them) and both are off at strength 0.
render_mode fog_disabled;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D rough_tex : hint_default_white, filter_linear_mipmap_anisotropic;
// RGB is a plain tangent-space normal map, alpha is roughness (the terrain's rock).
uniform sampler2D detail_tex : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tint_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
// 1 uses the model's normal map, 0 a flat one.
uniform float model_normal : hint_range(0.0, 1.0) = 1.0;
uniform float detail_strength : hint_range(0.0, 4.0) = 1.5;
// Tiles per metre of the detail normal map and of the colour variation.
uniform float detail_scale = 0.18;
uniform float tint_scale = 0.03;
uniform float tint_strength : hint_range(0.0, 1.0) = 0.6;
// The rock colour map's mean luma (linear), so the variation brightens and darkens round 1.
uniform float tint_mean = 0.075;
// The detail fades between these view distances (m).
uniform vec2 fade = vec2(500.0, 1800.0);

varying vec3 obj_pos;
varying vec3 obj_normal;

vec3 weights(vec3 n) {
	vec3 w = pow(abs(n), vec3(4.0));
	return w / (w.x + w.y + w.z + 1e-5);
}

void vertex() {
	obj_pos = VERTEX;
	obj_normal = NORMAL;
}

void fragment() {
	vec3 base = texture(albedo_tex, UV).rgb;
	vec3 w = weights(normalize(obj_normal));
	vec2 nx = texture(detail_tex, obj_pos.zy * detail_scale).xy * 2.0 - 1.0;
	vec2 ny = texture(detail_tex, obj_pos.xz * detail_scale).xy * 2.0 - 1.0;
	vec2 nz = texture(detail_tex, obj_pos.xy * detail_scale).xy * 2.0 - 1.0;
	// Each projection's slope, as a push on the object-space normal.
	vec3 push = vec3(0.0, nx.y, nx.x) * w.x + vec3(ny.x, 0.0, ny.y) * w.y + vec3(nz.x, nz.y, 0.0) * w.z;
	float near = 1.0 - smoothstep(fade.x, fade.y, length(VERTEX));
	vec3 push_view = normalize(mat3(VIEW_MATRIX) * mat3(MODEL_MATRIX) * push) * length(push);
	vec2 base_xy = (texture(normal_tex, UV).xy * 2.0 - 1.0) * model_normal;
	vec2 detail_xy = vec2(dot(push_view, TANGENT), dot(push_view, BINORMAL)) * detail_strength * near;
	NORMAL_MAP = vec3((base_xy + detail_xy) * 0.5 + 0.5, 0.0);
	// Colour: the model's own, varied by the rock's, a little.
	vec3 rock = vec3(0.0);
	rock += texture(tint_tex, obj_pos.zy * tint_scale).rgb * w.x;
	rock += texture(tint_tex, obj_pos.xz * tint_scale).rgb * w.y;
	rock += texture(tint_tex, obj_pos.xy * tint_scale).rgb * w.z;
	float rock_luma = dot(rock, vec3(0.2126, 0.7152, 0.0722));
	float variation = clamp(rock_luma / tint_mean, 0.5, 2.0);
	ALBEDO = base * mix(1.0, variation, tint_strength * near);
	ROUGHNESS = texture(rough_tex, UV).r;
}
