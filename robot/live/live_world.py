"""Render the Robot Live World in a Blender camera viewport and publish it to Magic.

    Blender --factory-startup -P robot/live/live_world.py -- --angle front

The v1 Camera Tracks are static. Magic's /vj/angle selects the matching Shot
Camera. The Android and the giant machine are drawn by Magic from their Clips.
"""

import argparse
import importlib.util
import json
import math
import site
import socket
import struct
import sys
import time
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = HERE.parent / "package" / "v1"
ARCLINK = HERE.parent / "assets" / "arclink_megapolis" / "extracted" / "GT ArcLink City Data Megapolis.blend"
CITY = "Arclink Megapolis"
# Asset Browser object suffix, then (arena X, arena Y, height, yaw in degrees).
# Keep the floor at zero and the central 7 m radius clear for the two figures.
CITY_LAYOUT = {
    "Large Buildings_3": ((-17, -8, 9.3, 20), (9, 17, 9.8, 145), (-17, 8, 8.1, -17)),
    "Mid Buildings_5": ((-19, 1, 6.7, 50), (16, 12, 7.8, 135), (1, 18, 5.8, 105)),
    "Small Buildings_6": ((-11, -6, 3.5, 15), (11, 10, 4.3, 80), (-12, 5, 3.8, 12)),
    "Passageway_3": ((-9, -3.8, 2.6, 12), (6.6, 7.8, 2.8, 135)),
    "Entrances_5": ((-9, 3.8, 2.3, 25), (3.8, 8.2, 2.5, 122)),
    "Ground Misc_3": ((-6.8, 5.3, 0.4, -30), (5.4, 6.8, 0.44, 120)),
}
CITY_FOOTPRINT = (11, 9, 5, 6, 4, 2)
ANGLES = ("front", "side", "duel_wide", "duel_low")
LOOKS = ("rehearsal", "chrome-foundry")
PORT, SERVER, SIZE = 9201, "ROBOT_LIVE", (640, 360)
TICK, HEARTBEAT_INTERVAL = 1 / 30, 0.5
WORLD_KEY = "robot_live_world"
RUNTIME_KEY = "robot_live_runtime"
SYPHON_KEY = "robot_live_syphon"
CONTROLS = {
    "/vj/angle": "vj_angle",
    "/vj/bass": "vj_bass",
    "/vj/energy": "vj_energy",
    "/vj/beat": "vj_beat",
    "/vj/clip": "vj_clip",
    "/vj/clip_frame": "vj_clip_frame",
}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def material(name, color, glow):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.78
    shader.inputs["Emission Color"].default_value = (*color, 1)
    strength = shader.inputs["Emission Strength"]
    strength.default_value = glow
    return mat, strength


