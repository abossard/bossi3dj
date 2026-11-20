# Chrome Foundry Robot Scene

The one-minute cinema pass has a solo Android section and a wide reveal of the six-metre Security Bot. Magic plays the transparent Clips and Shadow Passes over a live Blender foundry at 960×540. Magic crops the fighters, floor and background together for the closer views. The cuts land on bar lines. [Original mockups](../robot/concept/robot-scene.html) · [User’s opponent choice](https://github.com/abossard/bossi3dj/issues/23#issuecomment-6944388011)

The foundry keeps the downloaded Arclink Dark geometry and uses warm sodium pools, furnace channels and cool edge fill. The edit places short gold sparks at projected Clip Data Hits. Each burst travels with its Clip, so the sparks and impacts share the same frames. The director holds each framing through the Move. [Live World brief](https://github.com/abossard/bossi3dj/issues/22) · [Arclink choice](https://github.com/abossard/bossi3dj/issues/27#issuecomment-6941633671)

## Run the cinema pass

The cinema files are in `docs/video/rehearsal-robot-cinema-v2/`. Run these commands from the repo root. Use separate terminals for the dashboard and Blender, and keep a single Blender process.

```sh
.venv/bin/python tools/robot_cinema.py
python3 magic/rehearsal_magic.py --planet-live --robot-live --linked-world \
  --osc-audio --robot-cinema --size 960x540 \
  --robot docs/video/rehearsal-robot-cinema-v2/build-alpha.mov \
  --peak docs/video/rehearsal-robot-cinema-v2/peak-alpha.mov \
  --out docs/video/rehearsal-robot-cinema-v2/chrome-foundry.magic
python3 osc/show_dashboard.py --blender-port 9203
```

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --window-geometry 25 90 1250 760 --enable-autoexec \
  "$PWD/blender/scenes/synthwave_planet.blend" \
  --python "$PWD/tools/live_blender_show.py" -- --robot-cinema
```

```sh
python3 magic/magicproj.py load docs/video/rehearsal-robot-cinema-v2/chrome-foundry.magic
caffeinate -di .venv/bin/python tools/robot_cinema_capture.py
.venv/bin/python tools/rehearsal_review.py \
  docs/video/rehearsal-robot-cinema-v2/chrome-foundry-live.mp4 \
  docs/video/rehearsal-robot-cinema-v2/review --robot-cinema
```

The capture command makes two 30-second takes from `MAGIC_OUT` and joins them to the score. During capture, Magic receives measurements from the score over OSC. The native BlackHole tone probe measured zero after reopening Magic. To try the device reset, open **Input Sources** and reselect the output device. If the input still reads zero, use **Restart Input Device(s)** in the same window.

The dashboard can select Build, Peak or Safe without recording. Live controls accept `/show/robot/framing` with three floats for zoom and normalized source centre, measured from the top left. Send a new integer to `/show/robot/restart` to rewind the active Clip. `director.json` records each cut’s bar time, crop and projected Hits.

The Robot Scene uses a modified version of Blender Foundation’s Security Bot Rig under CC BY. [Security Bot Rig](https://studio.blender.org/characters/security-bot/v1/)

## Capture review

The final export is 60 seconds at 960×540 and 24 fps. The receiver repeated seven of its 1,440 frames. The black-frame scan found no intervals of at least 0.4 seconds. The headless suite and the Blender Chrome Foundry scene check passed. [Capture measurements](video/rehearsal-robot-cinema-v2/review/measurements.json)

The wide reveal at 00:30 shows the scale of the Security Bot. The contact sparks are easiest to see at 00:36.79 and 00:42.90. Both fighters fit head to boots in the revised shot around 00:55. The burst near 00:09 briefly crosses the Android’s face. [Final impact samples](video/rehearsal-robot-cinema-v2/review/impacts-sheet.jpg)
