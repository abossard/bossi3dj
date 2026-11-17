# Weighted animation without mocap

Question (the user, 2026-11-17): the Moves look "very mechanic and unnatural"; can we generate realistic, weighted motion ourselves, procedurally or with physics, in Python plus Blender? Mocap from Mixamo is a parallel route and only appears here where the two combine.

Scope: `robot/build/moves.py` as of 3d40a42. Numbers below are second differences of `moves.frames()` at 30 fps (hips z as a stand-in for the centre of mass).

## 1. Why our key tables look mechanical

- **Every key is a full stop.** Smoothstep has zero velocity at both ends, so every channel stops at every key. `jab_cross` has keys at beats 0.7, 1.0, 1.3, 1.7, 2.0, 2.5: the whole body halts every 4 to 6 frames. Real motion passes through key poses with speed; animators call stopping on every pose "pose to pose without breakdowns" (Lasseter 1987).
- **Uniform easing.** All 11 channels use the same curve between the same two keys. Heavy parts (hips, trunk) and light parts (fists, head) get identical timing, so mass does not read.
- **All joints in sync.** Every channel leaves and arrives on the same frame. Nothing leads, nothing trails: no successive breaking of joints, no overlapping action, no follow-through (Thomas and Johnston; Lasseter 1987; Neff and Fiume 2005 call this "succession").
- **No anticipation or overshoot.** A key is reached and held exactly. The Cartoon Animation Filter paper names this "wooden and dead" and shows that anticipation and follow-through are the missing second-derivative terms (Wang et al. 2006).
- **No momentum consistency.** Measured on our Moves:
  - `leap_slam` in the air (frames 36 to 55, both feet above 0.20 m): hips z acceleration swings from -66 to +48 m/s². Ballistic flight is a constant -9.81. The body speeds up upward at mid-air, then brakes at the apex key, then again at the "fall" and "reach" keys. Height is right (0.53 m rise for 0.67 s of air, ballistic gives 0.55 m), the shape is wrong.
  - Smoothstep's peak acceleration is `6·Δ/T²`. A 0.5 m hips drop over 0.15 s pulls at 130 m/s², 13 g downward: the floor would have to pull the robot down. `power_stomp` peaks at +69 m/s², `burst_rise` at -46.
  - Calm Moves stay within ±2.3 m/s², which is why they read better than the drop tier.
- **Feet sliding.** Our planted feet are exact (tested). The remaining tell is the lift: a foot rises and lands with smoothstep and no heel-toe roll, so it floats on and off rather than pushing and striking.
- **No ground reaction.** At a landing or stomp nothing absorbs: the hips arrive at the key and stop. Real contact compresses the legs after the contact frame (a decaying dip), and the impact runs up the chain into the trunk and head.

## 2. Techniques that read as weight, and how to compute them

### 2.1 Offset and overlap per chain (succession)

- Each chain samples the key table at a shifted time: `x_c(f) = keys(f + lead_c)`. A negative lead means the chain moves early.
- Proximal leads, distal follows on the way into a strike; the head and free arm trail after it (follow-through).
- Our channels group into chains: `hips, hips_rot` / `spine_rot` / `chest_rot` / `hand_*` / `head_rot` / `foot_*` (swing only).
- `_sample_keys` already accepts fractional frames, so this is a resample, no new keys.

### 2.2 Second-order dynamics (spring-damper as a filter)

The t3ssel8r formulation: the output `y` follows the target `x` like a mass on a spring, with three intuitive knobs.

```
y + k1·y' + k2·y'' = x + k3·x'
k1 = zeta / (pi·f)        f: natural frequency in Hz (speed of response)
k2 = 1 / (2·pi·f)²        zeta: damping (<1 overshoots and wobbles, 1 critical, >1 sluggish)
k3 = r·zeta / (2·pi·f)    r: initial response (>1 overshoots the onset, <0 anticipates, 0 lags in)
```

Discrete update per frame (semi-implicit Euler, T = 1/30, clamp keeps it stable at high f):

```
xd  = (x[n] - x[n-1]) / T
y  += T·yd
k2s = max(k2, T²/2 + T·k1/2, T·k1)
yd += T·(x[n] + k3·xd - y - k1·yd) / k2s
```

