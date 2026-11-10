extends SceneTree
## The scene headless on the test ports, for tools/godot_page_test.py to talk to over HTTP.
## Godot --headless --path godot/colossus --script res://tests/serve.gd -- <seconds to run>

const TEST_OSC_PORT := 19202
const TEST_PAGE_PORT := 19211


func _initialize() -> void:
	Engine.time_scale = 4.0
	var main: ColossusMain = load("res://main.tscn").instantiate()
	main.osc_port = TEST_OSC_PORT
	main.page_port = TEST_PAGE_PORT
	main.syphon_enabled = false
	root.add_child(main)
	var args := OS.get_cmdline_user_args()
	var seconds := float(args[0]) if not args.is_empty() else 60.0
	print("serve: control page on http://127.0.0.1:%d for %.0f s" % [TEST_PAGE_PORT, seconds])
	create_timer(seconds, true, false, true).timeout.connect(quit)
