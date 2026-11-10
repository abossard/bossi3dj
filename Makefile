BLENDER ?= /Applications/Blender.app/Contents/MacOS/Blender
GODOT   ?= /Applications/Godot_mono.app/Contents/MacOS/Godot
COLOSSUS = godot/colossus
SCENES   = blender/scenes
SCENE   ?= planet
BLEND_planet = $(SCENES)/synthwave_planet.blend
BLEND_island = $(SCENES)/synthwave_pyramids.blend

.PHONY: help status lab test magic-test osc-test blender-test osc-sync osc-sweep godot-test godot-smoke godot-check godot-page-test godot-capture godot-import godot-lint \
        godot-open godot-kill blender-open blender-kill blender-check blender-rebuild blender-paths magic-build venv verify

# Blender and Godot share one GPU: a live window of one refuses to start while the other runs.
BLENDER_RUNS   = pgrep -f "Blender.app/Contents/MacOS/Blender" >/dev/null
GODOT_GUI_RUNS = pgrep -lf "Godot_mono.app/Contents/MacOS/Godot" | grep -v -e "--headless" >/dev/null

help:
	@echo "bossi3dj: Magic -> OSC -> Blender scene + Godot scene -> Syphon -> Magic"
	@echo ""
	@echo "  status            what runs now: Blender, bridge, Syphon, Godot, Magic, relay, lock, load"
	@echo "  lab               OSC relay and debug page: Magic udp 9200 -> Blender 9201 + Godot 9202, http 8765"
	@echo "  test              magic-test + osc-test + blender-test + godot-test + godot-check (no GUI, no GPU)"
	@echo "  magic-test        Magic project tooling and generator unit tests"
	@echo "  osc-test          contract table, CONTROLS.md and sweep tests"
	@echo "  blender-test      the bridge's wire-to-scene scaling, without Blender"
	@echo "  magic-build       regenerate magic/projects/*.magic from the generators (synthwave_pyramids for Blender, show for both scenes)"
	@echo "  osc-sync          rewrite the CONTROLS.md table and the bridge's SCALES block from osc/contract.json"
	@echo "  osc-sweep         walk every /vj/* address through min, default, max (ARGS=\"--target godot --seconds 2\", ARGS=--dry-run)"
	@echo "  godot-test        Colossus logic tests, headless"
	@echo "  godot-smoke       one full Colossus Arc, headless, own OSC port and Syphon name"
	@echo "  godot-check       feature self-check headless on page port 19211: one row per control, JSON to CHECK_OUT (default /tmp/colossus-feature-check.json)"
	@echo "  godot-page-test   headless scene on 19211, then HTTP requests against its control page and its Check all"
	@echo "  godot-open        run the Colossus Scene in a window: OSC 9202, Syphon COLOSSUS_OUT (refuses while Blender runs)"
	@echo "  godot-kill        end every Godot window (headless runs are left alone)"
	@echo "  godot-capture     render one frame per Phase on Metal into OUT=<dir> (opens a window, refuses while Blender runs)"
	@echo "  godot-import      re-import the Godot project after adding assets or addons"
	@echo "  godot-lint        gdlint + gdformat --check on the project's own scripts"
	@echo "  blender-open      open SCENE=planet|island in the GUI with scripts allowed (refuses a second Blender or a Godot window)"
	@echo "  blender-kill      end the running Blender (unsaved state is lost)"
	@echo "  blender-check     feature check of the running scene: one row per control, contract cross-check, JSON in blender/review/out (ARGS=--only vj_fog)"
	@echo "  blender-rebuild   headless: rebuild synthwave_planet.blend from the island scene (no Blender may run)"
	@echo "  blender-paths     list the external files each .blend points at"
	@echo "  venv              .venv with numpy and Pillow for the verify scripts"
	@echo "  verify            pure-model checks of the star system and the Flight camera (needs venv)"

