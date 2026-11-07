#!/usr/bin/env python3
"""Static and quasi-static checks for gerdoo: mass, centre of gravity, tipping, traction,
drive torque and arm servo torque, per arm pose.  Sim frame: X forward, Y left, Z up (mm),
ground at Z = 0.  Usage: python3 physics.py [gerdoo.urdf]  (writes physics.json next to it)
"""
import json, math, os, sys, xml.etree.ElementTree as ET

G = 9.81
GROUND = 66.7
def sim(p):  # preview (x, y, z) mm -> sim
    return (p[2], p[0], p[1] + GROUND)

# ---- body (everything but the arm links), grams at preview-frame centroids ----
# printed: Fusion volume (cm3) x 1.25 g/cm3 x fill factor (plates 0.5, shells 0.9, bulky 0.6)
PRINTED = [
    ('1st layer deck',        487.3, 0.5, (0, -6, 2)),   # +11 cm3: the 4th pod (log 034)
    ('caster mounts',          45.8, 0.6, (0, -19, 0)),
    ('2nd floor',             347.6, 0.5, (0, 82, 0)),
    ('3rd floor',             279.6, 0.5, (0, 166, 4)),
    ('front cover',            98.0, 0.9, (0, 85, 117)),
    ('back cover',             46.0, 0.9, (0, 40, -115)),
    ('arm base L',            200.6, 0.6, (135, 31, -14)),
    ('arm base R',            200.6, 0.6, (-135, 31, -14)),
    ('posts 1st->2nd (4)',     63.6, 0.8, (2.5, 38, 0)),
    ('round posts (2)',        32.2, 0.8, (0, 40, 0)),
    ('posts 2nd->3rd (4)',     61.2, 0.8, (2.5, 124, 0)),
    ('board holders',          19.7, 0.6, (0, 5, 4)),
    ('lidar holder v2',        69.3, 0.6, (0, 245, 0)),
    ('screen bezel',           41.2, 0.6, (0, 262, 108)),
    ('screen-board bracket',    9.6, 0.6, (0, 262, 70)),
    ('neck pan base + clamp',  14.3, 0.6, (0, 190, 82)),
    ('neck arm',                8.4, 0.6, (0, 216, 75)),
    ('neck head yoke',         11.6, 0.6, (0, 245, 99)),
    ('antenna brackets',       20.4, 0.6, (0, 89, -118)),
]
# bought: grams (datasheet where known, else estimate -- marked ~)
BOUGHT = [
    ('3S2P 21700 pack + BMS + holder ~', 500, (0, 22, -66)),
    ('copper posts', 40, (0, 23, -66)),
    ('IBT-2 x2 ~', 132, (0, 15, 50)),
    ('Teensy + Treedix ~', 35, (0, 12, 68)),
    ('HC-SR04P front x2', 18, (0, -22, 95)),
    ('HC-SR04P back x2', 18, (0, -22, -95)),   # 4 pods since log 034
    ('Jetson Orin Nano dev kit ~', 250, (0, 130, 0)),
    ('UPS (C) + 3x 21700 ~', 234, (0, 93, 0)),
    ('XVF3800 core board ~', 30, (0, 93, 76)),
    ('mic ring + 1.69" display ~', 30, (0, 124, 125)),
    ('USB hub ~', 60, (0, 104, -74)),
    ('speaker (ALMOCN 2in, 18 g)', 18, (0, 152, -75)),
    ('power boards ~', 92, (10, 28, 4)),
    ('36GP-555 gearmotor x2 ~', 600, (0, -34, 0)),
    ('motor brackets x2 ~', 80, (0, -20, 0)),
    ('wheels x2 ~', 120, (0, -34, 0)),
    ('couplers x2', 30, (0, -34, 0)),
    ('casters x2 ~', 60, (0, -50, 0)),
    ('RPLIDAR C1', 110, (0, 340, 0)),
    ('5.5" panel ~', 100, (0, 262, 112)),
    ('screen driver board ~', 30, (0, 262, 66)),
    ('Logitech Brio 500', 63, (0, 317, 105)),
    ('neck: 2x STS3215 (55 g)', 110, (0, 213, 77)),
    ('WiFi antennas x2 ~', 40, (0, 148, -128)),
    ('wiring and fasteners ~', 250, (0, 40, 0)),
]

