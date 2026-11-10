class_name InputActions
## Keyboard actions for Takeover and performer triggers (see docs/SPEC.md).

const KEYS := {
	"move_forward": KEY_W,
	"move_back": KEY_S,
	"move_left": KEY_A,
	"move_right": KEY_D,
	"run": KEY_SHIFT,
	"grab": KEY_SPACE,
	"next_phase": KEY_N,
	"reset": KEY_R,
	"shake": KEY_Q,
	"next_colossus": KEY_C,
	"shot_1": KEY_1,
	"shot_2": KEY_2,
	"shot_3": KEY_3,
	"shot_4": KEY_4,
	"shot_5": KEY_5,
	"debug": KEY_F1,
}


static func install() -> void:
	for action: String in KEYS:
		if InputMap.has_action(action):
			continue
		InputMap.add_action(action)
		var ev := InputEventKey.new()
		ev.physical_keycode = KEYS[action]
		InputMap.action_add_event(action, ev)