status:
	@python3 tools/vj_status.py

lab:
	@python3 osc/lab.py

test: magic-test osc-test blender-test godot-test godot-check

magic-test:
	python3 -m unittest discover magic/tests

osc-test:
	python3 -m unittest discover osc/tests

blender-test:
	python3 -m unittest discover blender/tests

osc-sync:
	python3 osc/contract.py sync

osc-sweep:
	python3 osc/sweep.py $(ARGS)

magic-build:
	python3 magic/synthwave_magic.py
	python3 magic/show_magic.py
	python3 magic/edm_analysis_magic.py

godot-test:
	$(GODOT) --headless --path $(COLOSSUS) --script res://tests/run_tests.gd

godot-smoke:
	$(GODOT) --headless --path $(COLOSSUS) --script res://tests/smoke.gd

CHECK_OUT ?= /tmp/colossus-feature-check.json
godot-check:
	$(GODOT) --headless --path $(COLOSSUS) --script res://tests/check.gd -- $(CHECK_OUT)

godot-page-test:
	python3 tools/godot_page_test.py

OUT ?= /tmp/colossus-capture
godot-capture:
	@if $(BLENDER_RUNS); then echo "Blender runs and shares the GPU: make blender-kill first (make status)"; exit 1; fi
	$(GODOT) --path $(COLOSSUS) --script res://tests/capture.gd -- $(OUT)

godot-open:
	@if $(BLENDER_RUNS); then echo "Blender runs and shares the GPU: make blender-kill first (make status)"; exit 1; fi
	@if $(GODOT_GUI_RUNS); then echo "a Godot window is already running (make status)"; exit 1; fi
	$(GODOT) --path $(COLOSSUS) &

godot-kill:
	-pgrep -lf "Godot_mono.app/Contents/MacOS/Godot" | grep -v -e "--headless" | cut -d" " -f1 | xargs kill

godot-import:
	$(GODOT) --headless --path $(COLOSSUS) --import
	@git status --short $(COLOSSUS)/project.godot

godot-lint:
	cd $(COLOSSUS) && find . -name '*.gd' -not -path './addons/*' -print0 | xargs -0 gdlint
	cd $(COLOSSUS) && find . -name '*.gd' -not -path './addons/*' -print0 | xargs -0 gdformat --check

blender-open:
	@if $(BLENDER_RUNS); then echo "a Blender is already running (make status)"; exit 1; fi
	@if $(GODOT_GUI_RUNS); then echo "a Godot window runs and shares the GPU: make godot-kill first (make status)"; exit 1; fi
	open -a /Applications/Blender.app --args --enable-autoexec "$(CURDIR)/$(BLEND_$(SCENE))"

blender-check:
	python3 blender/review/feature_check.py $(ARGS)

blender-kill:
	-pkill -f "Blender.app/Contents/MacOS/Blender"
	@python3 tools/blender_lock.py release --force

blender-rebuild:
	@if pgrep -f "Blender.app/Contents/MacOS/Blender" >/dev/null; then echo "a Blender is running: make blender-kill first"; exit 1; fi
	cd $(SCENES)/planet_proto && $(BLENDER) -b --factory-startup -Y ../synthwave_pyramids.blend --python build_planet.py -- --graft

blender-paths:
	@if pgrep -f "Blender.app/Contents/MacOS/Blender" >/dev/null; then echo "a Blender is running: make blender-kill first"; exit 1; fi
	@for f in $(BLEND_island) $(BLEND_planet); do $(BLENDER) -b --disable-autoexec $$f --python tools/blend_paths.py 2>/dev/null | sed -n 's/^BLEND_PATHS //p'; done

venv:
	uv venv .venv
	uv pip install --python .venv/bin/python numpy pillow

verify:
	.venv/bin/python docs/research/synthwave-star-system/verify_star_system.py
	.venv/bin/python docs/research/synthwave-flight/verify_flight.py
