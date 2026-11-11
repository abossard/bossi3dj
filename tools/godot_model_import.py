"""Write the import settings of the prepared models into their .import files (git-ignored with them).

python3 -I tools/godot_model_import.py godot/colossus/assets/models

Run after a first `godot --import` has written the files, then import again: Godot re-imports
whatever settings changed. Textures: VRAM compressed with mipmaps (Godot's headless import picks
lossless without mipmaps), normal maps flagged. Grock: scaled to 28 m at import, clips and rest
with it (its prepared glTF is 1.9952 units tall, see tools/godot_prepare_models.py).
"""

import pathlib
import re
import sys

SCENE_PARAMS = {"grock/grock.gltf.import": {"nodes/root_scale": "14.0339"}}


def set_param(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    if pattern.search(text):
        return pattern.sub(line, text)
    return text.replace("[params]\n", f"[params]\n\n{line}\n", 1)


def main() -> None:
    root = pathlib.Path(sys.argv[1])
    changed = 0
    for imp in sorted(root.glob("*/textures/*.import")):
        normal = "normal" in imp.name.lower()
        text = imp.read_text()
        new = text
        for key, value in (
            ("compress/mode", "2"),
            ("mipmaps/generate", "true"),
            ("compress/normal_map", "1" if normal else "2"),
            ("detect_3d/compress_to", "0"),
        ):
            new = set_param(new, key, value)
        if new != text:
            imp.write_text(new)
            changed += 1
    for rel, params in SCENE_PARAMS.items():
        imp = root / rel
        text = imp.read_text()
        new = text
        for key, value in params.items():
            new = set_param(new, key, value)
        if new != text:
            imp.write_text(new)
            changed += 1
    print(f"import settings written to {changed} files under {root}")


main()
