# Godot Colossus Scene: look round 6 with the real models

Branch `integration/presentable`, main checkout. Rubric (frozen first): [godot/colossus/docs/look-rubric-models.md](../../godot/colossus/docs/look-rubric-models.md). Verdicts: round `godot-look-6` in [docs/reports/godot-look-verdict.json](../reports/godot-look-verdict.json). Sheet: [godot-look-round6.jpg](../images/2026-11-11/godot-look-round6.jpg), before: [godot-look-round5-before.jpg](../images/2026-11-11/godot-look-round5-before.jpg) (grabbed at the start of this session on the round 5 code, the old grabs were gone).

## State, Part 1 (look)

- Climb frames lit: `Shots.look` gives the over-shoulder and close grip shots on the Colossus a lamp on the camera (3.0, cool, from above), exposure x1.5 and contrast 0.85; the Director settles it over 0.5 s, Main passes exposure and contrast to the World. Real frames: over-shoulder luma 38.2 to 69.6, close grip 24.7 to 65.3, near black 30 % and 35 % to 0 %. Dusk of `shot-1` kept: luma 138.9 to 141.3, variance 491 to 423 (rubric: within 10, at least 393).
- Low hero on the long walk: `Director._long_walk` backs the camera off (up to 48 m) until the Wanderer takes at most 28 % of the frame height. At 1000 and 450 m: 526 px (49 %) to 295 px (27 %), whole in frame, no overlap with the Colossus (side gap 118 and 31 px).
- Grock: `colossi/grock_rock.gdshader` (own textures, triplanar rock normal at 0.04 tiles per metre, strength 6, and rock colour variation), eye glints on the head bone (two emissive discs, 1.2 m), a dust skirt (FogVolume, density 0.15, pale) at the feet of every Colossus. Surface detail energy in the body box (Laplacian, grain off): flat normal 3.2, model normal 3.8, product 4.6 at 150 m; 3.9, 4.5, 5.8 at 450 m. Dust skirt: feet region luma +7 at 150 m, no effect at 450 m (volumetric fog is 250 m long). Glints: 280 bright px at the head at 150 m (0 without). The model's derived normal map darkens the climb frames (near black 5 % against 1 % with a flat one) and adds 20 % detail energy: kept, the lamp pays for it.
- Scale wide shot: a lamp of 1.5 (`WIDE_LAMP`) lights the giant's front. Not enough: see Open.
- Shake-off with Attack and Defend: not kept. `make godot-shake-clips` (three grips): hands from their IK target, median 0.00 to 0.17 m, p95 0.07 to 0.28 m for every clip and for the current roll (p95 0.21 to 0.28 m), none under 5 cm; Defend1 throws the grip 9 to 12 m at 70 to 87 m/s; Attack1 is closest (p95 0.07 m on a low grip, 0.22 m higher up). The Shake stays as it was. The hand IK already misses the grip by about 15 cm while he hangs through the roll Shake: a Wanderer-side issue, not the clip. The knob `GrockColossus.shake_clip` (default "") stays for the probe.

## Cost (each against its own A/B in one run, vsync off, median ms, load 42 to 54, `fps_trustworthy` false)

| Change | Probe | Result |
|---|---|---|
| shot look (lamp, exposure, contrast) | `make godot-climb-light`, 3 rounds | over-shoulder 8.12 with, 8.17 without; close grip 8.14, 8.11: 0.0 ms |
| rock shader and tint | `make godot-climb-light`, `make godot-grock-detail` | 8.07 to 8.18 either way: 0.0 ms |
| dust skirt | `make godot-grock-detail` | 8.29 on, 8.45 off at 150 m: 0.0 ms |
| eye glints | `make godot-grock-detail` | 8.29 with, 8.42 without: 0.0 ms |
| hero back-off | camera only | none |
| whole scene, `make godot-model-cost`, models minus the empty view in the same run, before then after | close 0.05 to 0.08, medium 0.48 to -0.10, long walk 0.30 to 0.29 | none above 0.3 |

Medians on this machine sit at 8.1 to 8.5 ms (a 120 Hz floor: Metal keeps the display link with vsync off), so a change under that floor does not show. The wide lamp was not priced separately (the same lamp node as the climb one).

## Proof (final code)

`make godot-test` 411, `make godot-lint`, `make godot-check` 22 effect 0 error, `make godot-framing` exit 0 twice (one earlier run read 28 of 30 on the close grip through a Shake and exit 2, under load straight after the capture; two reruns 30 of 30), `make godot-hitch` worst frame 24 ms (limit 50), medians 16.7 ms. Not rerun without the models folder after the last change (the new code paths are behind the model checks; the shot look and tests run on stand-ins).

## Open

- `giant-scale` on the far wide frames (shot-1, fog and intensity frames, 1-approach-scale-wide): at 1.6 km the Colossus is 45 to 50 px, a dark figure with a lit edge, and the telephoto frame holds nothing of known size. Reviewer: "No known-size cue: no Wanderer, columns or feet dust, and the haze is a uniform sepia wash". Ideas not tried: the wide shot keeps the Wanderer in the lower corner (wider lens, giant smaller), a dust or haze layer at the giant's feet that reaches 1.6 km (the fog volume is 250 m), Shrine columns in frame at the start.
- `horizon-fog` on shot-2 and 2-approach-low-hero failed once (hard edge); passed in round 5 on the same camera: reviewer variance.
- Hand IK misses the grip by about 15 cm through the existing Shake.
- Climb frames now sit on lifted blacks (contrast 0.85): the look of the climb is flatter than the dusk; the user may want it between.

## Commands

```bash
make godot-climb-light               # Metal: luma, near black and frame time of the climb shots per variant
make godot-grock-detail OUT=<dir>    # Metal: detail energy, dust skirt and glints per variant, frames
make godot-shake-clips ARGS=<s>      # headless: Attack/Defend clips as a Shake, hands from IK target
make godot-wanderer-read OUT=<dir>   # Metal: low hero, Wanderer share of the frame, overlap
tools/godot_look_sheet.sh OUT.jpg LOOK_DIR CAPTURE_DIR READ_DIR
blender/review/named_sheet.sh OUT.png 3 <png>...   # 480 px tiles for the shot-reviewer
```

## README pictures (for the OSC manual)

- `make godot-readme-pics OUT=<dir> [ARGS=names]` then `tools/godot_readme_pics.sh <dir> docs/images/readme/osc`; pairs checked with `tools/png_pair_diff.py` (mean luma difference, share of pixels over 12 luma; film grain alone gives about 3.5 and 0.2 %).
- Kept: `level`, `intensity`, `fog`, `fog_height`, `haze`, `shock` as `<name>-godot.jpg` (480 px halves), `cam-godot.jpg` strip and `cam-godot-0..4.jpg`. Differences: level 35.8 / 91 %, intensity 109.9 / 95 %, fog 53.4 / 88 %, fog_height 21.5 / 28 %, haze 5.8 / 11 % (shot 0 at 1550 m), shock 28.1 / 67 %. Reviewer: intensity, fog, fog_height clearly visible; level (sun glow, wire 0 to 1 is only 1.0 to 2.6 light energy), haze and shock (a still of a Shake) weak by eye.
- Left out: `bass` and `beat`: the footfall dust at weight 0.5 against 1.0 (and none against a puff) differs by 3.4 luma on 0.2 % of the pixels, the film grain's floor, in the low hero shot 28 m from the foot.
- Single frames at 1280 px in `docs/images/readme/colossus-*.jpg`, the reviewer's top eight of the final look.
