/*{
  "DESCRIPTION": "Light trails over the live frame: each pixel is the brighter of the input and the fading, slightly zoomed history, so the picture never gets darker than its input.",
  "CATEGORIES": ["Feedback"],
  "INPUTS": [
    { "NAME": "inputImage", "TYPE": "image" },
    { "NAME": "amount", "TYPE": "float", "MIN": 0.0, "MAX": 1.0, "DEFAULT": 0.5 },
    { "NAME": "zoom", "TYPE": "float", "MIN": 0.0, "MAX": 1.0, "DEFAULT": 0.2 }
  ],
  "PASSES": [
    { "TARGET": "history", "PERSISTENT": true, "FLOAT": true },
    {}
  ]
}*/

void main()
{
	vec2 uv = gl_FragCoord.xy / RENDERSIZE.xy;
	if (PASSINDEX == 0) {
		vec4 live = IMG_THIS_PIXEL(inputImage);
		// Sample the history slightly toward the centre so trails drift outward; clamp keeps the edges filled.
		vec2 warp = clamp((uv - 0.5) * (1.0 - zoom * 0.01) + 0.5, 0.0, 1.0);
		vec3 past = IMG_NORM_PIXEL(history, warp).rgb * mix(0.80, 0.97, amount);
		gl_FragColor = vec4(max(live.rgb, past), 1.0);
	} else {
		gl_FragColor = vec4(IMG_THIS_PIXEL(history).rgb, 1.0);
	}
}
