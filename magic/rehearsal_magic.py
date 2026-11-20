#!/usr/bin/env python3
"""Generate one low-resolution Magic project for the four live rehearsal cues."""

import argparse
import os
from pathlib import Path
import sys

import magicproj as mp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "osc"))
from show_protocol import (  # noqa: E402
    AUDIO_LEVEL, AUDIO_SUB, CUES, MAGIC_PORT, PLANET_CUES, REACTIVITY,
    ROBOT_FRAMING, ROBOT_HIT, ROBOT_RESTART, SCENES, SELECTION, WORLD_READY,
)

SIZE = (480, 270)
FPS = 30
OUTPUT_SERVER = "MAGIC_OUT"
PLANET_SERVER = "CAM_OUT - Blender"
ROBOT_SERVER = "ROBOT_LIVE - Blender"
SCENE_PORT = 9201


def expression(source):
    return [("Expression", source)]


def video(scene, path, project_dir, speed=None, restart=False):
    params = {
        "File": os.path.relpath(path, project_dir),
        "Audio": 0,
        "Looping": 1,
        "Speed": ("global:ShowPhase", expression(speed), 1) if speed else 1,
    }
    if restart:
        params["Goto Start"] = ("global:RobotStartPulse", [], 0)
    return scene.node("VideoFile", params)


def select(scene, inputs, source, modifiers=()):
    return scene.node("InputSelector", {"Input #": (source, modifiers, 0)}, inputs=inputs)


def audio_globals(builder, osc_audio=False):
    volume = f"osc:{AUDIO_LEVEL}" if osc_audio else "audio:Source 0:Volume"
    subbass = f"osc:{AUDIO_SUB}" if osc_audio else "audio:Source 0:Freq. Range:20-80 Hz"
    builder.glob("Volume", 0, volume, [("Smooth", 0.65)])
    builder.glob("SubBass", 0, subbass,
                 [("Scale", 4), ("Smooth", 0.55), *expression("min(1, max(0, x))")])
    builder.glob("Bass", 0, "global:SubBass", expression("max(x, min(1, Volume*0.8))"))
    builder.glob("BassAverage", 0, "global:SubBass", [("Smooth", 0.93)])
    builder.glob("Beat", 0, "calc", expression("min(1, max(0, (SubBass - BassAverage)*3))"))


def robot_heartbeat(builder):
    builder.glob("RobotHeartbeat", 0, "osc:/vj/live_layer")
    builder.glob("PreviousRobotHeartbeat", 0, "calc", expression("RobotHeartbeat"))
    builder.glob("RobotLiveUntil", 0, "calc",
                 expression("if(RobotHeartbeat != PreviousRobotHeartbeat, MotionClock + 1.5, y)"))
    builder.glob("RobotLiveReady", 0, "calc", expression("if(MotionClock < RobotLiveUntil, 1, 0)"))


def cinema_globals(builder):
    builder.glob("RobotZoom", 1, f"osc:{ROBOT_FRAMING}", expression("min(3, max(1, x))"))
    center = expression("min(1 - 0.5/max(1, RobotZoom), max(0.5/max(1, RobotZoom), x))")
    builder.glob("RobotCenterX", 0.5, f"osc:{ROBOT_FRAMING} 1", center)
    builder.glob("RobotCenterY", 0.5, f"osc:{ROBOT_FRAMING} 2", center)
    builder.glob("RobotHitX", 0.5, f"osc:{ROBOT_HIT}", expression("min(1, max(0, x))"))
    builder.glob("RobotHitY", 0.5, f"osc:{ROBOT_HIT} 1", expression("min(1, max(0, x))"))
    builder.glob("RobotHitRaw", 0, f"osc:{ROBOT_HIT} 2")
    builder.glob("RobotHitPrevious", 0, "calc", expression("RobotHitRaw"))
    builder.glob("RobotHitUntil", 0, "calc",
                 expression("if(RobotHitRaw != RobotHitPrevious, MotionClock + 0.14, y)"))
    builder.glob("RobotHitStrength", 0, "global:RobotHitRaw",
                 expression("min(1, max(0, x))*min(1, max(0, (RobotHitUntil-MotionClock)/0.07))"))
    builder.glob("RobotRestartToken", 0, f"osc:{ROBOT_RESTART}")
    builder.glob("RobotRestartPrevious", 0, "calc", expression("RobotRestartToken"))
    builder.glob("RobotRestartUntil", 0, "calc",
                 expression("if(RobotRestartToken != RobotRestartPrevious, MotionClock + 0.08, y)"))
    builder.glob("RobotStartPulse", 0, "calc", expression("if(MotionClock < RobotRestartUntil, 1, 0)"))


