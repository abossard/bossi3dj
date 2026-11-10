"""Continuous LOD for the Planet: CDLOD on the cube sphere (docs/research/synthwave-flight.md, "Continuous LOD").

Pure Python (no bpy), checked by docs/research/synthwave-flight/verify_flight.py.

- Each cube face is a quadtree root. A node (face, depth, i, j) is one N x N grid of cells, the same grid for every
  node, so a node at depth d has cells of FACE_ARC / 2^d / N.
- Selection by distance: a node splits while the camera is closer to its bounds than range(d + 1) + margin, with
  range(d) = K * size(d). Past the horizon nothing splits, so a free view still sees a whole sphere.
- Morph: every vertex moves toward its parent's lattice (odd vertices onto the midpoint of their even neighbours,
  along the cell diagonal (0,1)-(1,0) for odd-odd ones, the one Blender's Triangulate splits a grid cell along) by m = smoothstep(M0 * range(d), range(d), distance). A
  node only merges where its vertices are fully morphed, and only splits where they would be, so the surface is the
  same just before and after a change. With K large enough, a fine node's edge against a coarser neighbour is fully
  morphed onto the coarse edge, and the coarse neighbour is not morphed there: no cracks without stitching. The
  condition is K >= (2.83 + 2 * slack / size) / (2 * M0 - 1), slack being the selection lag's travel plus the bounds'
  padding; K 9 and M0 0.75 hold it at 155 m/s with 3 frames of lag (verify_flight.py, check 5).
- Bounds use each node's own height range (from its parent's grid, padded), not the planet's: loose bounds put a
  coarse neighbour's morph band on a fine edge.
- Blocks: the nodes are grouped by their ancestor BLOCK_UP depths up into objects, so a split or merge
  re-evaluates the few small objects it touches, not the planet.

Face convention as build_planet.cube_dir: face f (0..5: +x +y +z -x -y -z), axis f % 3, sign + for f < 3; the face
point (a, b) in equal-angle coordinates (-1..1) is normalize(n + tan(a pi/4) u + tan(b pi/4) v).
"""
import math

R = 16000.0
CENTRE = (0.0, 0.0, -R)
FACE_ARC = R * math.pi / 2.0      # m, a cube face's side on the sphere
H_LO, H_HI = -250.0, 650.0        # m: the surface lies between these heights (node bounds)


class Params:
    def __init__(self, n=8, k=9.0, m0=0.75, d_max=9, margin=0.0, block_up=2, cull=True):
        self.n, self.k, self.m0, self.d_max, self.margin, self.block_up, self.cull = n, k, m0, d_max, margin, block_up, cull

    def size(self, d):
        return FACE_ARC / (1 << d)

    def range(self, d):
        return self.k * self.size(d)


# ---------------------------------------------------------------- cube sphere
def _unit(k):
    return tuple(1.0 if i == k else 0.0 for i in range(3))


FACES = []
for _f in range(6):
    _axis, _s = _f % 3, (1.0 if _f < 3 else -1.0)
    _n = tuple(_s * c for c in _unit(_axis))
    _u = _unit((_axis + 1) % 3)
    _v = tuple(_s * c for c in _unit((_axis + 2) % 3))
    FACES.append((_n, _u, _v))


def face_dir(f, a, b):
    n, u, v = FACES[f]
    ta, tb = math.tan(a * math.pi / 4.0), math.tan(b * math.pi / 4.0)
    x, y, z = (n[0] + ta * u[0] + tb * v[0], n[1] + ta * u[1] + tb * v[1], n[2] + ta * u[2] + tb * v[2])
    l = math.sqrt(x * x + y * y + z * z)
    return (x / l, y / l, z / l)


def dir_face(p):
    """The face and equal-angle coordinates of a unit direction."""
    best = max(range(6), key=lambda f: sum(FACES[f][0][k] * p[k] for k in range(3)))
    n, u, v = FACES[best]
    dn = sum(n[k] * p[k] for k in range(3))
    a = math.atan(sum(u[k] * p[k] for k in range(3)) / dn) * 4.0 / math.pi
    b = math.atan(sum(v[k] * p[k] for k in range(3)) / dn) * 4.0 / math.pi
    return best, a, b


