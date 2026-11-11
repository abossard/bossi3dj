#!/usr/bin/env python3
"""Let a phone on the same network open the scene's control page, or take that back.

    python3 tools/blender_page_lan.py on|off|status

The page listens on 127.0.0.1 only. `on` writes blender/local/page.json ({"host": "lan"}, git-ignored) so the next start of the scene
(`make blender-open`) listens on every interface; any device on the network can then drive the scene. `off` removes the file.
Prints the addresses to open. Standard library only.
"""
import json
import os
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "blender", "scenes"))
import page_model  # noqa: E402


def addresses():
    """This Mac's address on the network the phone is on (the one a UDP socket would route out of), and its Bonjour name."""
    out = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))          # no packet is sent: this only picks the interface
        out.append("http://%s:9210" % s.getsockname()[0])
        s.close()
    except OSError:
        pass
    name = socket.gethostname()
    if name:
        out.append("http://%s:9210" % name)
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    path = page_model.SETTINGS_FILE
    if cmd == "on":
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"host": "lan"}, f)
    elif cmd == "off":
        if os.path.exists(path):
            os.remove(path)
    elif cmd != "status":
        print(__doc__)
        return 2
    host = page_model.read_settings(path)["host"]
    print("control page: %s" % ("listens on every interface, any device on the network can drive the scene" if host == "lan" else "listens on 127.0.0.1 only"))
    if host == "lan":
        print("phone: " + ", ".join(addresses()))
    print("takes effect at the next start of the scene (make blender-open)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