def frame_robot(scene, composite, size):
    """Apply the same crop to the Live World, fighters and any local Hit accent."""
    impact = scene.node("Radial Gradient", {
        "Radius1": 0,
        "Radius2": 0.075,
        "Location X": ("global:RobotHitX", [], 0.5),
        "Location Y": ("global:RobotHitY", expression("1 - x"), 0.5),
        "StartColor R": 1, "StartColor G": 0.58, "StartColor B": 0.24,
        "StartColor A": ("global:RobotHitStrength", expression("0.24*x"), 0),
        "EndColor R": 1, "EndColor G": 0.40, "EndColor B": 0.11, "EndColor A": 0,
    })
    over = scene.node("Transparency", {"Amount": 0}, inputs=[impact, composite])
    source = select(scene, [composite, over], "global:RobotHitStrength", expression("if(x > 0.001, 1, 0)"))
    scale = scene.node("Scale", {"X": ("global:RobotZoom", [], 1), "X For All": 1}, inputs=[source])
    return scene.node("Translate", {
        "X": ("global:RobotCenterX", expression(f"(1 - 2*x)*RobotZoom*{size[0] / size[1]:.8g}"), 0),
        "Y": ("global:RobotCenterY", expression("(2*x - 1)*RobotZoom"), 0),
    }, inputs=[scale])


def live_controls(builder, master, planet_live, robot_live, port, release_index, peak_index, linked_world,
                  audio_probe=False):
    robot = f"ProgramScene == {SCENES.index('robot')}"
    bass_amount = f"if({robot}, 1, 0.20)" if planet_live else "1"
    beat_amount = f"if({robot}, 1, 0.14)" if planet_live else "1"
    energy = f"min(1, 0.22 + x*Reactivity*0.45 + if(ShowPhase == {peak_index}, 0.32, 0))"
    if planet_live:
        energy = f"if({robot}, {energy}, 0.10)"
    controls = {
        "/vj/bass": ("Bass", [("Smooth", 0.83), *expression(f"x*Reactivity*{bass_amount}")]),
        "/vj/beat": ("Beat", [("Smooth", 0.78), *expression(f"x*Reactivity*{beat_amount}")]),
        "/vj/energy": ("Volume", expression(energy)),
    }
    if audio_probe:
        controls["/show/audio_check/time"] = ("AudioFileTime", [])
        controls["/show/audio_check/playing"] = ("AudioFilePlaying", [])
        controls["/show/audio_check/volume"] = ("Volume", [])
    refresh = {}
    if planet_live:
        controls["/vj/level"] = ("Volume", [("Smooth", 0.88), *expression("min(0.58, 0.50 + max(0, x)*Reactivity*0.08)")])
        if not linked_world:
            # The linked controller applies the whole preset at once. A stand-alone
            # Planet cannot do that, so Magic sends and refreshes its held values.
            for address, arrive in PLANET_CUES["arrive"].items():
                release = PLANET_CUES["release"][address]
                preset = f"{arrive:g}" if release == arrive else f"if(x == {release_index}, {release:g}, {arrive:g})"
                controls[address] = ("ShowPhase", expression(preset))
                if arrive or release:
                    refresh[address] = 0.000001
            controls["/vj/takeover"] = ("ShowPhase", expression("0.33"))
            refresh["/vj/takeover"] = 0.001  # keeps the scene's idle shock timer off during silence
    if robot_live:
        controls["/vj/angle"] = ("ShowPhase", expression(f"if(x == {peak_index}, 2, 0)"))
        if not linked_world:
            refresh["/vj/angle"] = 0.000001

    out = builder.scene("OSC Out")
    # OSCSender sends on change. The falling edge reasserts the exact value.
    for address, (source, modifiers) in controls.items():
        if address in refresh:
            modifiers = modifiers + expression(f"x + if(frac(MotionClock) < 0.08, {refresh[address]:g}, 0)")
        out.output(out.node("OSCSender", {
            "IP Addr.": "127.0.0.1", "Port": port, "Message": address,
            "Value": (f"global:{source}", modifiers, 0),
        }))
    return master.scene_module(out)


