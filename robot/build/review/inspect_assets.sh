#!/bin/zsh
# inspect_assets.sh: inspect_asset.py on every downloaded .blend of the robot picks (auto-run off), one report per
# asset under robot/build/probe/asset/<folder>/. Read report.json and every texts/ file before anything runs.
cd "${0:A:h}/../../.."
B=/Applications/Blender.app/Contents/MacOS/Blender
pgrep -i blender >/dev/null && { echo "a Blender runs; one at a time"; exit 1; }
for f in "robot/assets/humanoid_m2000/extracted/HUMANOID M2000/DROID.blend" \
         "robot/assets/juno_android/extracted/ANDROID. JUNO FEMALE B/ANDROID.blend" \
         "robot/assets/arclink_megapolis/extracted/GT ArcLink City Data Megapolis.blend"; do
  [[ -f $f ]] || { echo "missing: $f"; continue; }
  n=$(basename "$(dirname "$f")")
  $B -b --factory-startup "$f" -P robot/build/review/inspect_asset.py -- "robot/build/probe/asset/$n" > "robot/build/probe/asset/$n.log" 2>&1
  echo "$n: $(grep -c . "robot/build/probe/asset/$n.log") log lines, $(ls "robot/build/probe/asset/$n/texts" 2>/dev/null | wc -l | tr -d ' ') text blocks"
done
