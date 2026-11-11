"""Copy the Wanderer's Mixamo clips from the downloads into the slot files the scene loads.

python3 -I tools/godot_mixamo_copy.py <downloads dir> <godot/colossus/assets/mixamo>

The slot table is godot/colossus/wanderer/clips.gd; godot/colossus/assets/MODELS.md lists the same
download for each slot. A slot whose download is missing is left alone (it plays its fallback).
"""

import pathlib
import shutil
import sys

# Slot file -> Mixamo download, named as Mixamo names the file (clip name + .fbx); the ones not
# downloaded yet are the clips MODELS.md asks for.
CLIPS = {
    "idle.fbx": "Idle.fbx",
    "walk.fbx": "Walking-2.fbx",
    "run.fbx": "Fast Run.fbx",
    "hang_idle.fbx": "Braced Hang.fbx",
    # Leads with the left hand (checked against "Braced Hang Shimmy-2", the same move with root motion).
    "shimmy_left.fbx": "Braced Hang Shimmy.fbx",
    "shimmy_right.fbx": "Right Braced Hang Shimmy.fbx",
    # A looping climb: "Braced Hang Hop Up" is a one-shot hop onto a ledge and pops when it loops.
    "climb_up.fbx": "Climbing Up Wall.fbx",
    "climb_down.fbx": "Climbing Down Wall.fbx",
    "hang_swing.fbx": "Hanging Idle.fbx",
    "fall_idle.fbx": "Falling Idle.fbx",
    "stand_up.fbx": "Standing Up.fbx",
}


def main() -> None:
    downloads = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for slot, name in CLIPS.items():
        src = downloads / name
        if src.is_file():
            shutil.copyfile(src, out / slot)
            print(f"{slot:18} <- {name}")
        else:
            print(f"{slot:18}    missing: {name}")


main()