def build(project_dir, planet, robot, peak=None, release=None, osc_in=MAGIC_PORT,
          server=OUTPUT_SERVER, audio_device="BlackHole 2ch", *, planet_live=None,
          robot_live=None, osc_out=SCENE_PORT, audio_file=None, linked_world=False, osc_audio=False,
          size=SIZE, robot_cinema=False):
    if bool(planet_live) == bool(planet):
        raise ValueError("Choose a Planet loop or a live Planet source.")
    if planet_live and release is not None:
        raise ValueError("Use the live Planet source for both Arrive and Release.")
    if linked_world and not (planet_live and robot_live):
        raise ValueError("World linking requires both live sources.")
    builder = mp.Builder(syphon=server, size=size, fps=FPS, audio_device=audio_device, osc_in=osc_in)
    cue_count = len(CUES)
    scene_count = len(SCENES)
    peak_index = tuple(CUES).index("peak")
    release_index = tuple(CUES).index("release")
    builder.glob("ProgramSelection", 0, f"osc:{SELECTION}",
                 expression(f"min({cue_count * scene_count - 1}, max(0, floor(x + 0.5)))"))
    builder.glob("ProgramScene", 0, "global:ProgramSelection", expression(f"x % {scene_count}"))
    builder.glob("ShowPhase", 0, "global:ProgramSelection", expression(f"floor(x / {scene_count})"))
    builder.glob("Reactivity", 0, f"osc:{REACTIVITY}", expression("min(1, max(0, x))"))
    audio_globals(builder, osc_audio)
    if audio_file is not None and (planet_live or robot_live):
        builder.glob("AudioFilePlaying", 0, "internal:Audio/MIDI Playing")
        builder.glob("AudioFileTime", 0, "internal:Playback Time")
    builder.glob("MotionClock", 0, "calc", [("Increase", 1)])
    if robot_cinema:
        cinema_globals(builder)
    program_scene = "global:ProgramScene"
    if robot_live:
        robot_heartbeat(builder)
        robot_unready = f"(x == {SCENES.index('robot')} and RobotLiveReady < 0.5)"
        unavailable = robot_unready
        if linked_world:
            builder.glob("WorldReady", 0, f"osc:{WORLD_READY}")
            unavailable = f"x != WorldReady or {robot_unready}"
        builder.glob("LiveProgramScene", 0, program_scene, expression(f"if({unavailable}, 0, x)"))
        program_scene = "global:LiveProgramScene"

    master = builder.scene("Master")
    safe = builder.scene("Safe")
    safe.output(safe.node("Linear Gradient", {
        "Curve": 1,
        "Frequency": 2,
        "Vertical": 1,
        "Offset": ("global:MotionClock", expression("frac(x / 14)"), 0),
        "StartColor R": 0.025, "StartColor G": 0.055, "StartColor B": 0.09,
        "EndColor R": 0.09, "EndColor G": 0.30, "EndColor B": 0.37,
    }))

    planet_scene = builder.scene("Synthwave Planet")
    if planet_live:
        planet_scene.output(planet_scene.node("SyphonClient", {"Server": planet_live}))
    else:
        planet_video = video(planet_scene, planet, project_dir, f"if(x == {release_index}, 0.8, 1)" if release is None else None)
        if release is not None:
            release_video = video(planet_scene, release, project_dir)
            planet_video = select(planet_scene, [planet_video, release_video], "global:ShowPhase",
                                  expression(f"if(x == {release_index}, 1, 0)"))
        planet_scene.output(planet_video)

    robot_scene = builder.scene("Robot")
    robot_video = video(robot_scene, robot, project_dir, f"if(x == {peak_index}, 1.12, 1)"
                       if peak is None and not robot_cinema else None, restart=robot_cinema)
    if peak is not None:
        peak_video = video(robot_scene, peak, project_dir, restart=robot_cinema)
        robot_video = select(robot_scene, [robot_video, peak_video], "global:ShowPhase",
                             expression(f"if(x == {peak_index}, 1, 0)"))
    if robot_live:
        world = robot_scene.node("SyphonClient", {"Server": robot_live})
        matte = robot_scene.node("Mask", {"Use Alpha": 1}, inputs=[robot_video, robot_video])
        robot_video = robot_scene.node("Transparency", {"Amount": 0}, inputs=[matte, world])
    if robot_cinema:
        robot_video = frame_robot(robot_scene, robot_video, size)
    robot_scene.output(robot_video)

    sources = {"safe": safe, "planet": planet_scene, "robot": robot_scene}
    program = select(master, [master.scene_module(sources[name]) for name in SCENES], program_scene)
    brightness = f"min(0.09, x*Reactivity*if(ShowPhase == {peak_index}, 0.22, 0.14))"
    if planet_live:
        planet_condition = f"ProgramScene == {SCENES.index('planet')}"
        brightness = f"if({planet_condition}, min(0.025, x*Reactivity*0.04), {brightness})"
    glow_modifiers = [("Smooth", 0.84)] if planet_live else []
    grade = master.node("Color Controls", {
        "Bright": ("global:Bass", glow_modifiers + expression(brightness), 0),
        "Saturation": ("global:ShowPhase", expression(
            f"if(x == {release_index}, 0.85, if(x == {peak_index}, 1.08, 1))"
        ), 1),
    }, inputs=[program], bypass=(program_scene, expression("if(x == 0, 1, 0)"), 1))
    master.output(grade)
    if planet_live or robot_live:
        master.output(live_controls(builder, master, planet_live, robot_live, osc_out, release_index, peak_index,
                                    linked_world, audio_file is not None))

    root = builder.build()
    if audio_file is not None:
        root = mp.add_audio(root, str(audio_file))
        for item in root.findall('./SoundFiles/SoundFile') + root.findall('./AudioFiles/AudioFile'):
            item.set('isMuted', '1')
    for value in root.findall(".//InputValue[@name='File']"):
        value.set("absoluteFilename", str((project_dir / value.get("value")).resolve()))
    return root


