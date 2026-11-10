# Look rubric, Colossus Scene (frozen for the round it is used in)

Judged on 480 px tiles of the output frame (what Syphon carries). A new wish starts the next round and does not change this bar. Criterion ids are used verbatim in the verdict JSON.

| id | pass when |
|---|---|
| `colossus-readable` | The Colossus can be told apart from sky, ground and fog in every frame that has it in view, including when it stands far away (beyond 450 m) in haze. A frame from inside a shot that is meant to be close (over-shoulder, close grip, aerial) passes if some of its body, grip or silhouette is recognisable. |
| `wanderer-visible` | In the close shots (low hero, over-shoulder, close grip) the Wanderer is visible as a small figure against the Colossus or ground. Not asked of the wide and aerial shots. |
| `exposure` | The frame is not black and not blown out: it has a dark end and a lit end, and no large area is a flat black or flat white. A deliberate fade (Reset) is exempt. |
| `no-ui` | No text, panel, slider, cursor or debug overlay is in the frame. |
| `horizon-fog` | Where a horizon is in view it is plausible: sky above ground, fog thicker near the ground and thinning upward, no hard band or hole in the fog. |

Frames to judge, with what each tests:

- `shot-1` to `shot-5`: the five director shots pinned with `/vj/cam` 0..4 and `/vj/cam_auto` 0.
- `fog_height-0`, `fog_height-0.41`, `fog_height-1`, `fog-0`, `fog-1`, `intensity-0`, `intensity-1`: shot 1 with that one control at that wire value. A control at an end may legitimately make a frame dark (intensity 0) or clear (fog 0); judge `exposure` as "still readable", not as "same as default".
- `1-approach-scale-wide` to `9-next-colossus`: one frame per Phase of one Arc.
