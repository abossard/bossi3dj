#!/usr/bin/env python3
"""One agent session drives the live Blender at a time.

A session takes the lock with its first state-changing Blender MCP call and keeps it while it
keeps calling; the lock expires after TTL seconds without a call. Another session's call is
denied with the owner and the remaining time, so nobody has to negotiate slots by message.

    blender_lock.py hook      PreToolUse hook: reads the hook JSON on stdin (.claude/settings.json)
    blender_lock.py status    lock owner, age, and the running Blender processes, as JSON
    blender_lock.py release [--force]   drop an expired lock; --force drops a live one
"""
import json
import os
import subprocess
import sys
import time

LOCK = os.path.expanduser(os.environ.get("BOSSI3DJ_BLENDER_LOCK", "~/.bossi3dj/blender.lock"))
TTL = int(os.environ.get("BOSSI3DJ_BLENDER_LOCK_TTL", "300"))


def read_lock():
    try:
        with open(LOCK) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_lock(lock):
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    tmp = LOCK + ".%d" % os.getpid()
    with open(tmp, "w") as f:
        json.dump(lock, f)
    os.replace(tmp, LOCK)


def decide(lock, session, now, ttl=TTL):
    """(allowed, lock to store or None, reason). Pure."""
    if lock and lock.get("session") != session and now - lock.get("last", 0) < ttl:
        left = int(ttl - (now - lock["last"]))
        return False, None, (
            "Blender is held by session %s (%s) since %s; its lock expires in %d s if it stays idle. "
            "Do work that needs no Blender meanwhile, or ask the user before `blender_lock.py release --force`."
            % (lock["session"], lock.get("cwd", "?"), time.strftime("%H:%M:%S", time.localtime(lock.get("since", now))), left))
    since = lock["since"] if lock and lock.get("session") == session else now
    return True, {"session": session, "since": since, "last": now, "cwd": os.getcwd()}, ""


def hook():
    event = json.load(sys.stdin)
    allowed, lock, reason = decide(read_lock(), event.get("session_id", "unknown"), time.time())
    if allowed:
        write_lock(lock)
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    return 0


def status():
    lock, now = read_lock(), time.time()
    pids = subprocess.run(["pgrep", "-lf", "Blender.app/Contents/MacOS/Blender"], capture_output=True, text=True).stdout.split("\n")
    print(json.dumps({
        "lock": lock,
        "idle_s": int(now - lock["last"]) if lock else None,
        "expired": bool(lock) and now - lock["last"] >= TTL,
        "ttl_s": TTL,
        "blender": [p for p in pids if p],
    }, indent=1))
    return 0


def release(force):
    lock = read_lock()
    if lock and not force and time.time() - lock.get("last", 0) < TTL:
        print("lock is live (session %s); pass --force to drop it" % lock["session"])
        return 1
    try:
        os.remove(LOCK)
    except FileNotFoundError:
        pass
    print("released")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    sys.exit({"hook": hook, "status": status}.get(cmd, lambda: release("--force" in sys.argv))())
