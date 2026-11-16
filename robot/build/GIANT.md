# Giant machine: design proposal (issue #23, 2026-11-16)

The opponent the user chose: a giant foundry machine the Android fights. Proposal only; no geometry yet.

## Form

Held: the user wants a rich, detailed, rigged model from the internet, not a script-built one; the form follows the chosen candidate. Fixed so far: about 6 m tall (3x the Android), a hammer or press arm and a claw or grab arm help the Exchanges below, a glowing core helps the look.

## Why the Android reads weak, and what the machine does instead

- Silhouette: built from boxes, spheres and cylinders, generic at tile size. The machine: a detailed model with distinct masses (hammer, claw, hunched torso) that read in silhouette alone.
- Materials: near-mirror steel that reflects a black world, so it renders dark (3.5 % of the frame lit in the v1 live test). The machine: materials that keep their own colour (painted, worn iron; steel only on edges and pistons), so they read without a bright environment.
- Light: one tiny amber visor is the only emitter. The machine: an emissive core and panel lights, plus a rim light per duel Angle that separates it from a dark backdrop.
- Detail and scale cues: no panel lines, no greebles, no set in the Clips, so nothing tells its size. The machine: detail at three scales (plates, bolts, cables), and the Android beside it as the scale cue, with a visible floor shadow.

## Imported, rigged asset

- Source: a model whose licence allows use without a login, stored under `robot/assets/<name>/` with its licence file (or git-ignored with a fetch script and a checksum if it is large).
- On import (`build_robot.py`, a new `import_asset` step): apply transforms, scale to the planned height, put the feet on the floor, convert its materials into the Chrome Foundry look by material name (metal, paint, emissive), set shadow visibility as for the Android, and add the Clip Data point empties parented to named bones. Passes stay as they are (beauty with the Matte, Shadow Catcher, Depth).
- Driving it from key tables: a bone map in the build script from our channels (hips, spine, chest, head, hand and foot targets) to the asset's bones. If the asset has IK, our hand and foot targets drive its IK controls; if not, the build adds 2-bone IK constraints with our targets and poles to its arm and leg bones. Rotations convert from our convention (bones up, roll 0) into each bone's rest frame with its rest matrix, so the key tables stay asset-independent and testable without Blender.
- `check` covers it as it covers the Android: planted soles, reach, lowest point; one probe frame per Key Pose before any render.
- The same path can later replace the Android (#28): only the bone map and the material rules change, not the Move tables.

## Staging and Angles

- The giant stands 4 m in front of the Android, facing it (Android at the origin facing -Y, giant at y = -4 facing +Y).
- The current Angles cannot hold it: `front` looks from where the giant stands, and `side` frames 2 m of figure. They stay for solo Android Clips; the giant is out of frame there.
- Two duel Angles (part of #20): `duel_wide`, a profile from +X far enough back to hold both full figures (about 12 m away, 24 mm); `duel_low`, low behind the Android looking up at the giant (the Android in the foreground, the giant towering).

## Moves: Exchanges

- An Exchange is one Move with both fighters: the giant's keys and the Android's keys on one beat grid, 124 BPM, 1, 2 or 4 bars. The Android's part starts and ends in its Key Poses (guard, low, crouch); the giant starts and ends in `loom`. So the Clip Graph, cut rules and tiers hold unchanged; an Exchange is just a Clip whose `move` carries two tables.
- Hits go both ways: the giant's limbs on the Android, the Android's on the giant. Clip Data gains the giant's points (`giant_hammer`, `giant_claw`, `giant_foot`, `giant_core`); a contract change to propose in `CONTRACTS.md`.

| Exchange | Tier | Bars | Android from > to | What happens |
|---|---|---|---|---|
| duel_idle | calm | 1 | guard > guard | both breathe; the core pulses, steam (Idle Clip) |
| circle | calm | 2 | guard > guard | the giant shifts its weight and turns; the Android steps around in guard |
| hammer_dodge | build | 1 | guard > low | overhead hammer into the floor; the Android sidesteps wide |
| sweep_jump | build | 1 | low > crouch | low claw sweep; the Android jumps over it and lands |
| knee_combo | build | 1 | guard > guard | jab, cross to the giant's knee; the knee buckles |
| hammer_hit | drop | 1 | guard > crouch | the hammer lands on the Android; it takes the hit and is driven into a crouch |
| core_strike | drop | 2 | crouch > guard | the Android leaps (as leap_slam) and punches the chest core; the giant reels back, sparks |
| quake_stomp | drop | 2 | low > low | the giant stomps; the floor shakes, the Android rides it out and answers with power_stomp |

- Tests in the style of `test_moves.py`, parametrized: both Key Poses at both ends, no jump per frame (the giant's speed cap scaled by its size), planted ankles for both, and the contact rule: at every Hit the striking point is within 0.15 m of the struck body, and on a dodge it stays more than 0.4 m away. Points are the IK targets and a few body points, as now.

Key tables: [exchanges.py](exchanges.py), tests in [tests/test_exchanges.py](tests/test_exchanges.py). The giant is written against named control points (`g_hips`, `g_hammer`, `g_claw`, `g_foot_l`, `g_foot_r` and three rotations), placed for a 6 m figure 2.5 m in front of the Android; the bone map of the imported model turns them into its IK targets. Contact uses point spheres (hammer 0.5 m, core 0.6 m, knee 0.35 m, the Android's fist 0.08 m, head 0.15 m): every Hit lands within 0.15 m of touching, every dodge clears by more than 0.4 m. The giant's speed cap is 0.6 m and 12° per frame.

Proposed contract change (not applied):

```diff
 ## Clip Data (`clip_data/<clip id>.json`)
-| `frames` | list, one entry per frame: `{f, head, eye_l, eye_r, hand_l, hand_r, foot_l, foot_r}`, each `[x, y, depth]` ... |
-| `hits` | list of Hits: `{f, point: [x, y, depth], strength: 0..1, limb}` |
+| `frames` | list, one entry per frame: `{f, head, eye_l, eye_r, hand_l, hand_r, foot_l, foot_r}`, plus in an Exchange `{g_head, g_core, g_hammer, g_claw, g_foot_l, g_foot_r}`, each `[x, y, depth]` ... |
+| `hits` | list of Hits: `{f, point: [x, y, depth], strength: 0..1, limb, target}`; `limb` may be a giant point (`g_hammer` ...), `target` is the struck point or `floor` |
 ## Manifest
+| `opponent` | Clip field: `true` for an Exchange (both fighters in the frame), `false` otherwise |
```

## Composition

- Recommended: one render with both fighters per duel Angle. Occlusion, shadows and contact come out right, and Magic plays an Exchange like any Clip: beauty, Shadow and Depth as now.
- Not recommended: the giant as its own layer and Passes. Magic would have to depth-composite two Clips per frame to get the overlap right (a leg in front of the Android, the Android in front of the giant), and the pair would have to stay frame-locked. That doubles the decode load at 4 Angles.

## Budget

- Frames per duel Angle: 58 + 116 + 58 + 116 + 58 + 58 + 116 + 116 = 696; two duel Angles 1392.
- Final at 64 samples: two figures and a wider frame, estimated at 20 s per frame against the Android's measured 15 to 16 s: about 7.7 h for both duel Angles. To measure on the first build.
- Preview (Eevee, half size): 9 s Blender start per Clip plus about 0.3 s per frame: 16 Clips, about 10 min. Every Exchange gets a preview first, for `tools/robot_preview_reel.sh`.
- Importing the giant (bone map, material rules, Key Pose): one session of script work once the asset is chosen, then one Blender slot of about 15 min for import, `check` and the first previews.
