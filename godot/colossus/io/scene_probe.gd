class_name SceneProbe
## What the scene is doing, as numbers, read from the nodes that act on the values.
## The state page shows it and the self-check judges by it. Node access only, no logic.


static func read(m: ColossusMain) -> Dictionary:
	var env := m.world.environment
	return {
		"sun_energy": m.world.sun.light_energy,
		"fog_density": env.volumetric_fog_density,
		"fog_height": env.fog_height,
		"haze_density": env.fog_density,
		"exposure": env.tonemap_exposure,
		"weight": m.colossus.weight,
		"shot": int(m.director.shot),
		"pinned": m.director.pinned(),
		"phase": int(m.arc.phase),
		"shake_roll": absf(m.colossus.roll),
		"shaking": m.colossus.is_shaking(),
		"on_colossus": m.wanderer.on_colossus(),
		"beats": m.vj.beats,
		"shocks": m.vj.shocks,
	}