def media_path(text):
    path = Path(text).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"media file not found: {path}")
    return path


def canvas_size(text):
    try:
        width, height = (int(part) for part in text.lower().split("x"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT") from exc
    if min(width, height) < 1:
        raise argparse.ArgumentTypeError("size must have positive dimensions")
    return width, height


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    planet = parser.add_mutually_exclusive_group(required=True)
    planet.add_argument("--planet", type=media_path, help="Planet loop for Arrive")
    planet.add_argument("--planet-live", nargs="?", const=PLANET_SERVER, metavar="SERVER", help="live Planet Syphon source")
    parser.add_argument("--robot", type=media_path, required=True, help="Robot Clip for Build")
    parser.add_argument("--robot-live", nargs="?", const=ROBOT_SERVER, metavar="SERVER",
                        help="composite alpha-preserving Robot Clips over live Syphon")
    parser.add_argument("--robot-cinema", action="store_true", help="enable OSC Robot framing, localized Hit and restart")
    parser.add_argument("--linked-world", action="store_true",
                        help="wait for the selected Blender world to report readiness")
    parser.add_argument("--peak", type=media_path, help="optional Robot Clip for Peak")
    parser.add_argument("--release", type=media_path, help="optional Planet loop for Release")
    parser.add_argument("--out", type=Path, required=True, help="generated .magic file")
    parser.add_argument("--osc-in", type=int, default=MAGIC_PORT)
    parser.add_argument("--osc-out", type=int, default=SCENE_PORT, help="live scene OSC destination port")
    parser.add_argument("--server", default=OUTPUT_SERVER)
    parser.add_argument("--size", type=canvas_size, default=SIZE, metavar="WIDTHxHEIGHT",
                        help="Magic canvas and Syphon dimensions (default 480x270)")
    parser.add_argument("--audio-device", default="BlackHole 2ch")
    audio = parser.add_mutually_exclusive_group()
    audio.add_argument("--audio-file", type=media_path, help="use a project audio file instead of live input")
    audio.add_argument("--osc-audio", action="store_true", help="receive score level and low-band intensity over OSC")
    args = parser.parse_args()
    if args.planet_live and args.release:
        parser.error("--release belongs with --planet. The Planet live source handles both phases.")
    if args.linked_world and not (args.planet_live and args.robot_live):
        parser.error("--linked-world needs both --planet-live and --robot-live.")
    out = args.out.expanduser().resolve()
    media = (args.planet, args.robot, args.peak, args.release)
    if out in (*media, args.audio_file):
        parser.error("output must be separate from the media files")
    root = build(out.parent, *media, osc_in=args.osc_in, server=args.server, audio_device=args.audio_device,
                 planet_live=args.planet_live, robot_live=args.robot_live, osc_out=args.osc_out,
                 audio_file=args.audio_file, linked_world=args.linked_world, osc_audio=args.osc_audio,
                 size=args.size, robot_cinema=args.robot_cinema)
    out.parent.mkdir(parents=True, exist_ok=True)
    mp.write(out, root)
    print(f"wrote {out} ({args.size[0]}x{args.size[1]}, OSC {args.osc_in}, Syphon {args.server})")


if __name__ == "__main__":
    main()
