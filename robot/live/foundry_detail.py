"""Optional Chrome Foundry lighting and localized sparks for the Robot Live World."""

import json
import math

import bpy
from mathutils import Vector


SPARK_COUNT = 8
SPARK_LIFE = 0.32


def lamp(collection, name, where, target, power, color, size):
    data = bpy.data.lights.new(name, "AREA")
    data.shape, data.size, data.energy, data.color = "DISK", size, power, color
    data.use_shadow = False
    light = bpy.data.objects.new(name, data)
    collection.objects.link(light)
    light.location = where
    light.rotation_euler = (Vector(target) - light.location).to_track_quat("-Z", "Y").to_euler()


def build(scene, floor, package, boxes, material):
    """Layer warm furnace light and cool separation into the existing Arclink arena."""
    collection = bpy.data.collections.new("Chrome Foundry")
    scene.collection.children.link(collection)
    floor.node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value = 0.38
    lamp(collection, "Sodium overhead", (2, -3, 7), (0, -1, 0), 780, (1, 0.72, 0.46), 5)
    lamp(collection, "Cool edge light", (-7, 2, 4.5), (-1, 0, 1.5), 480, (0.38, 0.68, 1), 4)
    lamp(collection, "Far furnace light", (-10, 7, 6), (-13, 3, 3), 620, (1, 0.59, 0.31), 6)
    channel, _ = material("Furnace channel", (1, 0.17, 0.028), 0.70)
    border, _ = material("Furnace metal", (0.045, 0.038, 0.035), 0.27)
    boxes(collection, "Furnace channel surround", border,
          [(-6.1, -0.5, 0.040, 0.5, 9, 0.08, 0), (1.1, 5.0, 0.040, 9, 0.5, 0.08, 0)])
    boxes(collection, "Furnace channels", channel,
          [(-6.1, -0.5, 0.09, 0.18, 8.6, 0.02, 0), (1.1, 5.0, 0.09, 8.6, 0.18, 0.02, 0)])
    spark_material, glow = material("Hit sparks", (1, 0.33, 0.055), 0.1)
    return HitSparks(scene, collection, package, spark_material, glow)


def read_hits(package):
    manifest = json.loads((package / "manifest.json").read_text())
    clips = []
    for clip in manifest["clips"]:
        data = json.loads((package / clip["clip_data"]).read_text())
        hits = []
        for hit in data.get("hits", []):
            u, v, depth = hit["point"]
            if 0 <= u <= 1 and 0 <= v <= 1 and depth > 0:
                hits.append((hit["f"], (u, v, depth), min(1, max(0, hit["strength"]))))
        clips.append((clip["angle"], clip["frames"], hits))
    return clips


def camera_point(scene, camera, point):
    """Invert the perspective projection used to export v1 Clip Data."""
    u, v, depth = point
    frame = camera.data.view_frame(scene=scene)
    left = min(c.x / -c.z for c in frame)
    right = max(c.x / -c.z for c in frame)
    bottom = min(c.y / -c.z for c in frame)
    top = max(c.y / -c.z for c in frame)
    ray = Vector((left + (right - left) * u, top - (top - bottom) * v, -1))
    return camera.location + camera.rotation_quaternion @ (ray * depth)


class HitSparks:
    def __init__(self, scene, collection, package, material, glow):
        self.scene, self.glow = scene, glow
        self.clips = read_hits(package)
        self.clip = self.frame = self.previous_frame = None
        self.wait_frame = None
        self.burst = None
        shape = bpy.data.meshes.new("Hit spark streak")
        shape.from_pydata([(-1, 0, 0), (0, 0.5, 0), (0, 0, 0.5), (0.24, 0, 0), (0, -0.5, 0), (0, 0, -0.5)], [],
                          [(0, 1, 2), (0, 2, 4), (0, 4, 5), (0, 5, 1), (3, 2, 1), (3, 4, 2), (3, 5, 4), (3, 1, 5)])
        shape.materials.append(material)
        self.streaks = []
        for i in range(SPARK_COUNT):
            streak = bpy.data.objects.new(f"Hit spark {i + 1}", shape)
            streak.rotation_mode = "QUATERNION"
            streak.scale = (0, 0, 0)
            collection.objects.link(streak)
            self.streaks.append(streak)

    def select_clip(self, clip):
        if clip != self.clip:
            self.wait_frame = self.frame
            self.clip, self.previous_frame = clip, None
            self.clear()

    def select_frame(self, frame):
        self.frame = frame

    def clear(self):
        if self.burst is not None:
            for streak in self.streaks:
                streak.scale = (0, 0, 0)
            self.burst = None

    def begin(self, point, strength, camera, now):
        origin = camera_point(self.scene, camera, point)
        rotation = camera.rotation_quaternion
        velocities = []
        for i in range(SPARK_COUNT):
            angle = i * math.tau / SPARK_COUNT + 0.32
            direction = Vector((math.cos(angle), math.sin(angle) + 0.25, 0.07 * (i % 3 - 1))).normalized()
            velocities.append((rotation @ direction) * (1.5 + 0.36 * (i % 4)))
        self.burst = now, origin, strength, velocities

    def tick(self, angle, camera, now):
        if self.clip is not None and self.frame is not None and self.clip < len(self.clips):
            clip_angle, frames, hits = self.clips[self.clip]
            frame, previous = self.frame, self.previous_frame
            if clip_angle != angle:
                self.clear()
            elif frame != self.wait_frame and 0 <= frame < frames:
                self.wait_frame = None
                if previous is None or (frame <= 1 and previous >= frames - 5):
                    previous = frame - 1
                if frame > previous:
                    self.previous_frame = frame
                    for hit_frame, point, strength in hits:
                        if max(previous, frame - 4) < hit_frame <= frame:
                            self.begin(point, strength, camera, now)
        if self.burst is None:
            return
        started, origin, strength, velocities = self.burst
        age = (now - started) / SPARK_LIFE
        if age >= 1:
            self.clear()
            return
        envelope = math.sin(math.pi * age) ** 0.8
        self.glow.default_value = 0.48 + 1.38 * strength * envelope
        for streak, velocity in zip(self.streaks, velocities):
            drift = velocity - Vector((0, 0, 1.5 * age))
            streak.location = origin + drift * (age * SPARK_LIFE)
            streak.rotation_quaternion = drift.to_track_quat("X", "Z")
            streak.scale = (0.23 * envelope, 0.042 * envelope, 0.042 * envelope)
