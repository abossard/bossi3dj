"""OSC commands for the rehearsal program, separate from the scene's /vj contract."""

MAGIC_PORT = 9202
SELECTION = "/show/selection"
REACTIVITY = "/show/reactivity"
WORLD_READY = "/show/world_ready"
AUDIO_LEVEL = "/show/audio/level"
AUDIO_SUB = "/show/audio/subbass"
ROBOT_FRAMING = "/show/robot/framing"  # zoom, center x, center y (top-left origin)
ROBOT_HIT = "/show/robot/hit"          # x, y (top-left origin), 0..1 strength
ROBOT_RESTART = "/show/robot/restart"  # a new integer token restarts the on-air Robot file
SCENES = ("safe", "planet", "robot")
CUES = {
    "arrive": "planet",
    "build": "robot",
    "peak": "robot",
    "release": "planet",
}
DEFAULT_REACTIVITY = 0.35

_PLANET_STEADY = {
    "/vj/blend": 0.12,
    "/vj/strobe": 0,
    "/vj/hit": 0,
    "/vj/shock": 0,
    "/vj/meteor": 0,
    "/vj/fog_speed": 0,
    "/vj/fog_beat": 0,
    "/vj/star_speed": 0,
    "/vj/flamingos": 0,
}
PLANET_CUES = {
    "arrive": {
        **_PLANET_STEADY,
        "/vj/path": 0,
        "/vj/target": 0,
        "/vj/height": 0.18,
        "/vj/night": 0.42,
        "/vj/cam_speed": 0.045,
    },
    "release": {
        **_PLANET_STEADY,
        "/vj/path": 3,
        "/vj/target": 4,
        "/vj/height": 0.43,
        "/vj/night": 0.62,
        "/vj/cam_speed": 0.025,
    },
}


def selection(cue, scene):
    """Send phase and scene together so an intervening frame cannot mix two commands."""
    return tuple(CUES).index(cue) * len(SCENES) + SCENES.index(scene)
