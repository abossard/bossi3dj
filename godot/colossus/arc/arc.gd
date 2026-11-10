class_name Arc
## Phase transitions of the Arc. Pure: takes a Phase and an event, returns the next Phase.

enum Phase { APPROACH, CLIMB, FALL, RESET }
enum Event { NEXT, RESET_NOW, FALL_SETTLED, FADE_DONE }


static func next(phase: Phase, event: Event) -> Phase:
	if event == Event.RESET_NOW:
		return Phase.RESET
	match phase:
		Phase.APPROACH:
			if event == Event.NEXT:
				return Phase.CLIMB
		Phase.CLIMB:
			if event == Event.NEXT:
				return Phase.FALL
		Phase.FALL:
			if event == Event.FALL_SETTLED:
				return Phase.RESET
		Phase.RESET:
			if event == Event.FADE_DONE:
				return Phase.APPROACH
	return phase


static func name_of(phase: Phase) -> String:
	return Phase.keys()[phase].capitalize()


## The event that moves `current` one step toward `goal`, or -1 to wait or when already there.
## Phases only go forward: back to an earlier one means a Reset, which comes back to Approach.
static func step_toward(current: Phase, goal: Phase) -> int:
	if current == goal or current == Phase.RESET:
		return -1
	if goal == Phase.RESET or goal < current:
		return Event.RESET_NOW
	return Event.NEXT
