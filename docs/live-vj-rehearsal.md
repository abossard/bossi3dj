# Live VJ showreel

One Magic project mixes two worlds from one Blender session. The dashboard switches both apps and exposes the same controls through its local HTTP API. Magic publishes the programme at 480×270. The eight-minute reel records that Syphon output at 24 fps against an original 128 BPM score.

| Time | Cue | Live programme |
| --- | --- | --- |
| 0:00 | Arrive | The live Synthwave Planet Scene holds a slow twilight orbit around the pyramids. |
| 2:00 | Build | Magic composites solo Android Clips and their ground shadows over the live Arclink foundry. |
| 4:00 | Peak | The matched wide Angle reveals the six-metre Security Bot. The live cyan and amber lamps respond to the score. |
| 6:00 | Release | The live Planet returns in a slow Moon vantage. |

The Planet uses the existing Path Camera and the user’s sky-framing choices. Camera presets apply once per cue. The live profile slows both views, removes beat-driven camera tilt, and keeps strobe, automatic shocks and fast fog changes out of the reel. Magic sends smoothed audio controls to the active world. [Planet look decision](https://github.com/abossard/bossi3dj/issues/25#issuecomment-6938464028) · [Moon framing](https://github.com/abossard/bossi3dj/issues/30#issuecomment-6938568251)

The Robot Live World follows the Arclink Dark direction. Blender loads six mesh types from the downloaded Megapolis library and instances them around the arena. Each Robot cue uses one matched Camera Track. The pre-rendered beauty and Shadow Pass take one alpha movie per cue, while Blender draws the background and its lights directly. [Robot Live World brief](https://github.com/abossard/bossi3dj/issues/22) · [Asset picks](https://github.com/abossard/bossi3dj/issues/27#issuecomment-6941633671) · [Asset handover](handover/robot-assets.md)

## Run the live setup

The generated project for the reel is `docs/video/rehearsal-live/capture.magic`. Keep its `media` folder beside it. The linked dashboard starts on Safe. The recording tool measures broadband and subbass levels from the score and sends them to Magic on the capture clock. Magic shapes the lighting and passes its controls to Blender. The tool adds the same score to the captured programme file. In rehearsal, Magic read zero from both BlackHole and its own file playback.

Run the dashboard and Blender in separate terminals from the repo root. Open one Blender process with the commands below, then load the Magic project. The dashboard is on `127.0.0.1:8766`. [Open dashboard](http://127.0.0.1:8766/)

```sh
python3 osc/show_dashboard.py --blender-port 9203
```

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --window-geometry 25 90 1010 650 --enable-autoexec \
  "$PWD/blender/scenes/synthwave_planet.blend" \
  --python "$PWD/tools/live_blender_show.py"
```

```sh
python3 magic/magicproj.py load docs/video/rehearsal-live/capture.magic
```

The dashboard shows the requested cue and offers direct scene selection, Reactivity and **Safe**. The two worlds publish `CAM_OUT - Blender` and `ROBOT_LIVE - Blender`. Magic uses Safe while the chosen world starts drawing. Keep Blender visible in its current Space during the performance.

The API exposes `GET /api/show`, `PUT /api/show/cue` with `{"cue":"peak"}` or `{"scene":"safe"}`, and `PUT /api/show/reactivity` with `{"value":0.35}`. Send `PUT` bodies as `application/json`.

## Build and capture again

Run `make venv` if the repo’s Python environment needs NumPy and Pillow. The Robot foreground build reads v1 beauty and Shadow Pass media. Blender loads the Arclink library from `robot/assets/arclink_megapolis/extracted/`.

```sh
.venv/bin/python tools/rehearsal_reel.py --foreground-only --output docs/video/rehearsal-live/media
python3 magic/rehearsal_magic.py --planet-live --robot-live --linked-world --osc-audio \
  --robot docs/video/rehearsal-live/media/build-alpha.mov \
  --peak docs/video/rehearsal-live/media/peak-alpha.mov \
  --out docs/video/rehearsal-live/capture.magic
.venv/bin/python tools/live_rehearsal_capture.py docs/video/rehearsal-live --probe-only
```

Reload `capture.magic` after the cue probe to rewind the Clips. The capture command supplies the music measurements, switches cues every two minutes, records `MAGIC_OUT` and returns to Safe when it finishes. The export is `docs/video/rehearsal-live/bossi3dj-live-showreel.mp4`. `capture-controls.jsonl` records the OSC values Blender received.

```sh
caffeinate -di .venv/bin/python tools/live_rehearsal_capture.py \
  docs/video/rehearsal-live --record-only --osc-score
.venv/bin/python tools/rehearsal_review.py \
  docs/video/rehearsal-live/bossi3dj-live-showreel.mp4 docs/video/rehearsal-live/review
```

The six-metre opponent uses the Security Bot Rig by Blender Foundation, CC BY, modified for the Robot Scene. [Security Bot Rig](https://studio.blender.org/characters/security-bot/v1/)

## Take review

The recording ran for 480.03 seconds at the receiver and produced 11,520 frames. The receiver reused its last frame 18 times. The export contains exactly four 120-second chapters. The black-frame scan reported zero intervals of at least 0.4 seconds. The 99th-percentile change in average brightness was 0.89, 1.12, 0.56 and 0.18 out of 255 for Arrive, Build, Peak and Release, with the three cue changes excluded. [Capture measurements](video/rehearsal-live/review/measurements.json)

The wide Exchange at the start of Peak gives the clearest sense of scale. Build keeps the Android readable but repeats its central guard silhouette. Release gives the Moon a clean outline over the ridge, although the quiet opening stays nearly still for about eleven seconds. The four contact sheets showed no conspicuous blanking, inversion or subject clipping.
