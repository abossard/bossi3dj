# Look rubric, Colossus Scene with the real models (round 6, frozen)

Frozen on 2026-11-11 before any change of the round. Judged on 480 px tiles of the output frame (what Syphon carries), together with [look-rubric.md](look-rubric.md). A new wish starts the next round and does not change this bar. Criterion ids are used verbatim in the verdict JSON.

Numbers come first (`python3 tools/png_stats.py <png>...`, `make godot-framing`, `make godot-wanderer-read`); the reviewer judges only what numbers cannot say.

| id | pass when |
|---|---|
| `climb-readable` | In every climb shot (`3-climb-over-shoulder`, `4-shake-close-grip`; the aerial shot is exempt) the Wanderer and the surface he holds are readable: `luma_mean` at least 60 of 255 and `near_black` (luma under 8) under 0.10 in `png_stats`, and the reviewer can see his body and the surface at his hands. The wide shots keep their dusk: `shot-1` stays within 10 luma of its round 5 value and keeps its dark end and lit end (`luma_variance` at least 80 % of round 5). |
| `giant-scale` | In each wide and medium frame with the Colossus in view (`shot-1`, `shot-2`, `shot-3`, `shot-5`, `1-approach-scale-wide`, `2-approach-low-hero`, `6-fall-toppling`, `7-fall-down`, and the fog and intensity frames) something of known size is in frame with it or on it (the Wanderer, Shrine columns, dust at its feet, haze layers across its height), and its surface shows detail at that distance (the reviewer names the detail: rock grain, plates, cracks, colour change). |
| `hero-tell-apart` | In the low hero shot on the long walk (`shot-2`, and `low-hero-start`, `low-hero-1500m`, `low-hero-1000m`, `low-hero-450m` of `make godot-wanderer-read`) a viewer tells the Wanderer from the Colossus at once: the Wanderer takes at most 40 % of the frame height (432 px of 1080, a number) and the Colossus stands clear of him against the sky (his outline does not overlap its). The Wanderer stays whole in frame. |
| `face-reads` | The Colossus has a face that reads at medium distance (the frames with its head in view at 150 m or less: `shot-3`, `shot-5`, `1-approach-scale-wide`, `3-climb-over-shoulder`): eye glints or an equivalent that fits Grock. The reviewer names the feature. Not asked of frames where the head is under 40 px. |
| `old-rubric` | Every frame still passes `colossus-readable`, `wanderer-visible`, `exposure`, `no-ui`, `horizon-fog` of `look-rubric.md`. |

Frames to judge: the frames of `make godot-look` (`start-f120`, `shot-1` to `shot-5`, the fog, fog_height and intensity ends, `new-colossus-after-hold`) and of `make godot-capture` (`1-approach-scale-wide` to `9-next-colossus`), plus the four `make godot-wanderer-read` frames for `hero-tell-apart`. A criterion that does not apply to a frame is `n/a`, not a pass.

Round budget: one look round, one fix pass, one re-grab of the failed frames. What still fails goes into the hand-over note with the reviewer's words.