def body_parts():
    parts = [(n, v * 1.25 * f, sim(c)) for n, v, f, c in PRINTED]
    parts += [(n, m, sim(c)) for n, m, c in BOUGHT]
    return parts

# ---- arms from the URDF ----
def load_urdf(path):
    r = ET.parse(path).getroot()
    J = {j.get('name'): j for j in r.findall('joint')}
    links = {l.get('name'): l for l in r.findall('link')}
    return J, links

def mmul(a, b): return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
def trans(x, y, z): return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]
def rot(ax, t):
    x, y, z = ax; n = math.sqrt(x * x + y * y + z * z); x, y, z = x / n, y / n, z / n
    c, s, C = math.cos(t), math.sin(t), 1 - math.cos(t)
    return [[c + x * x * C, x * y * C - z * s, x * z * C + y * s, 0], [y * x * C + z * s, c + y * y * C, y * z * C - x * s, 0],
            [z * x * C - y * s, z * y * C + x * s, c + z * z * C, 0], [0, 0, 0, 1]]
def rpy(r_, p, y): return mmul(mmul(rot((0, 0, 1), y), rot((0, 1, 0), p)), rot((1, 0, 0), r_))

def fk_all(J, q):
    child = {}
    for n, j in J.items(): child.setdefault(j.find('parent').get('link'), []).append(n)
    T = {}
    def walk(link, M):
        T[link] = M
        for n in child.get(link, []):
            j = J[n]; o = j.find('origin')
            Mj = mmul(M, mmul(trans(*[float(v) for v in o.get('xyz').split()]), rpy(*[float(v) for v in o.get('rpy').split()])))
            if j.get('type') in ('revolute', 'continuous', 'prismatic'):
                ax = [float(v) for v in j.find('axis').get('xyz').split()]
                v = q.get(n, 0.0)
                mim = j.find('mimic')
                if mim is not None: v = q.get(mim.get('joint'), 0.0) * float(mim.get('multiplier'))
                if j.get('type') == 'prismatic': Mj = mmul(Mj, trans(*[a * v for a in ax]))
                else: Mj = mmul(Mj, rot(ax, v))
            walk(j.find('child').get('link'), Mj)
    walk('base_link', [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    return T

ELROBOT = None
def arm_parts(J, links, q, payload_g=0):
    """Arm link masses come from the ElRobot follower URDF in the norma-core repo (inertial blocks)."""
    global ELROBOT
    if ELROBOT is None:
        here = os.path.dirname(os.path.abspath(__file__))
        src = os.environ.get('ELROBOT_URDF', os.path.join(here, 'elrobot_follower.urdf'))
        ELROBOT = {l.get('name'): l for l in ET.parse(src).getroot().findall('link')}
    T = fk_all(J, q)
    parts = []
    for name, M in T.items():
        if not (name.startswith('L_') or name.startswith('R_')): continue
        src = ELROBOT.get(name[2:])
        if src is None or name.endswith('base_link'): continue   # the table base is replaced by gerdoo's arm base
        ine = src.find('inertial')
        m = float(ine.find('mass').get('value')) * 1000
        c = [float(v) for v in ine.find('origin').get('xyz').split()]
        p = [sum(M[i][k] * c[k] for k in range(3)) + M[i][3] for i in range(3)]
        parts.append((name, m, tuple(v * 1000 for v in p)))
    if payload_g:
        for s in 'LR':
            a = T[s + '_Gripper_Base_v1_1']; b = T[s + '_ST3215_8_v1_1']
            pa = [a[i][3] for i in range(3)]; pb = [b[i][3] for i in range(3)]
            d = [pb[i] - pa[i] for i in range(3)]; Ld = math.sqrt(sum(x * x for x in d))
            tip = [pb[i] + 0.05 * d[i] / Ld for i in range(3)]
            parts.append((s + ' payload', payload_g, tuple(v * 1000 for v in tip)))
    return parts, T

def cog(parts):
    M = sum(m for _, m, _ in parts)
    return M, tuple(sum(m * p[i] for _, m, p in parts) / M for i in range(3))

# support polygon: wheel contacts (centre of tread) and the caster wheels' contacts.
# A 1" swivel caster's wheel trails ~10 mm behind its pivot: after driving forward the front contact
# is at +80 and the back at -100; after reversing, +100 and -80.
WHEEL_Y, CASTER_X, TRAIL = 145.65, 90.0, 10.0
CASTER_STATES = {'pivots': 0.0, 'after forward': 1.0, 'after reverse': -1.0}
POLY = [(CASTER_X, 0.0), (0.0, WHEEL_Y), (-CASTER_X, 0.0), (0.0, -WHEEL_Y)]
def set_casters(state):
    global POLY
    k = CASTER_STATES[state]
    POLY = [(CASTER_X - k * TRAIL, 0.0), (0.0, WHEEL_Y), (-CASTER_X - k * TRAIL, 0.0), (0.0, -WHEEL_Y)]

def edge_margin(pt):
    """Signed distance from the CoG ground point to each polygon edge (positive inside)."""
    out = []
    for i in range(4):
        (x1, y1), (x2, y2) = POLY[i], POLY[(i + 1) % 4]
        ex, ey = x2 - x1, y2 - y1; L = math.hypot(ex, ey)
        nx, ny = ey / L, -ex / L          # polygon is CCW, so the inward normal is (-ey, ex)/L ... check sign below
        d = ((pt[0] - x1) * -ey + (pt[1] - y1) * ex) / L
        out.append(d)
    return out

def accel_limit(c, direction):
    """a/g at which the CoG ground point, shifted by h*a/g opposite to the acceleration, leaves the polygon."""
    dx, dy = direction
    lo, hi = 0.0, 3.0
    for _ in range(60):
        mid = (lo + hi) / 2
        p = (c[0] + dx * c[2] * mid, c[1] + dy * c[2] * mid)
        if min(edge_margin(p)) > 0: lo = mid
        else: hi = mid
    return lo

def arm_torques(J, links, q, side, payload_g):
    """Gravity torque about each of the arm's joint axes (N m), from every link beyond it plus payload."""
    T = fk_all(J, q)
    parts, _ = arm_parts(J, links, q, payload_g)
    out = {}
    for k in ('j2', 'j3', 'j4', 'j6'):
        jn = side + '_' + k
        j = J[jn]
        child = j.find('child').get('link')
        M = T[child]
        ax = [float(v) for v in j.find('axis').get('xyz').split()]
        axw = [sum(M[i][kk] * ax[kk] for kk in range(3)) for i in range(3)]
        o = [M[i][3] * 1000 for i in range(3)]
        # links downstream of this joint
        down = set()
        def collect(l):
            down.add(l)
            for n2, j2 in J.items():
                if j2.find('parent').get('link') == l: collect(j2.find('child').get('link'))
        collect(child)
        tau = [0, 0, 0]
        for name, m, p in parts:
            if not (name in down or name == side + ' payload'): continue
            r = [(p[i] - o[i]) / 1000 for i in range(3)]
            F = [0, 0, -m / 1000 * G]
            t = [r[1] * F[2] - r[2] * F[1], r[2] * F[0] - r[0] * F[2], r[0] * F[1] - r[1] * F[0]]
            tau = [tau[i] + t[i] for i in range(3)]
        out[k] = abs(sum(tau[i] * axw[i] for i in range(3)))
    return out

POSES = {
    'rest':  {'j1': -1.2217, 'j2': 0, 'j3': 0, 'j4': 0, 'j5': 0, 'j6': 0, 'j7': 0},
    'reach': {'j1': -1.1417, 'j2': 0.78, 'j3': -0.47, 'j4': -0.47, 'j5': -0.02, 'j6': 0.18, 'j7': -0.13},
    'up':    {'j1': -1.2217, 'j2': -0.11, 'j3': -0.72, 'j4': -0.5, 'j5': 0.46, 'j6': -0.39, 'j7': -0.11},
    'low':   {'j1': -1.1317, 'j2': 0.62, 'j3': 0.37, 'j4': -0.12, 'j5': 0.4, 'j6': 0.13, 'j7': -0.28},
    'meet':  {'j1': -1.5317, 'j2': -0.42, 'j3': 0.71, 'j4': 0.12, 'j5': -0.34, 'j6': -0.85, 'j7': -0.21},
    'side':  {'j1': 0.3283, 'j2': 0.78, 'j3': -0.47, 'j4': -0.47, 'j5': 0, 'j6': 0.18, 'j7': 0},
}
MIRROR = {'j1': -1, 'j2': 1, 'j3': 1, 'j4': 1, 'j5': -1, 'j6': 1, 'j7': -1}

def qmap(p, only=None):
    q = {}
    for k, v in p.items():
        if only in (None, 'L'): q['L_' + k] = v
        if only in (None, 'R'): q['R_' + k] = v * MIRROR[k]
    return q

def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    urdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'gerdoo.urdf')
    J, links = load_urdf(urdf)
    body = body_parts()
    Mb, cb = cog(body)
    res = {'body_mass_g': round(Mb), 'body_cog_mm': [round(v, 1) for v in cb], 'poses': {}}
    print('body (no arm links) %.0f g, CoG X %.1f Y %.1f Z %.1f mm' % (Mb, *cb))
    for pname, p in POSES.items():
        for payload in (0, 250):
            q = qmap(p) if pname != 'side' else {**qmap(POSES['rest'], 'R'), **qmap(p, 'L')}
            arms, _ = arm_parts(J, links, q, payload if pname != 'side' else 0)
            if pname == 'side' and payload:
                arms, _ = arm_parts(J, links, q, 0)
                tipL = [a for a in arm_parts(J, links, q, payload)[0] if a[0] == 'L payload']
                arms += tipL
            M, c = cog(body + arms)
            m = edge_margin((c[0], c[1]))
            lim = {'brake (tip forward)': accel_limit(c, (1, 0)), 'accelerate (tip back)': accel_limit(c, (-1, 0)),
                   'turn left (tip right)': accel_limit(c, (0, -1)), 'turn right (tip left)': accel_limit(c, (0, 1))}
            tq = {s: arm_torques(J, links, q, s, payload) for s in ('L', 'R')}
            key = '%s%s' % (pname, '+%dg' % payload if payload else '')
            res['poses'][key] = {'mass_g': round(M), 'cog_mm': [round(v, 1) for v in c], 'min_edge_margin_mm': round(min(m), 1),
                                 'a_limit_g': {k: round(v, 2) for k, v in lim.items()},
                                 'servo_torque_Nm': {s: {k: round(v, 2) for k, v in t.items()} for s, t in tq.items()}}
            print('%-12s M %5.0f g  CoG (%5.1f, %5.1f, %5.1f)  margin %5.1f mm  brake %.2fg  accel %.2fg  turn %.2f/%.2fg  L J2 %.2f J3 %.2f N m' % (
                key, M, *c, min(m), lim['brake (tip forward)'], lim['accelerate (tip back)'], lim['turn left (tip right)'], lim['turn right (tip left)'], tq['L']['j2'], tq['L']['j3']))
    # braking limit with the casters' real contact points
    res['brake_by_caster_state'] = {}
    for pname in ('rest', 'reach', 'low'):
        for payload in (0, 250):
            arms, _ = arm_parts(J, links, qmap(POSES[pname]), payload)
            M_, c = cog(body + arms)
            row = {}
            for st in CASTER_STATES:
                set_casters(st); row[st] = round(accel_limit(c, (1, 0)), 2)
            set_casters('pivots')
            key = '%s%s' % (pname, '+%dg' % payload if payload else '')
            res['brake_by_caster_state'][key] = row
            print('brake limit %-12s pivots %.2fg  after forward %.2fg  after reverse %.2fg' % (key, row['pivots'], row['after forward'], row['after reverse']))
    # drive
    M = res['poses']['rest']['mass_g'] / 1000
    r = 0.03315
    for a, slope in ((0.5, 0), (0.5, 5), (0.3, 10)):
        F = M * (a + G * math.sin(math.radians(slope)) + 0.03 * G * math.cos(math.radians(slope)))
        print('drive: a %.1f m/s2 on %2d deg -> %.1f N total, %.2f N m per wheel (%.1f kg cm)' % (a, slope, F, F * r / 2, F * r / 2 / 0.0981))
    v = 160 / 60 * 2 * math.pi * r
    print('top speed at 160 rpm: %.2f m/s' % v)
    json.dump(res, open(os.path.join(here, 'physics.json'), 'w'), indent=1)

if __name__ == '__main__':
    main()