def node_ab(key, x, y, n):
    """Equal-angle coordinates of the node's lattice point (x, y), 0..n each."""
    f, d, i, j = key
    s = 2.0 / (1 << d)
    return -1.0 + (i + x / n) * s, -1.0 + (j + y / n) * s


def node_dir(key, x, y, n):
    a, b = node_ab(key, x, y, n)
    return face_dir(key[0], a, b)


def key_at(p, d):
    f, a, b = dir_face(p)
    m = 1 << d
    return (f, d, min(int((a + 1.0) / 2.0 * m), m - 1), min(int((b + 1.0) / 2.0 * m), m - 1))


# ---------------------------------------------------------------- bounds and selection
def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


_bounds = {}


def bounds(key, lo=H_LO, hi=H_HI):
    """A sphere (centre, radius) holding the node's surface for heights lo..hi, its centre direction and angular
    radius. Tight heights matter: the morph is set by the vertices' true distances, and loose bounds put a coarse
    neighbour's morph band on a fine node's edge (a crack) or a merge inside the parent's band (a pop)."""
    bk = (key, lo, hi)
    b = _bounds.get(bk)
    if b is None:
        c = node_dir(key, 0.5, 0.5, 1)
        rho = max(math.acos(min(1.0, sum(c[k] * q[k] for k in range(3))))
                  for q in (node_dir(key, x, y, 1) for x in (0, 1) for y in (0, 1)))
        rm = R + 0.5 * (lo + hi)
        rad = max(math.sqrt(r * r + rm * rm - 2.0 * r * rm * math.cos(rho)) for r in (R + lo, R + hi))
        rad = max(rad, 0.5 * (hi - lo))
        b = _bounds[bk] = (tuple(CENTRE[k] + c[k] * rm for k in range(3)), rad, c, rho)
    return b


def _seg_dist(q, a, b):
    """Distance from q to the segment a-b."""
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ll = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2]
    if ll <= 0.0:
        return _dist(q, a)
    t = min(max(((q[0] - a[0]) * ab[0] + (q[1] - a[1]) * ab[1] + (q[2] - a[2]) * ab[2]) / ll, 0.0), 1.0)
    return _dist(q, (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t))


def dist_to(key, cam, hr=None, ahead=None):
    """Distance from the camera to the node's bounds; with ahead, from the segment between the camera and where it
    will be (the look-ahead: the node is as fine as anywhere on the way asks)."""
    centre, rad = bounds(key, *((hr(key) if hr else None) or (H_LO, H_HI)))[:2]
    return max((_dist(cam, centre) if ahead is None else _seg_dist(centre, cam, ahead)) - rad, 0.0)


def horizon(cam):
    """past_horizon for one camera: the node lies wholly past its horizon, with H_HI mountains on both sides. The
    camera's part is worked out once (a selection asks for about 2000 nodes)."""
    rel = (cam[0] - CENTRE[0], cam[1] - CENTRE[1], cam[2] - CENTRE[2])
    r = math.sqrt(rel[0] * rel[0] + rel[1] * rel[1] + rel[2] * rel[2])
    ux, uy, uz = rel[0] / r, rel[1] / r, rel[2] / r
    lim = math.acos(min(R / max(r, R + 1.0), 1.0)) + math.acos(R / (R + H_HI))

    def past(key):
        c, rho = bounds(key)[2:]
        return math.acos(max(-1.0, min(1.0, c[0] * ux + c[1] * uy + c[2] * uz))) - rho > lim
    return past


def past_horizon(key, cam):
    return horizon(cam)(key)


def splits(key, cam, p, hr=None, past=None, ahead=None):
    d = key[1]
    if d >= p.d_max:
        return False
    if p.cull and (past or horizon(cam))(key):
        return False
    return dist_to(key, cam, hr, ahead) < p.range(d + 1) + p.margin


def children(key):
    f, d, i, j = key
    return [(f, d + 1, 2 * i + a, 2 * j + b) for b in (0, 1) for a in (0, 1)]


