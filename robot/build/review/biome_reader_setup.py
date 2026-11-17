"""Set up the Geo-Scatter Biome Reader for the Robot Scene's Arclink backdrop, and record what it changes.

Runs in Blender with the user's preferences loaded (no --factory-startup), in a Blender slot:

    B=/Applications/Blender.app/Contents/MacOS/Blender
    $B -b -P robot/build/review/biome_reader_setup.py -- dump OUT_DIR/before.json
    $B -b --command extension install-file -r user_default --enable robot/assets/geoscatter/_zips/Biome-Reader_5.6.4_for_b3d_5.2.zip
    $B -b -P robot/build/review/biome_reader_setup.py -- configure SCATPACK... KIT_DIR...
    $B -b -P robot/build/review/biome_reader_setup.py -- dump OUT_DIR/after.json

`configure` turns the automatic store fetch off, installs each SCATPACK (a .scatpack copy of a pack's biome zip,
e.g. robot/assets/arclink_biomes/_zips/arclink_city_biomes.scatpack) into the Biome Reader's scatter library, adds
each KIT_DIR (the folder of a kit's .blend) as a search path for the biomes' assets, and saves the user preferences. `dump` writes the preferences that matter here
as JSON, so before and after can be diffed with jq.
"""
import json
import os
import sys

import bpy

EXT = "bl_ext.user_default.biome_reader"


def _addon_prefs():
    addon = bpy.context.preferences.addons.get(EXT)
    return addon.preferences if addon else None


def dump(out):
    prefs = bpy.context.preferences
    rep = {
        "blender": bpy.app.version_string,
        "enabled_addons": sorted(a.module for a in prefs.addons),
        "extension_repos": [{"name": r.name, "module": r.module, "enabled": r.enabled, "directory": r.directory}
                            for r in prefs.extensions.repos],
        "online_access": bpy.app.online_access,
        "asset_libraries": [{"name": l.name, "path": l.path} for l in prefs.filepaths.asset_libraries],
        "biome_reader": None,
    }
    ap = _addon_prefs()
    if ap:
        rep["biome_reader"] = {
            "fetch_automatic_allow": ap.fetch_automatic_allow,
            "fetch_automatic_daycount": ap.fetch_automatic_daycount,
            "library_path": ap.library_path,
            "blend_environment_paths": [p.blend_folder for p in ap.blend_environment_paths],
        }
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as f:
        json.dump(rep, f, indent=1, sort_keys=True)
    print("dumped", out)


def configure(paths):
    """paths: .scatpack files to install, and folders holding the kits' .blend files to add as search paths."""
    ap = _addon_prefs()
    if ap is None:
        sys.exit("biome_reader is not enabled; install it first")
    ap.fetch_automatic_allow = False
    for p in paths:
        if p.endswith(".scatpack"):
            bpy.ops.scatter5.install_package(filepath=os.path.abspath(p), popup_menu=False)
            print("installed", p)
            continue
        folder = os.path.abspath(p) + os.sep
        if folder not in [b.blend_folder for b in ap.blend_environment_paths]:
            item = ap.blend_environment_paths.add()
            item.name = os.path.basename(os.path.dirname(folder))
            item.blend_folder = folder
            print("search path", folder)
    bpy.ops.wm.save_userpref()


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    if args[0] == "dump":
        dump(args[1])
    elif args[0] == "configure":
        configure(args[1:])
    else:
        sys.exit("usage: -- dump OUT.json | configure SCATPACK... KIT_DIR...")


main()
