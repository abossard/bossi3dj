# Giant machine: design proposal (issue #23, 2026-11-16)

The opponent the user chose: a giant foundry machine the Android fights. Proposal only; no geometry yet.

## Form

- A forge titan, about 6 m tall (3x the Android). Built by script like the Android (`build_robot.py`): rigid beveled parts parented to bones, no skinning.
- Chrome Foundry look with the existing materials: dark iron and gunmetal plates, polished steel on the edges and pistons, a molten core glowing through a grille in the chest (the `molten` material, the only light on the body).
- Readable silhouette at 1080p: a hunched torso on two thick piston legs, a hammer-press right arm (a block head about 1 m), a three-finger claw left arm, a small head with one slit eye.
- Rig: the Android's scheme scaled: root, hips, spine, chest, head; 2-bone IK arms and legs to wrist and ankle targets. Its own Key Pose `loom` (standing, hammer raised to the shoulder).

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
| sweep_jump | build | 2 | low > crouch | low claw sweep; the Android jumps over it and lands |
| knee_combo | build | 1 | guard > guard | jab, cross to the giant's knee; the knee buckles |
| hammer_hit | drop | 1 | guard > crouch | the hammer lands on the Android; it takes the hit and is driven into a crouch |
| core_strike | drop | 2 | crouch > guard | the Android leaps (as leap_slam) and punches the chest core; the giant reels back, sparks |
| quake_stomp | drop | 2 | low > low | the giant stomps; the floor shakes, the Android rides it out and answers with power_stomp |

- Tests in the style of `test_moves.py`, parametrized: both Key Poses at both ends, no jump per frame (the giant's speed cap scaled by its size), planted ankles for both, and the contact rule: at every Hit the striking point is within 0.15 m of the struck body, and on a dodge it stays more than 0.4 m away. Points are the IK targets and a few body points, as now.

## Composition

- Recommended: one render with both fighters per duel Angle. Occlusion, shadows and contact come out right, and Magic plays an Exchange like any Clip: beauty, Shadow and Depth as now.
- Not recommended: the giant as its own layer and Passes. Magic would have to depth-composite two Clips per frame to get the overlap right (a leg in front of the Android, the Android in front of the giant), and the pair would have to stay frame-locked. That doubles the decode load at 4 Angles.

## Budget

- Frames per duel Angle: 58 + 116 + 58 + 116 + 58 + 58 + 116 + 116 = 696; two duel Angles 1392.
- Final at 64 samples: two figures and a wider frame, estimated at 20 s per frame against the Android's measured 15 to 16 s: about 7.7 h for both duel Angles. To measure on the first build.
- Preview (Eevee, half size): 9 s Blender start per Clip plus about 0.3 s per frame: 16 Clips, about 10 min. Every Exchange gets a preview first, for `tools/robot_preview_reel.sh`.
- Building the giant (rig, parts, Key Pose): one session of script work, then one Blender slot of about 15 min for build, `check` and the first previews.