- Critically damped spring (zeta = 1, r = 0): fastest approach with no overshoot. Holden's "Spring-It-On" gives exact closed forms, including half-life parametrisation `halflife ≈ 0.69 / (zeta·omega)`; exact solutions avoid the step-size clamp (Holden 2021, Juckett 2012).
- Run each axis of each channel through its own filter. Euler degrees are fine at our ranges (no channel wraps past ±180).
- Offline we can also run the filter backwards in time and average, which gives zero lag; we want the lag, so forward only.

### 2.3 Anticipation and overshoot as filter responses

- Overshoot and settle: zeta < 1 on light chains (fists, head). The fist arrives, passes 2 to 4 cm, comes back.
- Anticipation is non-causal: the body counter-moves before the action starts. Two ways:
  - r < 0 in the second-order filter gives a small initial counter-movement on each change of target.
  - Cartoon Animation Filter (Wang et al. 2006), offline, per channel: `x*(t) = x(t) - A·(x ⊗ LoG_sigma)(t)`. Subtracting the smoothed second derivative pushes the signal backwards before a fast move (anticipation) and past it after (follow-through). One knob A; sigma sets the time scale (paper: about the duration of the action, 3 to 8 frames for our strikes).
- Our hand-written LOAD keys (`CROSS_LOAD`, `HOOK_LOAD`, `cock`) already are anticipation; the filter adds it to the channels nobody keyed (hips, chest, head).

### 2.4 Centre of mass, balance, support polygon, ZMP

- Segment masses from Winter (fractions of body mass): head and trunk 0.578, each arm 0.050, each leg 0.161. A 0.46 m jab moves the centre of mass about 1.5 cm: arms are light, counterbalancing punches with the hips is nearly invisible. A kick moves 16 % of the mass by about 0.5 m: 8 cm, which the hips must take back (our `front_kick` keys move hips 0.14 m back, consistent).
- Approximation from our channels (within a few cm, enough for a rule):

```
c ≈ 0.70·(hips + (0,0,0.25)) + 0.025·(hand_l + hand_r) + 0.025·(sh_l + sh_r)
    + 0.16·(0.6·hip_joint_l + 0.4·foot_l) + 0.16·(0.6·hip_joint_r + 0.4·foot_r)
```

- Static balance: `c_xy` inside the support polygon (convex hull of the planted soles). Dynamic balance, cart-table model (Kajita 2003): `zmp_xy = c_xy - (c_z / g)·c''_xy` must stay inside the polygon (Vukobratović and Borovac 2004).
- Rule, applied after the keys: if the ZMP leaves the polygon with a margin of 3 cm, translate the hips by `Δh_xy = -(Σ m_i·Δp_i,xy) / 0.70` until it returns. Hips moved this way must keep the planted legs in reach (clamp by `hip_joint`/`LEG_M`, as `test_ankles_planted` does).

### 2.5 Momentum transfer in strikes (kinetic chain)

- Striking and throwing follow proximal-to-distal sequencing: each segment's peak angular velocity comes after the previous one's, and the distal segment is fastest (Putnam 1993). For a cross: hips turn, then trunk, then shoulder, then elbow extension, then fist.
- Inter-segment delays in fast strikes are tens of milliseconds; at 30 fps that is one or two frames per link (estimate, not a measured boxing figure).
- For us: the fist keeps its Hit frame, the chain ahead of it peaks earlier: `hips_rot` -4 frames, `spine_rot` -3, `chest_rot` -2, hand 0, `head_rot` +2 (trails), rear hand +1.

### 2.6 Impact: hit-stop, recoil, shake

- Hit-stop: freeze the whole image for a few frames at the contact frame, then continue. Fighting games scale the freeze with damage (Sakurai, "Creating Games", episode on hitstop). At 30 fps: `n = round(1 + 2·strength)` frames, so 2 to 3 frames (67 to 100 ms).
- On a beat grid the frames must come back: time warp `s(f)` from output frame to source time, flat for `n` frames after the Hit, then faster until the next beat so the next beat still lands:

```
s(f) = h                                      for h <= f <= h + n
s(f) = h + (f - h - n)·(b - h)/(b - h - n)    for h + n < f <= b   (b: next beat frame)
```

