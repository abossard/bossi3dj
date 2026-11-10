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

## Relationships

- A **Colossus** carries one **Grab Path** made of many **Grab Points**
- The **Wanderer** holds at most one **Grab Point** per hand
- **Shake** can happen in any **Phase** in which the **Wanderer** is on the **Colossus**
- Each **Reset** brings the next **Colossus** and returns the **Wanderer** to the **Shrine**