def select(cam, p, hr=None, ahead=None):
    """The leaves for a camera at cam: the nodes that do not split, under ones that do. hr(key) gives a node's
    height range (lo, hi), or None for H_LO..H_HI. With ahead (where the camera will be when the selection is
    drawn), distances are to the segment between the two: nodes on the way split early, while the nodes behind and
    beside the camera keep the small margin the no-crack and no-pop conditions allow (a margin as large as the
    travel broke them: metre-sized cracks at 150 m)."""
    out, stack = [], [(f, 0, 0, 0) for f in range(6)]
    now = horizon(cam)
    if ahead is None:
        past = now
    else:
        later = horizon(ahead)

        def past(key):
            return now(key) and later(key)
    while stack:
        key = stack.pop()
        if splits(key, cam, p, hr, past, ahead):
            stack.extend(children(key))
        else:
            out.append(key)
    return out


def child_range(parent_grid, key, n, pad):
    """A child's height range from its quadrant of the parent's grid (heights over R), padded for the detail between
    the parent's samples."""
    ox, oy = key[2] % 2, key[3] % 2
    hs = [parent_grid[y][x] for y in range(oy * n // 2, oy * n // 2 + n // 2 + 1) for x in range(ox * n // 2, ox * n // 2 + n // 2 + 1)]
    return min(hs) - pad, max(hs) + pad


def block_of(key, p):
    """The object a node belongs to: its depth and its ancestor BLOCK_UP depths up (4^BLOCK_UP nodes at most)."""
    f, d, i, j = key
    up = min(p.block_up, d)
    return (f, d, i >> up, j >> up)


# ---------------------------------------------------------------- morph
def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def morph_factor(dist, d, p):
    """0 near the camera, 1 from range(d) on: there the vertex sits on its parent's lattice."""
    if d == 0:
        return 0.0
    rd = p.range(d)
    return smoothstep(p.m0 * rd, rd, dist)


def node_grid(key, height, p):
    """The node's (n+1) x (n+1) unmorphed positions, height(dir) in m over R."""
    n = p.n
    g = []
    for y in range(n + 1):
        row = []
        for x in range(n + 1):
            u = node_dir(key, x, y, n)
            r = R + height(u)
            row.append((CENTRE[0] + u[0] * r, CENTRE[1] + u[1] * r, CENTRE[2] + u[2] * r))
        g.append(row)
    return g


def _mid(a, b):
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def parent_target(g, x, y):
    """Where lattice point (x, y) lies on the parent's lattice (cells twice as wide, diagonal (0,1)-(1,0))."""
    ox, oy = x % 2, y % 2
    if not ox and not oy:
        return g[y][x]
    if ox and not oy:
        return _mid(g[y][x - 1], g[y][x + 1])
    if oy and not ox:
        return _mid(g[y - 1][x], g[y + 1][x])
    return _mid(g[y + 1][x - 1], g[y - 1][x + 1])


def morphed(key, g, cam, p):
    """The node's positions as the vertex shader draws them for a camera at cam."""
    d, n = key[1], p.n
    out = []
    for y in range(n + 1):
        row = []
        for x in range(n + 1):
            q = g[y][x]
            m = morph_factor(_dist(q, cam), d, p)
            if m > 0.0 and (x % 2 or y % 2):
                t = parent_target(g, x, y)
                q = (q[0] + (t[0] - q[0]) * m, q[1] + (t[1] - q[1]) * m, q[2] + (t[2] - q[2]) * m)
            row.append(q)
        out.append(row)
    return out


def on_mesh(gm, px, py):
    """A point of a drawn node at lattice coordinates (px, py) (halves allowed), on its triangles."""
    x0, y0 = int(math.floor(px)), int(math.floor(py))
    fx, fy = px - x0, py - y0
    if fx == 0.0 and fy == 0.0:
        return gm[y0][x0]
    if fy == 0.0:
        return _mid(gm[y0][x0], gm[y0][x0 + 1])
    if fx == 0.0:
        return _mid(gm[y0][x0], gm[y0 + 1][x0])
    return _mid(gm[y0 + 1][x0], gm[y0][x0 + 1])
