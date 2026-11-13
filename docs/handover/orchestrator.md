# Orchestrator hand-over (2026-11-13)

For the session that takes over orchestration. Where the work stands and what is decided is in [STATE.md](../../STATE.md); read "Now" and "Decided by the user" first. This note holds what `STATE.md` does not: how the orchestration itself works here.

## The job

- The user gives direction; sub sessions do the work; the orchestrator briefs them, hands out the GPU, checks results itself, keeps `STATE.md` and [presentable-plan.md](presentable-plan.md) current, and commits and pushes on the user's word.
- The orchestrator edits only `STATE.md`, this folder's plan and notes, and small glue fixes. Everything else goes to a session.
- Work is paused since 2026-11-12. Start nothing until the user says go.

## Sessions to reuse (all in the main checkout, branch `integration/presentable`)

| Session | Id | Model, effort | Knows |
|---|---|---|---|
| B10 Blender: finish the planet | `local_d14375d0-dec7-4a71-80ba-025aef62c613` | Opus 5.5, high | planet build, Flight stream, review tools; next: the terrain test ([terrain-test.md](terrain-test.md)); 580k tokens of context on 2026-11-12 |
| B9 Planet: night-edge guard | `local_bc25e601-456e-4cdc-a717-bc0703c56812` | Sonnet 5.5, medium | bridge, Art-Net, QLC+ fixture, README and manual generators, start-up guard |
| B11 Handbook, control page, Magic | `local_849d7786-a4c9-457f-bb9a-5504ae4eb2f5` | Sonnet 5.5, medium | handbook, page on 9210, Magic generators and live proof |

Every other session in the list is finished or parked (all Godot ones; notes in [godot-parked.md](godot-parked.md)).

## Mechanics learned the hard way

- A new session can only be started in a turn the user's own message starts, and not while the user works over Remote Control. On a turn started by a session's report, continue existing sessions with `SendMessage` (`to` = the session id).
- Reuse before starting: send the follow-up to the session that knows the area, then read its context with `get_usage` once it runs (an idle session reports nothing). Hand over to a fresh one only above about 350k tokens, or tell the user the number and let them choose.
- A message to a working session may only arrive when its turn ends. To get it read now, `stop_session` and the queued message runs next; every queued message runs, so send a replacing message before stopping.
- `stop_session`, `set_session_model` and `set_session_effort` are rewritten by a hook: the first call is refused and quotes the input to send again (it adds a `session` field). Send exactly that, alone in the next response.
- One live app at a time (Blender or Godot), one Blender at a time. Give the slot by message, have sessions close Blender when done, and check with `pgrep -f "MacOS/Blender"` before granting. Two sessions once opened Blender on each other.
- Never put an app name into a long-running shell command of your own: `make status` and the Makefile guards use `pgrep -f` and count such a shell as the app.
- Images and videos never enter the orchestrator's context. Sessions send frames to the `shot-reviewer` subagent; files for the user go out with SendUserFile.
- Check a session's claim before reporting it: rerun `make magic-test`, `make osc-test`, `make blender-test`, `make godot-test`, read the note it wrote, look at `git status --short`.

## Pushing (only on the user's word)

`main` and `integration/presentable` move together by fast-forward, without switching branches in the checkout:

```bash
target=$(git rev-parse HEAD)
git push origin "${target}:refs/heads/integration/presentable" "${target}:refs/heads/main"
git fetch -q . "${target}:main"
```

- Use the braces: zsh mangles `$target:refs`.
- Before every push, no model file may be in the commits: `for c in $(git rev-list origin/main..HEAD); do git ls-tree -r --name-only $c -- godot/colossus/assets/models godot/colossus/assets/incoming godot/colossus/assets/mixamo; done | wc -l` must print 0.
- Three state commits after `5338a61` are local only on 2026-11-13.

## Left as it is on the Mac

- The control page is in LAN mode (`python3 tools/blender_page_lan.py off` turns it back).
- MagicBeta may be open; it is the user's app.
- QLC+ has never opened the generated fixture or workspace; the checklist is in [docs/artnet-qlc.md](../artnet-qlc.md) and needs the user.

## What the user cares about

- Short answers, bullets, no filler, no em dashes, no AI attribution in commits.
- The live, moving picture, judged with show defaults. Still-frame passes and self-checks are not "presentable".
- Simplicity over features. The chosen direction is a path camera with targets on one terrain; the terrain test comes first.
- Cost: reuse sessions, few rebuilds and review rounds, the cheapest model that does the job, and say the plan usage when it gets high.
