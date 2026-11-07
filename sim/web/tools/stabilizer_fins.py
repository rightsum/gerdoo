#!/usr/bin/env python3
"""Snap-off stabilizer fins for the covers, which print standing (log 042).

  python3 stabilizer_fins.py <front|back> <out.stl> [<samples.json>]

A cover is a 2.4 mm shell (r 125.6-128) up to 181 mm tall, standing on its bottom edge. Each fin is a
triangle on the inside of the shell, standing on the bed: it widens the footprint and props the wall.
The fin stops 0.6 mm short of the shell and joins it only through small tabs, so it snaps off and leaves
nubs on the hidden inner face. Everything is in preview coordinates (Y up, front +z, deck top y 0), the
same frame as the cover STLs, so the plate can use the cover's own map.

samples.json (optional) lists points inside the fins (must be outside the cover) and inside the tabs
(must be inside the cover), for checking against the Fusion bodies.
"""
import json
import math
import struct
import sys

R_IN = 125.6
THICK = 1.6      # fin thickness
GAP = 0.6        # fin to shell
TAB_H = 1.5      # tab height (y)
TAB_PITCH = 8.0
OVERLAP = 0.5    # tabs reach this far into the shell

# (angle from the cover's centre line in degrees, top of the fin y, width on the bed)
FINS = {
    # front: clear of the chevron louvers (|x| < 22, y 9-39) and the KA009 cradle (x ~50-60, y > 55)
    # the wider covers (log 042): two more fins near each end, where the arc lifted off the bed
    # taller after the v5 front cover toppled at 86 mm (log 042): the wing ends and the free middle are braced
    # most of the way up; +36 deg stays low because the KA009 board cradle sits just above it (y 52-66)
    # +-40 deg up to y 120: braces the upper half (the heavy heart/cup hangs 35 mm inward), after a second topple at ~80 %
    'front': [(-56, 80, 24), (-40, 120, 32), (-24, 70, 30), (24, 70, 30), (40, 120, 32), (56, 80, 24)],
    # back: outside the gill louvers (21-33 deg) and clear of the pogo sleeves (x +/-20)
    'back': [(-54, 75, 24), (-38, 40, 26), (-13, 6, 14), (13, 6, 14), (38, 40, 26), (54, 75, 24)],
}
Y0 = -10.0       # the covers' bottom edge, on the bed


def frame(side, a):
    s, c = math.sin(math.radians(a)), math.cos(math.radians(a))
    zs = 1.0 if side == 'front' else -1.0

    def p(u, v, w):  # u: inward from the inner face, v: y, w: across the fin
        r = R_IN - u
        return (r * s + w * c, v, zs * (r * c - w * s))
    return p


def prism(p, poly, w0, w1):
    """Triangles of a prism: the (u, v) polygon, extruded across w."""
    n = len(poly)
    a = [p(u, v, w0) for u, v in poly]
    b = [p(u, v, w1) for u, v in poly]
    tris = []
    for i in range(1, n - 1):
        tris.append((a[0], a[i + 1], a[i]))
        tris.append((b[0], b[i], b[i + 1]))
    for i in range(n):
        j = (i + 1) % n
        tris.append((a[i], a[j], b[j]))
        tris.append((a[i], b[j], b[i]))
    return tris


def fin_parts(side, a, top, width):
    p = frame(side, a)
    h = THICK / 2
    tris = prism(p, [(GAP, Y0), (GAP + width, Y0), (GAP, top)], -h, h)
    tabs = []
    v = Y0
    while v + TAB_H <= top - 3:
        tabs.append(v)
        tris += prism(p, [(-OVERLAP, v), (GAP + 0.3, v), (GAP + 0.3, v + TAB_H), (-OVERLAP, v + TAB_H)], -h, h)
        v += TAB_PITCH
    fin_pts = []
    for k in range(1, 12):
        for m in range(1, 8):
            u = GAP + 0.2 + (width - 0.4) * k / 12
            vt = Y0 + (top - Y0) * (1 - (u - GAP) / width)
            vv = Y0 + 0.2 + (vt - Y0 - 0.4) * m / 8
            if vv < vt - 0.2:
                fin_pts.append(p(u, vv, 0.0))
    tab_pts = [p(-OVERLAP / 2, v + TAB_H / 2, 0.0) for v in tabs]
    return tris, fin_pts, tab_pts


def write_stl(path, tris):
    with open(path, 'wb') as f:
        f.write(b'gerdoo cover stabilizer fins'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for t in tris:
            f.write(struct.pack('<3f', 0, 0, 0))
            for q in t:
                f.write(struct.pack('<3f', *q))
            f.write(b'\0\0')


def yoke_fins():
    """neck head yoke, printed upside down (print Z = 278 - y): its 3.5 mm arms stand 29 mm free above the pad,
    with the horn holes near their tops, and the nozzle knocked them over twice. Two fins on the outside of each
    arm, in the z bands either side of the horn screw holes, from the bed to Z 45; tabs only below the
    countersinks (Z <= 36)."""
    tris, fin_pts, tab_pts = [], [], []
    for s in (1, -1):
        for z0, z1 in ((83.0, 86.0), (103.0, 106.0)):
            p = lambda u, v, w: (s * u, v, w)
            # (u, v) polygon: u = |x|, v = y; the bed is at y 278
            tris += prism(p, [(22.6, 278.0), (40.6, 278.0), (22.6, 233.0)], z0, z1)
            v = 276.5
            while v - 1.5 >= 242.0:
                tris += prism(p, [(21.5, v), (22.9, v), (22.9, v - 1.5), (21.5, v - 1.5)], z0, z1)
                tab_pts.append((s * 21.75, v - 0.75, (z0 + z1) / 2))
                v -= 8.0
            for k in range(1, 8):
                for m in range(1, 6):
                    u = 22.8 + 17.6 * k / 8
                    vtop = 278.0 - 45.0 * (1 - (u - 22.6) / 18.0)
                    vv = 278.0 - (278.0 - vtop - 0.4) * m / 6
                    fin_pts.append((s * u, vv, (z0 + z1) / 2))
    return tris, fin_pts, tab_pts


if __name__ == '__main__':
    side, out = sys.argv[1], sys.argv[2]
    if side == 'yoke':
        tris, fp, tp = yoke_fins()
        write_stl(out, tris)
        print('yoke: 4 fins, %d triangles -> %s' % (len(tris), out))
        if len(sys.argv) > 3:
            json.dump({'fin': fp, 'tab': tp}, open(sys.argv[3], 'w'))
        sys.exit(0)
    tris, samples = [], {'fin': [], 'tab': []}
    for a, top, width in FINS[side]:
        t, fp, tp = fin_parts(side, a, top, width)
        tris += t
        samples['fin'] += fp
        samples['tab'] += tp
    write_stl(out, tris)
    print('%s: %d fins, %d triangles -> %s' % (side, len(FINS[side]), len(tris), out))
    if len(sys.argv) > 3:
        json.dump(samples, open(sys.argv[3], 'w'))