- In an Exchange both fighters share one `s(f)`, otherwise the contact breaks.
- Recoil: a damped sine added after the freeze, along `-u` (u: the fist's direction just before contact):

```
d(t) = -A·u·exp(-zeta·w·t)·sin(w·sqrt(1 - zeta²)·t),   t = (f - h - n)/30
fist: A = 0.04·strength m, w = 2·pi·5, zeta = 0.35
hips: A = 0.02·strength m, w = 2·pi·3, zeta = 0.5   (whole body takes the reaction)
```

- Camera shake (Nijman 2013; Eiserloh 2016: shake = trauma², noise not random): Shot Cameras are locked and the Depth and Shadow Passes align with them. Leave shake to Magic on the Hit frames the Clip Data already lists; do not bake it.

### 2.7 Foot locking and ground contact

- Keep what we have: a planted foot is copied from the key table, never filtered.
- Swing feet: filter with zeta >= 1 (no overshoot through the floor), then clamp `z >= ANKLE_Z`.
- Touch-down: a pin at the contact frame (2.8), then a ground reaction on the hips: `d_z(t) = -A·exp(-zeta·w·t)·sin(w_d·t)`, A = 0.03 to 0.06 m by strength, f 3 Hz, zeta 0.5.
- Lift-off: push before the foot leaves (hips drop 1 to 2 cm two frames before), heel before toe via `foot_*_rot` x. Kovar et al. (2002) is the reference for cleaning sliding on top of edited or mocap motion.

### 2.8 Pins: keep the contract while filtering

- Filters move keyed values, our tests need some of them exact. Fix with offset blending (the idea behind inertialization, Bollo 2018): at each pin frame p, take the residual `e = keys(p) - y(p)` and add it back with a window.

```
y'(f) = y(f) + e·w(f - p),   w(d) = 0.5·(1 + cos(pi·d / W)) for |d| < W, else 0
W = 6 frames at Hits and touch-downs; one-sided W = 10 at the Clip's first and last frame
```

- Pins: first and last frame (all channels), each Hit (the hitting limb only), every planted foot (raw keys), Cut Point beats if we keep them.
- Two pins closer than 2W: use `W = gap/2`.

### 2.9 Squash and per-joint timing

- Rigid hard-surface pieces cannot squash. The robot's squash is compression of the chain: hips drop, spine and chest flex at the contact frame, recover through the spring.
- Per-joint timing comes from the per-chain f and zeta in section 4, step 2: heavy chains slow and damped, light chains fast and springy.

## 3. Physics routes and their cost

| Route | What it gives | Cost for us | Verdict |
|---|---|---|---|
| Blender rigid body world (Bullet), pieces linked by constraints | Real collisions and falls | Constraint springs pull to the rest state set at creation; tracking an animated pose needs a per-frame Python handler feeding the cache, fragile headless | No |
| Offline active ragdoll in MuJoCo or PyBullet: 15 bodies from our rig, PD position actuators tracking the keyed pose, 500 to 1000 Hz, record at 30 fps, bake | Secondary motion and impacts with true inertia | 1 to 2 weeks. A PD-tracking body without a balance controller falls; the usual fix is a residual "hand of god" force on the pelvis (Yuan and Kitani 2020), which hides exactly the balance errors we want to see. Hit frames drift, pins needed again. New dependency (vetting), deterministic per build | Later, for take-hit reactions only (Zordan and Hodgins 2002 did punches and hit reactions this way) |
| Trajectory optimisation (spacetime constraints, Witkin and Kass 1988; momentum constraints from simple key animation, Liu and Popović 2002) | Physically valid motion that keeps keyed poses | Weeks; a nonlinear optimiser over all frames, tuning per Move | The right theory for our problem; take its two cheapest rules (ballistic flight, ground reaction force) as tests and filters |
| DeepMimic / AMP reinforcement learning (Peng et al. 2018, 2021) | Robust physics-based skills from reference clips | Days of training per skill on many CPU cores or a GPU sim, an RL stack, a physics model of the M2000; no guarantee of exact Hit frames or Key Poses | No: 21 Moves on a beat grid with frame-exact contracts is the wrong shape |
| Inverse dynamics check | Whether a trajectory is physically possible | Hours; pure Python on the centre of mass | Yes, as tests |

Inverse dynamics on the centre of mass, the cheapest physics we can have:

```
F = m·(c'' + g·z)                       ground reaction force, m = 1 (per kg)
on the ground:  F_z >= 0                the floor pushes, never pulls
                |F_xy| <= mu·F_z, mu = 0.8   no skating
in the air:     c''_z = -g, c''_xy = 0  ballistic, within a tolerance
landing peak:   F_z <= 6·g              legs absorb, not a wall
```

## 4. Recommendation

Keep the key tables and the beat grid as targets. Add one pure module, `robot/build/weight.py` (no bpy), applied inside `moves.frames()`, so `build_robot.py`, `exchanges.py` and every test get the weighted Pose sequence with no other change. Order by gain per cost:

1. **Ballistic flight** (biggest single fix for the drop tier). Between take-off (last frame both feet planted) and touch-down, replace the hips with a parabola through both ends with `g = 9.81`; the apex follows from the air time (`h = g·t²/8`), the apex key goes. Same rule for `burst_rise`. Half a day.
2. **Per-chain lead plus second-order filter, with pins.** Sample each chain at `f + lead`, filter it, pin as in 2.8. Parameters at 30 fps, tune by eye on one Move:

| Chain | lead (frames) | f (Hz) | zeta | r |
|---|---|---|---|---|
| hips, hips_rot | -3 | 2.0 | 0.8 | 0 |
| spine_rot | -2 | 2.5 | 0.7 | 0 |
| chest_rot | -1 | 3.0 | 0.6 | 0.5 |
| hand_* (striking) | 0 | 4.5 | 0.45 | 1.5 |
| hand_* (free) | +1 | 3.5 | 0.5 | 0 |
| head_rot | +2 | 3.0 | 0.4 | 0 |
| foot_* (swing only) | 0 | 5.0 | 1.0 | 0 |

   The leads remove the all-stop-together frames; the filter turns smoothstep's stops into carried motion with overshoot on light parts. One to two days with tests.
3. **Hit-stop and recoil** (2.6), shared time warp for both fighters in an Exchange, Hit frames unchanged. One day.
4. **Ground reaction at touch-downs and stomps** (2.7), hips spring dip. Half a day.
5. **Centre-of-mass rule** only for kicks, stomps and leans (2.4); punches barely move it. One day, lower priority.
6. Optional: Cartoon Animation Filter on hips and chest for anticipation the keys lack. Half a day to try.

What stays deterministic and testable: everything. Filters and warps are pure functions of the key table, no randomness, no simulation state. Existing parametrised tests keep their meaning:
- Key Poses at both ends: pins at the first and last frame make them exact.
- No jump between frames: the filter is smoother than its input; recoil amplitudes are well inside 0.33 m and 20° per frame; the hit-stop catch-up speeds up by `(b-h)/(b-h-n)`, about 1.2x for n = 3 over one beat.
- Planted ankles: planted feet bypass the filter; hips offsets get the reach clamp.
- Hit contact distance (`test_hits_land_on_their_target`): the hitting limb is pinned at the Hit frame.

New parametrised tests, per Move and frame:
- Air: `|c''_z + 9.81| <= 1.5` while both feet are off the ground.
- Ground: `F_z >= 0` and `|F_xy| <= 0.8·F_z` while a foot is planted, outside the pin windows.
- Succession: at each Hit, the `hips_rot` speed peak comes at least 2 frames before the hand's.
- Still frames: no frame where every channel moves less than 1 mm or 0.1°, outside Idle Clips and hit-stops.

Cost: about 4 to 6 days for steps 1 to 4 with tests, plus one low re-render of the 42 Clips. Cut Points will mostly drop to the beats that are pins; check that Magic's cut logic copes or pin the Cut Point beats.

## 5. Ceiling, and combining with mocap

- Procedural layers add weight to poses we chose; they do not invent the poses. They cannot give the small asymmetries, balance corrections, breathing coupling and style that a performer has, and they cannot fix a key pose that is anatomically wrong. Expect "heavy robot" quality, not "human fighter" quality.
- Mocap gives the body; it is weak exactly where the procedural layer is strong: frame-exact Hits on a beat, contact with the giant, impacts, and staying on the floor after retargeting.
- Combined stack, bottom to top:
  1. Mocap clip retargeted to our IK targets (hips, hands, feet, rotations), time-warped so its contact frames land on the beat (the same `s(f)` as hit-stop).
  2. Foot locking and reach clamp (Kovar et al. 2002 style).
  3. Pins at Hits and Key Poses, offset blending.
  4. Impact layer: hit-stop, recoil, ground reaction.
  5. No second-order filter on mocap channels (it already has overlap; filtering it only adds lag), or a light one on the head only.
- So the work in section 4 is not wasted if mocap wins: steps 1, 3 and 4 and all the tests apply to mocap unchanged.

## Sources

- Lasseter, "Principles of traditional animation applied to 3D computer animation", SIGGRAPH 1987: https://doi.org/10.1145/37402.37407
- Thomas and Johnston, *The Illusion of Life: Disney Animation*, 1981 (book): the twelve principles.
- Wang, Drucker, Agrawala, Cohen, "The Cartoon Animation Filter", SIGGRAPH 2006: https://grail.cs.washington.edu/wp-content/uploads/2015/08/wang-2006-tca.pdf
- Neff and Fiume, "AER: aesthetic exploration and refinement for expressive character animation", SCA 2005: https://doi.org/10.1145/1073368.1073391
- t3ssel8r, "Giving Personality to Procedural Animations using Math" (second-order systems): https://www.youtube.com/watch?v=KPoeNZZ6H4s
- Holden, "Spring-It-On: The Game Developer's Spring-Roll-Call", 2021: https://theorangeduck.com/page/spring-roll-call
- Juckett, "Damped Springs", 2012: https://www.ryanjuckett.com/damped-springs/
- Bollo, "Inertialization: High-Performance Animation Transitions in Gears of War", GDC 2018: https://www.gdcvault.com/play/1025165/Inertialization-High-Performance-Animation-Transitions
- Rosen, "An Indie Approach to Procedural Animation", GDC 2014: https://www.gdcvault.com/play/1020583/Animation-Bootcamp-An-Indie-Approach
- Winter, *Biomechanics and Motor Control of Human Movement*, 4th ed., Wiley 2009 (segment mass table).
- Vukobratović and Borovac, "Zero-moment point: thirty five years of its life", IJHR 2004: https://doi.org/10.1142/S0219843604000083
- Kajita et al., "Biped walking pattern generation by using preview control of zero-moment point", ICRA 2003: https://doi.org/10.1109/ROBOT.2003.1241826
- Putnam, "Sequential motions of body segments in striking and throwing skills", J. Biomechanics 1993: https://doi.org/10.1016/0021-9290(93)90084-R
- Sakurai, "Masahiro Sakurai on Creating Games" (hitstop episode, 2022): https://www.youtube.com/@sora_sakurai_en
- Nijman, "The art of screenshake", 2013: https://www.youtube.com/watch?v=AJdEqssNZ-U
- Eiserloh, "Math for Game Programmers: Juicing Your Cameras With Math", GDC 2016: https://www.gdcvault.com/play/1023557/Math-for-Game-Programmers-Juicing
- Kovar, Schreiner, Gleicher, "Footskate cleanup for motion capture editing", SCA 2002: https://research.cs.wisc.edu/graphics/Gallery/kovar.vol/Cleanup/
- Zordan and Hodgins, "Motion capture-driven simulations that hit and react", SCA 2002: https://doi.org/10.1145/545261.545276
- Witkin and Kass, "Spacetime constraints", SIGGRAPH 1988: https://doi.org/10.1145/378456.378507
- Liu and Popović, "Synthesis of complex dynamic character motion from simple animations", SIGGRAPH 2002: https://doi.org/10.1145/566654.566607
- Yuan and Kitani, "Residual Force Control for Agile Human Behavior Imitation and Extended Motion Synthesis", NeurIPS 2020: https://arxiv.org/abs/2006.07364
- Peng et al., "DeepMimic", SIGGRAPH 2018: https://xbpeng.github.io/projects/DeepMimic/index.html
- Peng et al., "AMP: Adversarial Motion Priors", SIGGRAPH 2021: https://xbpeng.github.io/projects/AMP/index.html
- Blender manual, Rigid Body constraints: https://docs.blender.org/manual/en/latest/physics/rigid_body/constraints/index.html
- MuJoCo documentation: https://mujoco.readthedocs.io/