def boxes(collection, name, material, pieces):
    """Build a static batch of cuboids that share a material."""
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    sides = ((3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
    vertices, faces = [], []
    for x, y, z, dx, dy, dz, angle in pieces:
        c, s = math.cos(angle), math.sin(angle)
        offset = len(vertices)
        for height in (-dz / 2, dz / 2):
            for a, b in corners:
                u, v = a * dx / 2, b * dy / 2
                vertices.append((x + c * u - s * v, y + s * u + c * v, z + height))
        faces.extend(tuple(offset + i for i in face) for face in sides)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def shot_cameras(scene):
    cameras = []
    for angle in ANGLES:
        track = json.loads((PACKAGE / "camera" / f"{angle}.json").read_text())
        frame = track["frames"][0]
        fields = ("location", "rotation", "focal_length", "sensor_width")
        if any(any(f[key] != frame[key] for key in fields) for f in track["frames"]):
            raise ValueError(f"{angle} needs animated Camera Track playback")
        data = bpy.data.cameras.new(track["camera"])
        data.lens, data.sensor_width = frame["focal_length"], frame["sensor_width"]
        data.clip_end = 160
        camera = bpy.data.objects.new(track["camera"], data)
        scene.collection.objects.link(camera)
        camera.location = frame["location"]
        camera.rotation_mode = "QUATERNION"
        camera.rotation_quaternion = Quaternion(frame["rotation"]).normalized()
        cameras.append(camera)
    return cameras


def add_arclink(scene):
    """Append selected meshes from the user's Dark kit, including into a running World."""
    if CITY in scene.collection.children:
        return scene.collection.children[CITY]
    if not ARCLINK.is_file():
        print(f"Robot Live World: missing {ARCLINK}; using the built-in staging geometry", flush=True)
        return None

    names = ["GT_AL_Dark " + part for part in CITY_LAYOUT]
    old_images = set(bpy.data.images)
    with bpy.data.libraries.load(str(ARCLINK), link=False) as (source, target):
        missing = set(names) - set(source.objects)
        if missing:
            raise RuntimeError(f"Arclink library missing objects: {', '.join(sorted(missing))}")
        target.objects = names
    textures = 0
    for image in set(bpy.data.images) - old_images:
        filename = Path(image.filepath.replace("\\", "/")).name
        texture = ARCLINK.parent / "textures" / "1K" / filename
        if image.source == "FILE" and not image.packed_file and texture.is_file():
            image.filepath = str(texture)
            image.reload()
            textures += 1

    collection = bpy.data.collections.new(CITY)
    scene.collection.children.link(collection)
    tris = 0
    for (part, placements), asset, max_width in zip(CITY_LAYOUT.items(), target.objects, CITY_FOOTPRINT):
        mesh = asset.data
        source_rotation = asset.matrix_basis.to_quaternion()
        bounds = [source_rotation @ Vector(corner) for corner in asset.bound_box]
        low = Vector(tuple(min(point[i] for point in bounds) for i in range(3)))
        high = Vector(tuple(max(point[i] for point in bounds) for i in range(3)))
        floor_pivot = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
        for i, (x, y, height, yaw) in enumerate(placements, 1):
            rotation = Quaternion((0, 0, 1), math.radians(yaw))
            scale = min(height / max(0.01, high.z - low.z), max_width / max(0.01, high.x - low.x, high.y - low.y))
            obj = bpy.data.objects.new(f"Arclink {part} {i}", mesh)
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = rotation @ source_rotation
            obj.scale = (scale,) * 3
            obj.location = Vector((x, y, 0)) - (rotation @ floor_pivot) * scale
            collection.objects.link(obj)
        tris += len(placements) * sum(len(face.vertices) - 2 for face in mesh.polygons)
        bpy.data.objects.remove(asset)

    for name, energy, color, direction in (
        ("Sodium light", 1.05, (1.0, 0.76, 0.5), (-0.42, 0.36, -1.0)),
        ("City fill", 0.48, (0.45, 0.7, 1.0), (0.5, -0.64, -1.0)),
    ):
        data = bpy.data.lights.new(name, "SUN")
        data.energy, data.color, data.use_shadow = energy, color, False
        sun = bpy.data.objects.new(name, data)
        sun.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        collection.objects.link(sun)

    fallback = scene.objects.get("Bays and stacks")
    if fallback is not None:
        fallback.hide_viewport = fallback.hide_render = True
    scene["robot_environment"] = ARCLINK.name
    print(f"Robot Live World: Arclink Dark, {len(collection.objects) - 2} placements, {tris} triangles, {textures} × 1K maps", flush=True)
    return collection


def build_world(scene=None, *, look=LOOKS[0]):
    """Build into a new, empty scene with no window, publishing, or network side effects."""
    if look not in LOOKS:
        raise ValueError(f"unknown Robot Live World look {look!r}")
    if scene is None:
        scene = bpy.data.scenes.new("Robot Live World")
    scene["robot_look"] = look
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.view_settings.view_transform = "AgX"
    if hasattr(scene.eevee, "taa_samples"):
        scene.eevee.taa_samples = 8
    if hasattr(scene.eevee, "use_shadows"):
        scene.eevee.use_shadows = False
    scene.world = bpy.data.worlds.new("Foundry at night")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.012, 0.022, 0.036, 1)
    background.inputs["Strength"].default_value = 0.4

    floor, _ = material("Graphite floor", (0.022, 0.031, 0.035), 0.45)
    steel, _ = material("Blue steel", (0.038, 0.066, 0.085), 0.55)
    dark, _ = material("Dark structural steel", (0.016, 0.029, 0.044), 0.55)
    cyan, cyan_strength = material("Cooling conduits", (0.009, 0.39, 0.58), 0.52)
    amber, amber_strength = material("Foundry channels", (0.9, 0.195, 0.025), 0.49)

    collection = scene.collection
    boxes(collection, "Ground", floor, [(0, 0, -0.2, 84, 84, 0.4, 0)])
    deck, pylons, cold_lines, warm_lines = [], [], [], []
    for i in range(40):
        angle = i * math.tau / 40
        c, s = math.cos(angle), math.sin(angle)
        tangent = angle + math.pi / 2
        deck.append((5.5 * c, 5.5 * s - 1.2, 0.025, 0.84, 0.58, 0.05, tangent))
        if i % 4 != 3:
            cold_lines.append((5.65 * c, 5.65 * s - 1.2, 0.054, 0.63, 0.135, 0.012, tangent))
        if i % 5 == 0:
            warm_lines.append((4.8 * c, 4.8 * s - 1.2, 0.017, 0.61, 0.14, 0.02, tangent))

    for i in range(10):
        angle = (i + 0.5) * math.tau / 10
        c, s = math.cos(angle), math.sin(angle)
        tangent = angle + math.pi / 2
        height = 3.5 + 0.9 * (i % 3)
        pylons.extend(((12 * c, 12 * s - 1.2, height / 2, 2.7, 0.9, height, tangent),
                       (13.4 * c, 13.4 * s - 1.2, 1.35, 4.3, 1.2, 2.7, tangent)))
        deck.extend(((11.55 * c, 11.55 * s - 1.2, height - 0.38, 2.8, 0.24, 0.34, tangent),
                     (11.5 * c, 11.5 * s - 1.2, 0.63, 3.2, 0.55, 1.25, tangent)))
        cold_lines.extend(((11.39 * c, 11.39 * s - 1.2, height - 0.39, 2.2, 0.1, 0.125, tangent),
                           (11.45 * c, 11.45 * s - 1.2, 2.05, 0.18, 0.12, 2.85, tangent)))
        warm_lines.append((11.03 * c, 11.03 * s - 1.2, 0.68, 1.57, 0.11, 0.14, tangent))

    for i in range(12):
        angle = (i + 0.25) * math.tau / 12
        x, y = 21 * math.cos(angle), 21 * math.sin(angle)
        height = 5.7 + 1.3 * (i % 4)
        pylons.append((x, y, height / 2, 3.6, 4.8, height, angle))
        cold_lines.append((0.93 * x, 0.93 * y, height - 0.7, 0.2, 1.05, 0.145, angle))

    boxes(collection, "Bays and stacks", dark, pylons)
    boxes(collection, "Foundry deck and rails", steel, deck)
    boxes(collection, "Cooling conduits and rim", cyan, cold_lines)
    boxes(collection, "Furnace mouths and markers", amber, warm_lines)
    cameras = shot_cameras(scene)
    scene.camera = cameras[0]
    add_arclink(scene)
    sparks = None
    if look == "chrome-foundry":
        detail = load_module(HERE / "foundry_detail.py", "robot_foundry_detail")
        sparks = detail.build(scene, floor, PACKAGE, boxes, material)
    return World(scene, cameras, cyan_strength, amber_strength, sparks)


class World:
    def __init__(self, scene, cameras, cyan, amber, sparks):
        self.scene, self.cameras = scene, cameras
        self.cyan, self.amber = cyan, amber
        self.sparks = sparks
        self.started = self.last_tick = time.monotonic()
        self.bass = self.energy = self.beat = 0.0
        self.smooth_bass = self.smooth_energy = self.accent = 0.0
        self.breath_time = 0.0
        self.beat_at = float("-inf")

    def control(self, address, value, now):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return False
        if address == "/vj/angle" and 0 <= value < len(self.cameras) and value == int(value):
            camera = self.cameras[int(value)]
            if camera != self.scene.camera:
                self.scene.camera = camera
        elif address == "/vj/bass":
            self.bass = min(1, max(0, value))
        elif address == "/vj/energy":
            self.energy = min(1, max(0, value))
        elif address == "/vj/beat":
            if value >= 0.5 and self.beat < 0.5:
                self.beat_at = now
            self.beat = value
        elif self.sparks is not None and address in ("/vj/clip", "/vj/clip_frame") and 0 <= value == int(value):
            if address == "/vj/clip":
                self.sparks.select_clip(int(value))
            else:
                self.sparks.select_frame(int(value))
        else:
            return False
        return True

    def animate(self, now):
        # Cap catch-up after a scene switch or a slow frame so the glow cannot jump.
        dt = min(0.065, max(0.0, now - self.last_tick))
        self.last_tick = now
        self.breath_time += dt
        blend = -math.expm1(-dt / 0.8)
        self.smooth_bass += (self.bass - self.smooth_bass) * blend
        self.smooth_energy += (self.energy - self.smooth_energy) * blend
        beat_glow = math.exp(-(now - self.beat_at) / 0.65)
        self.accent += (beat_glow - self.accent) * blend
        breathing = (1 - math.cos(self.breath_time * math.tau / 14)) / 2
        self.cyan.default_value = 0.52 + 0.18 * self.smooth_energy + 0.045 * breathing
        self.amber.default_value = 0.49 + 0.15 * self.smooth_bass + 0.16 * self.accent
        if self.sparks is not None and self.scene.camera in self.cameras:
            angle = ANGLES[self.cameras.index(self.scene.camera)]
            self.sparks.tick(angle, self.scene.camera, now)

    def tick(self, controls=None, now=None):
        """Apply bridge properties from the scene, or another scene owned by the bridge."""
        if controls is None:
            controls = self.scene
        if now is None:
            now = time.monotonic()
        for address, key in CONTROLS.items():
            if key in controls:
                self.control(address, controls[key], now)
        self.animate(now)


class LiveWorld:
    def __init__(self, world, angle, port, server, size, heartbeat_port):
        self.world, self.scene = world, world.scene
        self.scene.camera = world.cameras[ANGLES.index(angle)]
        self.server, self.size = server, size
        self.scene.render.resolution_x, self.scene.render.resolution_y = size
        bridge = load_module(ROOT / "blender" / "blender_osc_bridge.py", "robot_osc_parser")
        self.parse_packet = bridge.parse_packet
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(("127.0.0.1", port))
            self.sock.setblocking(False)
            heartbeat = load_module(HERE / "heartbeat.py", "robot_live_heartbeat")
            self.heartbeat = heartbeat.Heartbeat(port=heartbeat_port)
        except Exception:
            self.sock.close()
            raise
        self.last_heartbeat = time.monotonic()
        self.last_frame = self.packets = 0
        self.sender = self.area = None
        self.callback = self.tick

    def start_viewport(self):
        for window in bpy.context.window_manager.windows:
            area = next((area for area in window.screen.areas if area.type == "VIEW_3D"), None)
            if area is None:
                continue
            window.scene = self.scene
            space = area.spaces.active
            space.show_region_toolbar = False
            space.show_region_ui = False
            space.overlay.show_overlays = False
            space.region_3d.view_perspective = "CAMERA"
            space.region_3d.view_camera_zoom = -9
            space.use_local_camera = False
            space.shading.type = "RENDERED"
            self.area = area
            return True
        return False

    def start_syphon(self):
        usersite = site.getusersitepackages()
        if usersite not in sys.path:
            sys.path.append(usersite)
        publisher = load_module(ROOT / "blender" / "scenes" / "syphon_out.py", "robot_syphon_out")
        publisher.SERVER, publisher.SIZE, publisher.REGISTRY_KEY = self.server, self.size, SYPHON_KEY
        scene, draw = self.scene, publisher.Sender.draw

        def draw_robot(sender):
            if bpy.context.scene == scene:
                draw(sender)

        publisher.Sender.draw = draw_robot
        self.sender = publisher.start()

    def read_controls(self, now):
        for _ in range(128):
            try:
                data = self.sock.recv(8192)
            except BlockingIOError:
                break
            try:
                packets = self.parse_packet(data)
            except (ValueError, struct.error, RecursionError):
                continue
            for address, _, args in packets:
                if args and self.world.control(address, args[0], now):
                    self.packets += 1

    def tick(self):
        if bpy.app.driver_namespace.get(RUNTIME_KEY) is not self:
            return None
        if self.sender is None:
            if not self.start_viewport():
                return 0.25
            try:
                self.start_syphon()
            except Exception:
                self.close()
                raise
        now = time.monotonic()
        self.read_controls(now)
        self.world.animate(now)
        self.area.tag_redraw()
        if now - self.last_heartbeat >= HEARTBEAT_INTERVAL and self.sender.frames > self.last_frame:
            self.heartbeat.beat()
            if self.last_frame == 0:
                print(f"Robot Live World: publishing frames from {self.scene.camera.name}", flush=True)
            self.last_frame = self.sender.frames
            self.last_heartbeat = now
        return TICK

    def close(self):
        self.sock.close()
        self.heartbeat.close()
        if self.sender is not None:
            if bpy.app.driver_namespace.get(SYPHON_KEY) is self.sender:
                del bpy.app.driver_namespace[SYPHON_KEY]
            self.sender.close()
            self.sender = None


def attach(angle="front", port=PORT, server=SERVER, size=SIZE, heartbeat_port=9202, *, look=LOOKS[0]):
    """Switch the current Blender window to the Robot Live World and start its runtime."""
    if bpy.app.background:
        raise RuntimeError("Robot Live World needs a Blender window")
    storage = bpy.app.driver_namespace
    previous = storage.pop(RUNTIME_KEY, None)
    if previous is not None:
        previous.close()
        if bpy.app.timers.is_registered(previous.callback):
            bpy.app.timers.unregister(previous.callback)
    if WORLD_KEY not in storage or storage[WORLD_KEY].scene["robot_look"] != look:
        storage[WORLD_KEY] = build_world(look=look)
    runtime = LiveWorld(storage[WORLD_KEY], angle, port, server, size, heartbeat_port)
    storage[RUNTIME_KEY] = runtime
    bpy.app.timers.register(runtime.callback)
    return runtime


def check_world(look):
    world = build_world(look=look)
    for index, camera in enumerate(world.cameras):
        world.tick({"vj_angle": index}, now=world.started)
        if world.scene.camera != camera:
            raise RuntimeError(f"could not select the {ANGLES[index]} Angle")
    world.tick({"vj_beat": 0}, now=world.started + 1)
    calm = world.amber.default_value
    world.tick({"vj_beat": 1}, now=world.started + 1 + TICK)
    if not calm < world.amber.default_value < calm + 0.01:
        raise RuntimeError("foundry lights did not respond smoothly to the beat")
    if world.sparks is not None:
        clip, (angle, _, hits) = next((i, data) for i, data in enumerate(world.sparks.clips) if data[2])
        sample = {"vj_angle": ANGLES.index(angle), "vj_clip": clip, "vj_clip_frame": hits[0][0]}
        world.tick(sample, now=world.started + 2)
        world.tick(sample, now=world.started + 2.12)
        if not all(streak.scale.x > 0 for streak in world.sparks.streaks):
            raise RuntimeError("Clip Data Hit did not reach the streaks")
        world.tick(sample, now=world.started + 2.4)
        if any(streak.scale.x != 0 for streak in world.sparks.streaks):
            raise RuntimeError("Clip Data Hit streaks did not expire")
    print(f"Robot Live World check ({look}): {len(world.scene.objects)} objects, {len(world.cameras)} Shot Cameras")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--angle", choices=ANGLES, default=ANGLES[0])
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--server", default=SERVER)
    parser.add_argument("--size", nargs=2, type=int, metavar=("WIDTH", "HEIGHT"), default=SIZE)
    parser.add_argument("--look", choices=LOOKS, default=LOOKS[0])
    parser.add_argument("--heartbeat-port", type=int, default=9202)
    parser.add_argument("--check", action="store_true", help="build geometry and Camera Tracks without a window or ports")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if min(args.size) <= 0:
        parser.error("--size needs a positive width and height")
    if args.check:
        check_world(args.look)
    else:
        attach(angle=args.angle, port=args.port, server=args.server, size=tuple(args.size), heartbeat_port=args.heartbeat_port, look=args.look)


if __name__ == "__main__":
    main()
