# EDM analysis in Magic (session gallant-nobel-56f239)

Branch `claude/gallant-nobel-56f239` (fast-forwarded onto `claude/magic-scene-tooling-874023`, then 5 commits, not pushed).

- Generator `magic/edm_analysis_magic.py` -> `scenes/edm_analysis.magic` (Compare, A, B, C, OSC Tap). README section lists every Global. Tests: `tests/test_edm_analysis.py`.
- User ratings: beat clock, kick, vocals great in A; B best structure (presence buildup, low-end-jump drop). B, C share A's analysis and differ only in structure. Magic opens on B.

## Verified facts (Magic 3.0b6, live)

- Audio features update about 94 times/s (512-sample hop at 48 kHz); graphics run 110-300 fps. Band values are not smoothed (autocorrelation matches a 46 ms FFT window).
- Magic's band onsets lag the audio by about 30-60 ms.
- ExprTk in Magic: `var` locals, `frac`, `log2`, `atan2`, `pi`, `%`, `!=`, `pow`, `^` work; `round` rounds half away from zero. `var` cannot sit inside an `if()` argument.
- OSCSender sends only on change: add a per-frame jitter Global (`TapJ = 1 - y`) to read constants.
- OSCSender default port is 9201 (Blender's): always set Port.
- Text: `Align` only matters for multi-line text; text is centred on its Translate. Bold Menlo glyphs are about 0.72 of their height wide.
- Magic opens a project on its first scene.
- Child order: first child is drawn in front.

## Methods that worked (measured against an AVCaptureSession recording of BlackHole)

- Tempo: 24 leaky resonators (Scheirer) on squared low-band log flux, argmax + parabolic refine: within 0.5 %.
- Phase: adaptive oscillator (Large & Kolen) with a von Mises window, kph 0.1, kp 0.01, re-seeded from the bank: about 30 ms error on one track. On the other the error was about 80 ms, mostly a constant offset that the `Lead` Global corrects.
- Kick onset-IOI and kick-reset beat trackers failed (phase near random) because techno rolling basslines put as much low-band flux on the offbeat as the kick.
- Snare/hat: Dixon-style "fraction of the recent max" thresholds; the mean-ratio thresholds fired 6-10 times/s.

## Tooling bugs found (not fixed, out of scope)

- `lab.parse_packet` returns None for OSC addresses whose length is 7 mod 4 (e.g. `/p/LVol`); Magic's packets are correct.
- `magicproj check`: `expression_identifiers` strips trailing digits after the first (`aB12` reads as `aB1`), so Global names ending in 2+ digits are reported unknown.
- ffmpeg avfoundation capture of BlackHole drops about 10-14 % of the audio; AVCaptureSession (Swift) is clean.
