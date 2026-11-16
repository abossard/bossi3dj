# Robot MMV effects in Magic, round 1 (frozen 2026-11-17, before the review)

One sheet, 4 tiles (2x2, 480x270 each, left to right, top to bottom), Syphon grabs of Magic's output 3 s apart, project `robot/package/many/robot.magic` (placeholder Clips: a tinted test card inside a disc, the Matte, on transparent black; an Idle Clip is a plain blue card in a breathing disc). No music: the tier is calm, so the calm grade (less saturation) is on and the glow is off; a flash or colour split shows only if a grab caught a Hit or a cut.

| ID | Pass when | Counterexample (fail) |
|---|---|---|
| X1 | Every tile shows one placeholder Clip: a disc with test-card content, centred, on a dark background. | A black tile, a full-frame card with no disc, a solid colour, two discs. |
| X2 | The image is clean: no tearing, no stretched or offset content, no stripes or blocks from a broken module. | A shifted or mis-scaled card, a band of garbage pixels. |
| X3 | Any colour fringe (red and blue edges offset) sits evenly round the disc edge; otherwise none. | Fringes in one corner only, or the whole card doubled. |
| X4 | The tiles differ (another Clip or another frame of one), so the output moves. | Four identical tiles. |

Name the tile numbers for every fail; mark a line "not judged" when no tile can show it.
