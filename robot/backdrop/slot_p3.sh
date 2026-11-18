#!/bin/zsh
# Backdrop round P3 Blender slot: every plate fresh on the current robot.blend, then the 8 variants of the 3 plates
# that failed P2 (docs/handover/robot-assets.md). Writes robot/build/probe/backdrop/slot_p3.DONE when finished.
set -e
cd "$(dirname "$0")/../.."
R="python3 -I robot/backdrop/render_plates.py"
rm -f robot/build/probe/backdrop/slot_p3.DONE
eval $R render
eval $R render chipset_04 --angles front --set sky=0.03 --tag _a
eval $R render chipset_04 --angles front --set sky=0.03 rim=3 --tag _b
eval $R render chipset_04 --angles front --set sky=0.03 rim=3 fill=1 scale=20 "'area=[120,120]'" --tag _c
for n in 1 2 3; do eval $R render greeble_01 --angles front --set y0=16 seed=$n --tag _s$n; done
eval $R render greeble_01 --angles duel_low --set scale=16 "'area=[800,800]'" y0=15 sky=0.03 --tag _a
eval $R render greeble_01 --angles duel_low --set scale=12 "'area=[600,600]'" y0=20 sky=0.03 rim=3 --tag _b
touch robot/build/probe/backdrop/slot_p3.DONE
