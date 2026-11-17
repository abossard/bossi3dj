"""The Clip Library (#32): every Move that becomes Clips in the package. Pure, no bpy.

The key-table Moves of moves.py (with their variants) and the Mocap Moves of mocap.py, the latter as moves.Move
entries with `source="mocap"` and no keys (retarget.py bakes them). The hand-keyed jab_cross, jab_jab_hook and
uppercut_combo are gone (the user, 2026-11-17: unusable); the Mocap fight Moves replace them. A Mocap Clip without a
Key Pose (mocap_idle, the first proof) stays out.
"""
import mocap
import moves


def _mocap_move(clip):
    return moves.Move(clip.name, clip.tier, clip.beats, clip.key_in, clip.key_out, (), mocap.hits(clip), clip.idle,
                      (), clip.variant_of, None, None, "mocap")


LIBRARY = dict(moves.MOVES)
LIBRARY.update({c.name: _mocap_move(c) for c in mocap.CLIPS.values() if c.key_in})


def is_mocap(move):
    return move.source == "mocap"


def cut_points(move):
    """Beats whose frame shows the Move's Key Pose: computed from a key table; a Mocap Move only its first beat."""
    return [0] if is_mocap(move) else moves.cut_points(move)
