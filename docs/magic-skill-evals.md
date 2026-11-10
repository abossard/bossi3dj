# magic-projects skill evals

Run 2026-11-04 with the skill-creator flow. Prompts, fixtures and the grader live in `.claude/skills/magic-projects/evals/` (`evals.json`, `files/`, `grade.py`, `trigger_evals.json`); per-run grading, timing and benchmarks are in `evals/results/`. Each run is a fresh subagent (Opus 5.5) in this worktree; "without skill" runs were told not to read `.claude/skills/`. No run touched Magic, OSC or a `.blend` file.

## Results

| Eval | Iteration 1 with / without | Iteration 2 with / without | Tokens it2 with / without | Seconds it2 with / without |
|---|---|---|---|---|
| 1 inspect: what feeds `/vj/shock`, which bands the kick uses | 5/5 / 5/5 | 5/5 / 5/5 | 73.5k / 82.5k | 38 / 87 |
| 2 edit: OSC to 9200, Syphon on and named, Gain 0.7, nothing else | 8/8 / 8/8 | 8/8 / 8/8 | 69.7k / 82.8k | 39 / 89 |
| 3 generate: bass-pulsed square, Hue Global, OSCSender | 11/11 / 11/11 | 11/11 / 11/11 | 78.9k / 92.7k | 53 / 89 |
| 4 diff: what the synthetic build replaces | 5/5 / 4/5 | 5/5 / 5/5 | 74.0k / 98.5k | 67 / 98 |
| 5 plan a live `/vj/beat` check (added in iteration 2) | | 6/6 / 5/6 | 110.9k / 96.1k | 250 / 180 |
| Total | 29/29 / 28/29 | 35/35 / 34/35 | | |

## What the numbers say

- Pass rate barely separates the configurations: the baselines found `magic/magicproj.py` (and, in iteration 2, this report) in the worktree and used them. The skill's measurable gain is cost: on evals 1-4, 46% less time (49 s vs 91 s) and 17% fewer tokens (74k vs 89k) in iteration 2.
- Baseline misses: iteration 1 eval 4 could not name modifier type 6 (Random); iteration 2 eval 5 did not account for OSCSender sending only on change.
- Behaviour the assertions do not score: the iteration-1 eval-3 baseline read the user's unrelated projects (`~/Documents/test.magic`, another repo's `GARAGE.magic`) for param names; the skill runs used `catalog`. Both eval-3 runs in iteration 1 guessed the Polygon scale.
- The eval-5 skill run found a real bug: `listen` unpacked 3 values from `lab.parse_packet`, which returns 4, so it would crash on the first message. Fixed after iteration 2, with a loopback test (`ListenTests`). That run was also the most expensive (111k tokens, 250 s): it dry-ran the retarget and tested its own log analysis.
- Eval 5 baseline built a safe plan of its own (passive `sudo tcpdump` on 9201, no project load). The first version of the grader penalised that; the assertions were rewritten to score outcomes (nothing binds 9201, Magic's project left as it was) instead of the skill's method.

## Iteration 1 → 2 changes

- `format.md`: measured coordinate system (y -1..1, one unit = half the frame height).
- `SKILL.md`: `catalog` covers ISF headers, OSCSender and SyphonClient, so no digging through other projects; check 9200 with `lsof` before using it, retarget to a free port (9300).
- `magicproj.py catalog`: parse Magic's lenient ISF JSON (480 of 480 `.fs` headers in Magic's and the user's module folders now parse; strict JSON rejected 10), add OSCSender and SyphonClient params.
- New eval 5 for the live-app rules.

## Description optimisation

- `scripts/run_loop.py` needs `claude -p`. The nested CLI fails here: `Failed to authenticate: OAuth session expired and could not be refreshed` (this session authenticates through the desktop host). Not run.
- Proxy instead: 20 trigger queries (10 should, 10 near-miss should-not; 12 train, 8 held out). Three independent Sonnet judges saw the skill list (this skill plus 13 real neighbours: hyperframes, music-to-video, run, qa, research, computer-use...) and picked the skill they would invoke per query.
- Current description: train 12/12, held-out 8/8, every query unanimous across the 3 judges. With nothing failing there was nothing for the loop to improve, so the description is unchanged.
- The proxy asks for an explicit choice, which triggers more readily than real use; rerun `run_loop.py` from a terminal where `claude -p` is logged in to confirm.

## Human review

- Viewer: `generate_review.py --static` pages for both iterations are in this session's scratchpad (`magic-projects-workspace/iteration-*/review.html`). The user has not reviewed them yet.

## Validation

- `quick_validate.py`: "Skill is valid!" (run as `uv run --no-project --with pyyaml python scripts/quick_validate.py <skill>`, since Homebrew's Python refuses `pip install --user`).

## Iteration 3: general Magic skill

The skill was reworked into a general Magic Music Visuals skill (no Blender in the main flow) and checked against Magic 3. New prompts in `evals.json`, fixtures copied from Magic's samples (`MIDIPiano`, `ManyScenes`, `DemoProject`) plus `hand_edited.magic`, a GlobalsExamples copy with three seeded faults. The iteration-1/2 lab prompts are kept in `evals-v1-lab.json`.

| Eval | With / without | Tokens with / without | Seconds with / without |
|---|---|---|---|
| 1 explain MIDIPiano's MIDI mapping | 6/6 / 6/6 | 108k / 108k | 147 / 153 |
| 2 playlist for a gig: 16 s crossfade, Syphon, looping | 9/9 / 8/9 | 90k / 84k | 69 / 93 |
| 3 generate Iterator spectrum + MIDI CC hue + OSC speed | 9/9 / 9/9 | 121k / 113k | 141 / 202 |
| 4 repair a hand-edited project | 7/7 / 7/7 | 82k / 82k | 90 / 131 |
| 5 4K stutter and 1080p60 export advice | 8/8 / 8/8 | 98k / 116k | 150 / 187 |
| 6 custom ISF module wired into a project | 8/8 / 8/8 | 110k / 93k | 149 / 131 |
| Total | 47/47 / 46/47 | 102k / 99k mean | 124 / 150 mean |

- Baselines again used `magicproj.py` from the worktree. The skill shows as time (17% faster) and as behaviour: the eval-5 baseline grepped Magic's whole preferences file, which contains an API key; skill runs read single keys.
- Baseline miss: eval 2 did not say that auto-advance is switched on in Magic and is not stored in the project.
- The runs found five tool issues, fixed and tested afterwards: `set_playlist` dropped existing entries (an Element without children is falsy), `check` assumed Tabs are in scene order (MIDIPiano's are not), `set` had no `--looping` or `--inputs`, and `--size` forced Syphon on without setting `fixedMagicSize`.
- The eval-3 grader first rejected a rotation driven through an intermediate Global; it now follows one hop.
- Viewer: `magic-projects-workspace/iteration-3/review.html` in this session's scratchpad.

## Description, general version

- New 20-query trigger set (`trigger_evals.json`): 10 general Magic tasks, 10 near-misses (Resolume, TouchDesigner, Synesthesia, Shadertoy GLSL, OBS Syphon, Ableton MIDI clock, a buy decision, this repo's Swift app).
- Same 3-judge proxy as before (`run_loop.py` still cannot authenticate): train 12/12, held-out 8/8, unanimous. Results in `evals/results/trigger-v2/`.
