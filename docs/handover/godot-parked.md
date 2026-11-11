# Godot Colossus Scene: parked on 2026-11-11

The user parked the scene: "lets park the godot stuff, it's too ugly to be honest". Nothing is built there until the user says so. This note is the one place to start from when it is picked up; the session notes it points to hold the detail.

## What works

| Area | State | Proof |
|---|---|---|
| Arc (Approach, Climb, Fall, Reset) and auto director | runs end to end | `make godot-test` (422), `make godot-smoke` |
| Controls | 22 of 22 with an effect, values persist, page on http 9211 with "Check all" and named shots | `make godot-check`, [godot-page-check-2026-11-11.json](../reports/godot-page-check-2026-11-11.json) |
| OSC | listens on udp 9201, the one scene port; 20 of 20 test packets applied live | [STATE.md](../../STATE.md) |
| Syphon | `COLOSSUS_OUT`, 1920x1080 with content | grab on 2026-11-11 |
| Real models | Nomad as Wanderer (Mixamo clips by runtime retarget, foot and hand IK, look-at), Grock as Colossus 1 (19 Grab Points, foot IK, 17-body ragdoll) | [godot-models.md](godot-models.md), [godot-model-cost.md](../reports/godot-model-cost.md) |
| Cost of the models | +0.08 to 0.48 ms over the stand-ins, 6 to 13 draw calls | same report, context only (load) |
| Look | round 5: 27 of 27 on the old rubric; round 6 on the rubric for the models: climb frames lit, low hero backs off, rock detail, eye glints, dust skirt | [godot-look-models.md](godot-look-models.md), [godot-look-verdict.json](../reports/godot-look-verdict.json) |
| Frame time | one run, load 20 to 55: context only; costliest at 4x pixels: SSIL, SDFGI, glow | [godot-fps.md](../reports/godot-fps.md) |

Models are not in git. [godot/colossus/assets/MODELS.md](../../godot/colossus/assets/MODELS.md) lists pages, licences and downloads; `make godot-models` prepares them from `~/Downloads`. Without them the scene runs on the stand-ins and every test passes.

## Why it is parked

The scene passes its checks and its rubrics, and the user still finds it too ugly. The rubrics measured readability (figures in frame, brightness, contrast in haze), not whether the picture is good. What the reviewers and numbers named, without it being the whole answer:

- far wide shot: the Colossus is 45 to 50 px at 1.6 km with nothing of known size in frame, so it does not read as a giant;
- climb frames sit on lifted blacks (contrast 0.85) and look flatter than the dusk;
- Grock is a game-ready model with a derived normal map; little surface detail at distance;
- the ruins (Shrine columns, fallen head) are stand-ins;
- climbing, hanging, falling and standing up run on fallbacks: seven Mixamo clips are not downloaded;
- the hand IK misses the grip by about 15 cm through a Shake.

## Open tasks, in the order I would take them

1. Decide the look target with the user before any code: reference images, and which shots must carry the piece. Without that a further round only moves numbers.
2. Art direction pass on light and atmosphere (sky, fog layers, colour grade), judged by the user on full frames, not by rubric.
3. Scale: something of known size with the Colossus in the wide shots (the Wanderer in frame, real ruins, birds, dust reaching its feet at distance).
4. Real ruins in place of the stand-ins (asset table in `godot/colossus/docs/SPEC.md`).
5. The seven Mixamo clips (Braced Hang, Right Braced Hang Shimmy, Climbing Up Wall, Climbing Down Wall, Hanging Idle, Falling Idle, Standing Up), then the hand IK through a Shake.
6. Colossus 2 and 3 (Titan: 302 joints, large textures; Golem: licence text unclear), see the cost report.
7. Frame-time table on an idle machine: `make godot-fps`.
8. A live run with Magic driving the scene (`magic/projects/show.magic` to udp 9201).

## Pick up

```bash
make godot-models      # only if assets/models is missing; needs the downloads
make godot-test && make godot-lint && make godot-check
make godot-open        # window, page on http://127.0.0.1:9211 (refuses while Blender runs)
make godot-look OUT=/tmp/look
make godot-fps FPS_OUT=docs/reports/godot-fps.json
```

Session notes, newest first: [godot-look-models.md](godot-look-models.md) (round 6, parked section), [godot-models.md](godot-models.md) (models, three stages), [godot-look-round2.md](godot-look-round2.md) (rounds 2 and 3, probes), [godot-control-page.md](godot-control-page.md) (page and self-check). Scene guide: [godot/colossus/docs/GUIDELINES.md](../../godot/colossus/docs/GUIDELINES.md).
