# bossi3dj

A live VJ toolkit: music signals and performer input drive visual scenes that are mixed into a show.

## Colossus Scene

**Colossus**:
The giant creature that roams the Colossus Scene's landscape and can be climbed. Several exist; one appears at a time.
_Avoid_: Golem, titan, boss

**Wanderer**:
The small human figure who gives the Colossus its scale and climbs it.
_Avoid_: Hero, player, climber

**Grab Point**:
A hand-placed spot on the Colossus's body where the Wanderer can hold on. It moves with the Colossus.
_Avoid_: Handhold, anchor

**Grab Path**:
The graph of linked Grab Points along which the Wanderer climbs in a chosen direction.
_Avoid_: Climb route, climb graph

**Shake**:
The Colossus trying to throw the Wanderer off. The Wanderer swings from its grip but never falls.
_Avoid_: Buck, shake-off

**Arc**:
The ordered set of Phases the Colossus Scene can be advanced through, ending in a reset.
_Avoid_: Story, sequence

**Phase**:
One stage of the Arc: Approach, Climb, Fall or Reset.
_Avoid_: Act, state, section

**Shrine**:
The temple ruin where the Wanderer starts every Arc.
_Avoid_: Temple, spawn, start

**Takeover**:
The performer steering the Wanderer directly. It begins with any performer input and ends after a short idle, when the Wanderer returns to autonomous behaviour.
_Avoid_: Manual mode, override

## Synthwave Planet Scene

**Planet**:
The small fixed world sphere that every ground camera stands on. It never turns.
_Avoid_: Earth, globe, island

**Star System**:
The sun, moon and stars, which turn together around the Planet's spin axis and give every camera the same sky.
_Avoid_: Sky frame, celestial bodies

**On-Air Camera**:
The camera whose view is being sent to the show. The time of day is always set for it.
_Avoid_: Active camera, current shot

**Sun Height**:
The sun's angle above the On-Air Camera's horizon, chosen by the night control.
_Avoid_: Sun elevation, sun amount

**Moon Phase**:
How far the moon sits around its orbit from the sun, from new (beside the sun) to full (opposite it). The lit part shown follows from it.
_Avoid_: Moon light, moon angle

**Eclipse**:
The moon lined up with the sun and the Planet: in the Planet's shadow at full moon (lunar), or in front of the sun at new moon (solar).
_Avoid_: Blackout, occlusion

**Flight**:
The one continuous, procedural camera that a single control carries from an orbit around the Planet, through a landing approach and a skim over the mountains, down to hovering over the water.
_Avoid_: Fly-through, descent shot, canyon flight

**Boost**:
A push of the Flight's accelerator: a short forward surge while hovering low.
_Avoid_: Turbo, speed-up

**Star Drift**:
The slow turn of the stars against the sun, as over a year, which leaves the Sun Height alone.
_Avoid_: Star rotation, sky spin

## Robot Scene

**Robot Scene**:
The VJ scene in which a pre-rendered Android fights to the music, with live Blender layers around it.
_Avoid_: Robot show, android scene

**Android**:
The humanoid fighting machine at the centre of the Robot Scene; one rig, one design.
_Avoid_: Robot, mech, bot, fighter

**Move**:
One named action of the Android, such as a jab, a duck or a recoil, independent of camera.
_Avoid_: Animation, action, attack

**Clip**:
One Move rendered from one Angle, a whole number of beats long, with its Passes and Clip Data.
_Avoid_: Video, footage, loop, take

**Key Pose**:
A pose in which Clips start and end, so any Clip may follow any Clip that ends in the same Key Pose.
_Avoid_: Hub pose, transition pose, Pose Key

**Clip Graph**:
The graph of Clips joined by Key Poses that Magic walks to pick the next Clip.
_Avoid_: State machine, move tree, playlist

**Cut Point**:
A beat inside a Clip where Magic may switch to another Clip or Angle.
_Avoid_: Cue, marker, switch point

**Intensity Tier**:
One of three energy levels a Clip belongs to (calm, build, drop); Magic picks from the tier the music is in.
_Avoid_: Energy level, energy bucket, fight mode

**Angle**:
One of the views every Move is rendered from with the same timing.
_Avoid_: View, cam, shot

**Shot Camera**:
The Blender camera that renders one Angle.
_Avoid_: CAM_N, On-Air Camera

**Camera Track**:
The per-frame export of a Shot Camera that Live Layers replay so their parallax matches.
_Avoid_: Camera path, camera export

**Pass**:
One rendered image layer of a Clip; Light Pass, Matte, Depth Pass, Normal Pass and Shadow Pass are kinds.
_Avoid_: AOV, render layer, channel

**Light Pass**:
A Pass lit by one light only, so Magic can mix lights after the render.
_Avoid_: Light layer, light group

**Matte**:
A Pass that says where the Android covers the frame.
_Avoid_: Mask (Magic's module), alpha, cutout

**Depth Pass**:
A Pass with the distance of every pixel, so Live Layers sit in front of or behind the Android.
_Avoid_: Z buffer, Z pass

**Normal Pass**:
A Pass with the surface direction of every pixel, for Relight.
_Avoid_: Normal map

**Shadow Pass**:
The Android's shadow and contact shade on the ground, to lay over a Live World.
_Avoid_: Contact shadow, AO pass

**Clip Data**:
Per-frame screen positions and depths of the Android's head, eyes, hands and feet, plus its Hits.
_Avoid_: Metadata, tracking data

**Hit**:
An impact event in Clip Data: frame, point and strength. Not the music trigger `/vj/hit`.
_Avoid_: Impact, strike, hit point

**Clip Library**:
Every Clip rendered for the Robot Scene.
_Avoid_: Footage pool, video bank

**Manifest**:
The JSON that lists every Clip with its Move, Angle, beats, Key Poses, Passes and files.
_Avoid_: Index, catalog, metadata file

**Render Package**:
The folder Blender writes: the Clip Library, its Clip Data and the Manifest.
_Avoid_: Export, bundle, output file

**Live Layer**:
Anything Blender draws live that Magic puts on top of or behind the Clip.
_Avoid_: Overlay, live stuff, FX layer

**Live World**:
A Live Layer that is the whole surroundings behind the Android, drawn live and reacting to the music.
_Avoid_: Live background, environment

**Relight**:
Changing a Clip's lighting in Magic by mixing Light Passes or shading the Normal Pass.
_Avoid_: Recolour, relighting, regrade

## Relationships

- A **Colossus** carries one **Grab Path** made of many **Grab Points**
- The **Wanderer** holds at most one **Grab Point** per hand
- **Shake** can happen in any **Phase** in which the **Wanderer** is on the **Colossus**
- Each **Reset** brings the next **Colossus** and returns the **Wanderer** to the **Shrine**
- A **Clip** is one **Move** from one **Angle**; it starts and ends in a **Key Pose**, and the **Clip Graph** joins **Clips** that share one
- The **Render Package** holds the **Clip Library**, its **Clip Data** and the **Manifest**; each **Clip** brings its **Passes**
- A **Live Layer** replays the **Camera Track** of the **Clip** on air and places effects at its **Hits**
