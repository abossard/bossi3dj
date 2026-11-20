"""Run both rehearsal Worlds in one Blender window and publish the active World via Syphon.

Load synthwave_planet.blend with autoexec, then pass --python tools/live_blender_show.py.
The dashboard selects the World on UDP 9203. The existing Blender bridge retains UDP 9201.
"""

import argparse
import functools
import importlib.util
from pathlib import Path
import socket
import struct
import sys
import time

import bpy


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'osc'))
from contract import by_address, scene_value
from lab import encode_message, parse_packet
from show_protocol import CUES, MAGIC_PORT, PLANET_CUES, SCENES, SELECTION


HOST = '127.0.0.1'
SWITCH_PORT = 9203
SIZE = (480, 270)
ROBOT_CINEMA_SIZE = (960, 540)
WORLD_READY = '/show/world_ready'
LIVE_LAYER = '/vj/live_layer'
PLANET_MODULES = {'synthwave_runtime', 'planet_runtime', 'flight_rt'}
CONTRACT = by_address()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def guard_planet_handlers(planet):
    def local_to_planet(handler):
        @functools.wraps(handler)
        def guard(scene, *args):
            if scene == planet:
                return handler(scene, *args)
        return guard

    reset = None
    for handlers in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.depsgraph_update_pre):
        for index, handler in enumerate(handlers[:]):
            module = getattr(handler, '__module__', '')
            if module not in PLANET_MODULES:
                continue
            if module == 'flight_rt' and handler.__name__ == 'frame':
                handler.__globals__['en'].BEAT_TILT = 0.0
                reset = handler.__globals__['quiesce']
            if module == 'synthwave_runtime':
                settings = handler.__globals__
                settings['SHOCK_IDLE_EVERY'] = float('inf')
                settings['IDLE_DEPTH'] = 0.0
                settings['_state']['meteor_wait'] = float('inf')
            handlers[index] = local_to_planet(handler)
    if reset is None:
        raise RuntimeError('The Planet Path Camera did not start')
    return reset


def publisher(scene, name, key, size=SIZE):
    module = load_module(ROOT / 'blender/scenes/syphon_out.py', f'show_publisher_{name}')
    module.SERVER, module.SIZE, module.REGISTRY_KEY = name, size, key

    class SceneSender(module.Sender):
        def draw(self):
            if bpy.context.scene == scene:
                super().draw()

    namespace = bpy.app.driver_namespace
    old = namespace.get(key)
    if old is not None:
        old.close()
    sender = SceneSender()
    namespace[key] = sender
    return sender


def viewport(window, scene, planet, cinema=False):
    window.scene = scene
    # Supersample the Planet viewport before its 480x270 Syphon crop to reduce thin-edge shimmer.
    scene.render.preview_pixel_size = '2' if planet or cinema else '4'
    scene.render.fps = 30
    scene.render.fps_base = 1
    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            view = area.spaces.active
            view.use_local_camera = False
            view.overlay.show_overlays = False
            view.show_gizmo = False
            view.shading.type = 'RENDERED'
            view.shading.use_compositor = 'ALWAYS' if planet else 'DISABLED'
            view.region_3d.view_perspective = 'CAMERA'
            area.tag_redraw()


class Show:
    def __init__(self, window, planet, robot, reset_planet, cinema=False):
        self.window = window
        self.scenes = {1: planet, 2: robot.scene}
        self.robot = robot
        self.reset_planet = reset_planet
        self.cinema = cinema
        self.senders = {1: publisher(planet, 'CAM_OUT', 'syphon_out'),
                        2: publisher(robot.scene, 'ROBOT_LIVE', 'robot_syphon_out',
                                     ROBOT_CINEMA_SIZE if cinema else SIZE)}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((HOST, SWITCH_PORT))
        self.socket.setblocking(False)
        self.world = 1
        self.phase = 0
        self.last_frames = -1
        self.last_draw = 0.0
        self.last_message = 0.0
        self.ready_after = 0.0
        self.heartbeat = 0
        viewport(self.window, planet, True)
        self.apply_planet('arrive')

    def apply_planet(self, phase):
        scene = self.scenes[1]
        for address, wire in PLANET_CUES[phase].items():
            value = scene_value(CONTRACT[address], 'blender', wire)
            if value is not None:
                scene[address[1:].replace('/', '_')] = value
        self.reset_planet()
        scene.frame_set(scene.frame_current)

    def notify(self, address, value):
        self.socket.sendto(encode_message(address, [value]), (HOST, MAGIC_PORT))

    def select(self, selection):
        phase, world = divmod(selection, len(SCENES))
        if not 0 <= phase < len(CUES) or world == 0:
            return
        if world == self.world and phase == self.phase:
            return
        self.phase = phase
        self.notify(WORLD_READY, 0)
        if world == 2:
            self.robot.scene['vj_angle'] = 2 if list(CUES)[phase] == 'peak' else 0
            self.robot.tick()
        if world != self.world:
            viewport(self.window, self.scenes[world], world == 1, self.cinema)
            self.world = world
        if world == 1:
            self.apply_planet('release' if list(CUES)[phase] == 'release' else 'arrive')
        self.last_frames = self.senders[world].frames
        self.last_draw = 0.0
        self.ready_after = time.monotonic() + 0.35

    def read_selection(self):
        latest = None
        for _ in range(32):
            try:
                packet = self.socket.recv(4096)
            except BlockingIOError:
                break
            try:
                for address, _, values, _ in parse_packet(packet):
                    if address == SELECTION and values and type(values[0]) is int:
                        latest = values[0]
            except (ValueError, struct.error, RecursionError):
                continue
        if latest is not None:
            self.select(latest)

    def tick(self):
        self.read_selection()
        if self.world == 2:
            self.robot.tick()
        for area in self.window.screen.areas:
            if area.type == 'VIEW_3D':
                view = area.spaces.active
                if view.region_3d.view_perspective != 'CAMERA':
                    view.region_3d.view_perspective = 'CAMERA'
                    area.tag_redraw()
                elif self.world == 2:
                    area.tag_redraw()

        now = time.monotonic()
        frames = self.senders[self.world].frames
        if frames != self.last_frames:
            self.last_frames, self.last_draw = frames, now
        if now - self.last_message >= 0.25:
            ready = self.world if now >= self.ready_after and now - self.last_draw <= 1 else 0
            self.notify(WORLD_READY, ready)
            if ready == 2:
                self.heartbeat ^= 1
                self.notify(LIVE_LAYER, self.heartbeat)
            self.last_message = now
        return 1 / 30


def start(cinema=False):
    namespace = bpy.app.driver_namespace
    window = bpy.context.window or next(iter(bpy.context.window_manager.windows), None)
    if window is None or 'syphon_out' not in namespace or 'vj_osc_bridge' not in namespace:
        return 0.2
    planet = window.scene
    reset_planet = guard_planet_handlers(planet)
    module = load_module(ROOT / 'robot/live/live_world.py', 'rehearsal_robot_world')
    scene = bpy.data.scenes.new('Robot Live World')
    robot = module.build_world(scene, look='chrome-foundry') if cinema else module.build_world(scene)
    show = Show(window, planet, robot, reset_planet, cinema)
    namespace['vj_live_show'] = show
    bpy.app.timers.register(show.tick)
    print(f'live_blender_show: two Worlds, selection on udp {SWITCH_PORT}', flush=True)
    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--robot-cinema', action='store_true', help='use the 960×540 Chrome Foundry Robot output')
    options = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    bpy.app.timers.register(functools.partial(start, options.robot_cinema), first_interval=0.8)
