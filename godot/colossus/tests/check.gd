extends SceneTree
## The scene's feature self-check, headless: one row per control, a JSON file, exit 1 on any
## verdict but "effect". Same implementation as the page's "Check all" (io/feature_check.gd).
## Godot --headless --path godot/colossus --script res://tests/check.gd -- <out.json> [id,id,...]

## Never the show's ports: a test must not steal or feed the live scene.
const TEST_OSC_PORT := 19202
const TEST_PAGE_PORT := 19211
const DEFAULT_OUT := "/tmp/colossus-feature-check.json"


func _initialize() -> void:
	_run()


func _run() -> void:
	Engine.time_scale = 4.0
	var main: ColossusMain = load("res://main.tscn").instantiate()
	main.osc_port = TEST_OSC_PORT
	main.page_port = TEST_PAGE_PORT
	main.syphon_enabled = false
	root.add_child(main)
	await process_frame
	await create_timer(0.5).timeout
	var started := Time.get_ticks_msec()
	var check := FeatureCheck.new(main)
	var args := OS.get_cmdline_user_args()
	var out := args[0] if not args.is_empty() else DEFAULT_OUT
	var ids: Array = Array(args[1].split(",")) if args.size() > 1 else []
	var rows := await check.run(ids)
	print("%-16s %-10s %-14s %s" % ["control", "verdict", "address", "what (observed, expected)"])
	for r: Dictionary in rows:
		print(
			(
				"%-16s %-10s %-14s %s (%s, %s)"
				% [
					r["id"],
					r["verdict"],
					r["address"],
					r["detail"],
					JSON.stringify(r["observed"]),
					JSON.stringify(r["expected"]),
				]
			)
		)
	var summary := ControlServer.summary(rows)
	var wall := Time.get_ticks_msec() - started
	var doc := {"summary": summary, "wall_ms": wall, "rows": rows}
	var f := FileAccess.open(out, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(doc, "  "))
	print("check: %s in %d ms, rows in %s" % [JSON.stringify(summary), wall, out])
	quit(
		(
			0
			if (
				rows.size() == FeatureCheck.TABLE.size()
				and summary[FeatureCheck.EFFECT] == rows.size()
			)
			else 1
		)
	)
