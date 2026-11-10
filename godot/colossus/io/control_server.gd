class_name ControlServer
extends Node
## The scene's control page: http on 127.0.0.1, the counterpart of Blender's page on 9210.
## It lives beside the output viewport, so nothing of it reaches the Syphon frame. With no client
## connected a frame costs one accept check. Every write goes through VjSignals.apply.
##
##   GET  /                the page
##   GET  /api/state       Phase, shot, fps, every value, OSC and Syphon counters, simulator
##   GET  /api/check       progress and results of the self-check
##   POST /api/set         {"values": {address: v}, "hold": bool}
##   POST /api/fire        {"address": "/vj/shock", "strength": 1.0}
##   POST /api/hold        {"addresses": [..] or omitted for all, "on": bool}
##   POST /api/defaults    every value to its rest value, holds released
##   POST /api/phase       {"phase": "Climb"}
##   POST /api/sim         {"on": bool, "bpm": 124, "shock_every": 8}
##   POST /api/check       {"ids": [..] or omitted for all}

const PORT := 9211
const PAGE := "res://io/control_page.html"
const MAX_REQUEST := 65536
const CLIENT_SECONDS := 5.0

## Set before the node enters the tree. Tests use 19211.
var port := PORT
var main: ColossusMain
var check: FeatureCheck
var sim_on := false
var sim_bpm := 124.0
var sim_shock_every := 8

var _tcp := TCPServer.new()
var _clients: Array[Client] = []
var _sim_time := 0.0


class Client:
	extends RefCounted
	var peer: StreamPeerTCP
	var buf := PackedByteArray()
	var age := 0.0

	func _init(p: StreamPeerTCP) -> void:
		peer = p


func _ready() -> void:
	var err := _tcp.listen(port, "127.0.0.1")
	if err != OK:
		push_warning("ControlServer: cannot listen on tcp %d (%s)" % [port, error_string(err)])


func start_sim(bpm: float, shock_every: int) -> void:
	sim_bpm = clampf(bpm, 40.0, 240.0)
	sim_shock_every = maxi(shock_every, 0)
	if not sim_on:
		_sim_time = 0.0
	sim_on = true


func stop_sim() -> void:
	sim_on = false


func _process(delta: float) -> void:
	if sim_on:
		_step_sim(delta)
	if _tcp.is_connection_available():
		_clients.append(Client.new(_tcp.take_connection()))
	var i := _clients.size() - 1
	while i >= 0:
		if _serve(_clients[i], delta):
			_clients.remove_at(i)
		i -= 1


func _step_sim(delta: float) -> void:
	_sim_time += delta
	var vj := main.vj
	var src := VjSignals.SOURCE_SIM
	vj.apply("/vj/beat", BeatSim.beat(_sim_time, sim_bpm), src)
	vj.apply("/vj/bass", BeatSim.bass(_sim_time, sim_bpm), src)
	vj.apply("/vj/level", BeatSim.level(_sim_time, sim_bpm), src)
	vj.apply("/vj/shock", BeatSim.shock(_sim_time, sim_bpm, sim_shock_every), src)


## Read what has arrived and answer a complete request. True when the client is done.
func _serve(c: Client, delta: float) -> bool:
	c.peer.poll()
	c.age += delta
	if c.peer.get_status() != StreamPeerTCP.STATUS_CONNECTED or c.age > CLIENT_SECONDS:
		return true
	var n := c.peer.get_available_bytes()
	if n > 0:
		var got := c.peer.get_data(n)
		if got[0] == OK:
			c.buf.append_array(got[1])
	var request := HttpLite.parse(c.buf)
	if request.is_empty():
		if c.buf.size() <= MAX_REQUEST:
			return false
		c.peer.put_data(HttpLite.json(413, {"error": "request too large"}))
	else:
		c.peer.put_data(_route(request))
	c.peer.disconnect_from_host()
	return true


func _route(req: Dictionary) -> PackedByteArray:
	var host: String = req["headers"].get("host", "")
	if not (host.begins_with("127.0.0.1") or host.begins_with("localhost")):
		return HttpLite.json(403, {"error": "local requests only"})
	var answer := HttpLite.json(404, {"error": "not found"})
	if req["method"] == "GET":
		answer = _answer_get(req["path"])
	elif req["method"] == "POST":
		answer = _post_json(req)
	return answer


func _answer_get(path: String) -> PackedByteArray:
	var answer := HttpLite.json(404, {"error": "not found"})
	match path:
		"/", "/index.html":
			answer = _page()
		"/api/state":
			answer = HttpLite.json(200, state())
		"/api/check":
			answer = HttpLite.json(200, check_state())
	return answer


