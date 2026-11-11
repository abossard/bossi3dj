"""Art-Net input for the OSC bridge: ArtDmx frames in, the bridge's wire values out. Standard library only, no bpy.

A DMX desk or QLC+ sends one frame of up to 512 channels a few times a second, all channels every time. The fixture
(qlc/*.qxf, made from osc/contract.json by osc/qlc_fixture.py) has one channel per address the Blender scene reacts to,
in contract order, starting at the DMX start address (default 1) of one universe (default 0). This module turns a frame
into (address, wire value) pairs for exactly the channels that changed, so a resting fader never fights Magic or the page:

- the first frame after a start (or after the universe, address or shot count changes) is the baseline and applies nothing;
- a float channel maps 0..255 linearly onto the row's wire range;
- /vj/cam splits 0..255 into equal ranges, one per shot of the running scene (12 on the planet, 7 on the island);
- a trigger fires when its channel rises through TRIGGER_AT (128); the strength grows from 0.5 at 128 to the row's
  wire maximum at 255; when the channel falls below 128 the trigger gets 0 again, so the next rise is a new edge.

ArtNetInput owns the udp socket (non-blocking, address reuse on so QLC+ can share the port) and never raises: a failed
bind is reported in `error`. The bridge polls it from its own timer.
"""
import socket
import struct

ARTNET_PORT = 6454
OP_DMX = 0x5000
ID = b"Art-Net\x00"
TRIGGER_AT = 128
TRIGGER_MIN = 0.5          # the strength a trigger gets at the threshold; the runtime's rising edge is "above 0.5"
MAX_FRAMES_PER_POLL = 200


def parse_artdmx(data):
    """(port-address, sequence, dmx bytes) of an ArtDmx packet, or None for anything else (short, wrong id, other OpCode)."""
    if len(data) < 18 or data[:8] != ID:
        return None
    if struct.unpack("<H", data[8:10])[0] != OP_DMX:
        return None
    length = struct.unpack(">H", data[16:18])[0]
    if length < 1 or length > 512 or len(data) < 18 + length:
        return None
    universe = (data[15] & 0x7F) << 8 | data[14]          # Net (7 bits) and SubUni
    return universe, data[12], bytes(data[18:18 + length])


def encode_artdmx(universe, dmx, sequence=0):
    """An ArtDmx packet (Art-Net 4, protocol version 14). The data is padded to an even length of at least 2."""
    dmx = bytes(dmx)[:512]
    if len(dmx) % 2 or not dmx:
        dmx += b"\x00" * (2 - len(dmx) % 2 if dmx else 2)
    return (ID + struct.pack("<H", OP_DMX) + bytes([0, 14, sequence & 0xFF, 0, universe & 0xFF, (universe >> 8) & 0x7F])
            + struct.pack(">H", len(dmx)) + dmx)


def channel_map(rows):
    """[(address, kind, wire min, wire max)] of the rows the scene uses, in the given (contract) order."""
    return [(a, k, float(lo), float(hi)) for a, k, lo, hi in rows]


class DmxDecoder:
    """Frames to changes. channels: channel_map(). shots: how many shots the running scene has (the /vj/cam ranges)."""

    CAMERA = "/vj/cam"

    def __init__(self, channels, shots=12, universe=0, address=1):
        self.channels = list(channels)
        self.shots, self.universe, self.address = shots, universe, address
        self.previous = None            # the frame the next one is compared with; None: the next frame is the baseline
        self.frames = 0                 # frames of our universe
        self.other = 0                  # frames of other universes
        self.changes = 0

    def configure(self, universe=None, address=None, shots=None):
        """Changes a setting; the next frame becomes the baseline again."""
        if universe is not None:
            self.universe = int(universe)
        if address is not None:
            self.address = min(max(int(address), 1), 512)
        if shots is not None:
            self.shots = max(int(shots), 1)
        self.previous = None

    def wire(self, row, v):
        address, kind, lo, hi = row
        if address == self.CAMERA:
            return float(min(v * self.shots // 256, self.shots - 1))
        return lo + v / 255.0 * (hi - lo)

    def feed(self, universe, dmx):
        """The (address, wire value) pairs for the channels of `dmx` that changed since the last frame of our universe."""
        if universe != self.universe:
            self.other += 1
            return []
        self.frames += 1
        base = self.address - 1
        now = {i: dmx[base + i] for i in range(len(self.channels)) if base + i < len(dmx)}
        before, self.previous = self.previous, now
        if before is None:
            return []                                   # the baseline
        out = []
        for i, v in now.items():
            was = before.get(i)
            if was is None or was == v:                 # a channel the last frame was too short for is a baseline too
                continue
            row = self.channels[i]
            if row[1] == "trigger":
                if v >= TRIGGER_AT and was < TRIGGER_AT:
                    out.append((row[0], TRIGGER_MIN + (v - TRIGGER_AT) / (255.0 - TRIGGER_AT) * (row[3] - TRIGGER_MIN)))
                elif v < TRIGGER_AT and was >= TRIGGER_AT:
                    out.append((row[0], 0.0))
                continue
            out.append((row[0], self.wire(row, v)))
        self.changes += len(out)
        return out


class ArtNetInput:
    """The socket and the decoder. `host` "" listens on every interface (broadcast frames arrive there)."""

    def __init__(self, decoder, host="", port=ARTNET_PORT, enabled=True):
        self.decoder = decoder
        self.host, self.port, self.enabled = host, port, enabled
        self.sock, self.error = None, None
        self.packets = 0                # ArtDmx packets parsed
        self.malformed = 0              # datagrams that were not ArtDmx
        self.last_src = None
        if enabled:
            self.open()

    def open(self):
        self.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)      # BSD and macOS: two listeners share the port
            sock.setblocking(False)
            sock.bind((self.host, self.port))
        except OSError as e:
            sock.close()
            self.sock, self.error = None, "%s (udp %d)" % (e, self.port)
            return False
        self.sock, self.error = sock, None
        return True

    def bound_port(self):
        return self.sock.getsockname()[1] if self.sock is not None else None

    def set_enabled(self, on):
        self.enabled = bool(on)
        if self.enabled and self.sock is None:
            self.decoder.previous = None
            self.open()
        elif not self.enabled:
            self.close()

    def poll(self):
        """[(sender, [(address, wire value), ...])] for the frames waiting; never raises."""
        out = []
        if self.sock is None:
            return out
        for _ in range(MAX_FRAMES_PER_POLL):
            try:
                data, src = self.sock.recvfrom(2048)
            except BlockingIOError:
                break
            except OSError as e:
                self.error = str(e)
                break
            frame = parse_artdmx(data)
            if frame is None:
                self.malformed += 1
                continue
            self.packets += 1
            self.last_src = src
            changes = self.decoder.feed(frame[0], frame[2])
            if changes:
                out.append((src, changes))
        return out

    def state(self):
        d = self.decoder
        return {"enabled": self.enabled, "bound": self.sock is not None, "port": self.bound_port(), "error": self.error,
                "universe": d.universe, "address": d.address, "channels": len(d.channels), "shots": d.shots,
                "packets": self.packets, "malformed": self.malformed, "frames": d.frames, "other_universe": d.other,
                "changes": d.changes, "last_src": "%s:%d" % self.last_src[:2] if self.last_src else None}

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