func _post_json(req: Dictionary) -> PackedByteArray:
	# A browser page of another origin cannot send this type without a preflight we never answer.
	if not str(req["headers"].get("content-type", "")).begins_with("application/json"):
		return HttpLite.json(415, {"error": "send application/json"})
	var body: Variant = JSON.parse_string(req["body"] if req["body"] != "" else "{}")
	if not body is Dictionary:
		return HttpLite.json(400, {"error": "body is not a JSON object"})
	return _post(req["path"], body)


func _page() -> PackedByteArray:
	var f := FileAccess.open(PAGE, FileAccess.READ)
	if f == null:
		return HttpLite.json(404, {"error": "page missing"})
	return HttpLite.response(200, "text/html; charset=utf-8", f.get_buffer(f.get_length()))


func _post(path: String, body: Dictionary) -> PackedByteArray:
	var vj := main.vj
	match path:
		"/api/set":
			var values: Dictionary = body.get("values", {})
			var hold: bool = body.get("hold", false)
			for a: String in values:
				if not VjMap.known(a) or not (values[a] is float or values[a] is int):
					return HttpLite.json(400, {"error": "bad address or value: %s" % a})
			for a: String in values:
				vj.apply(a, float(values[a]), VjSignals.SOURCE_PAGE)
				vj.set_hold(a, hold)
		"/api/fire":
			var a: String = body.get("address", "")
			if VjMap.known(a) and VjMap.ROWS[a]["kind"] == VjMap.Kind.TRIGGER:
				vj.fire(a, float(body.get("strength", 1.0)))
			else:
				return HttpLite.json(400, {"error": "not a trigger: %s" % a})
		"/api/hold":
			var on: bool = body.get("on", false)
			var addresses: Array = body.get("addresses", VjMap.addresses())
			for a: String in addresses:
				vj.set_hold(a, on)
		"/api/defaults":
			vj.reset_defaults()
		"/api/phase":
			var name := str(body.get("phase", "")).to_upper()
			if not Arc.Phase.has(name):
				return HttpLite.json(400, {"error": "phase is Approach, Climb, Fall or Reset"})
			main.arc.go_to(Arc.Phase[name])
		"/api/sim":
			if body.get("on", false):
				start_sim(float(body.get("bpm", sim_bpm)), int(body.get("shock_every", 8)))
			else:
				stop_sim()
		"/api/check":
			if check != null and check.running:
				return HttpLite.json(409, {"error": "a check is running"})
			check = FeatureCheck.new(main)
			check.run(body.get("ids", []))
		_:
			return HttpLite.json(404, {"error": "not found"})
	return HttpLite.json(200, {"ok": true})


func check_state() -> Dictionary:
	if check == null:
		return {"running": false, "current": "", "results": [], "summary": {}}
	return {
		"running": check.running,
		"current": check.current,
		"results": check.results,
		"summary": summary(check.results),
	}


static func summary(rows: Array) -> Dictionary:
	return {
		FeatureCheck.EFFECT: FeatureCheck.count_of(rows, FeatureCheck.EFFECT),
		FeatureCheck.NO_EFFECT: FeatureCheck.count_of(rows, FeatureCheck.NO_EFFECT),
		FeatureCheck.ERROR: FeatureCheck.count_of(rows, FeatureCheck.ERROR),
	}


func state() -> Dictionary:
	var vj := main.vj
	var values := {}
	var controls: Array = []
	for a: String in VjMap.addresses():
		values[a] = vj.describe(a)
		var row: Dictionary = VjMap.ROWS[a]
		(
			controls
			. append(
				{
					"address": a,
					"kind": row["kind"],
					"lo": row["lo"],
					"hi": row["hi"],
					"rest": row["rest"],
					"drives": row["drives"],
				}
			)
		)
	var probe := SceneProbe.read(main)
	var syphon := {
		"server": main.syphon_server,
		"active": main.syphon != null,
		"frames": Engine.get_frames_drawn() - main.syphon_since_frame if main.syphon else 0,
	}
	return {
		"scene": "colossus",
		"phase": Arc.name_of(main.arc.phase),
		"shot": probe["shot"],
		"pinned": probe["pinned"],
		"colossus": main.colossus.name,
		"wanderer_on_colossus": probe["on_colossus"],
		"fps": Engine.get_frames_per_second(),
		"frame_ms": snappedf(Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, 0.01),
		"display": DisplayServer.get_name(),
		"controls": controls,
		"values": values,
		"probe": probe,
		"osc":
		{
			"port": vj.port,
			"packets": vj.packets,
			"messages": vj.messages,
			"applied": vj.applied,
			"dropped": vj.dropped,
			"ignored": vj.ignored,
			"live": vj.fresh(),
			"holds": vj.held_addresses(),
		},
		"syphon": syphon,
		"sim": {"on": sim_on, "bpm": sim_bpm, "shock_every": sim_shock_every},
		"check": check_state(),
	}
