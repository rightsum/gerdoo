#!/usr/bin/env python3
"""Build the gerdoo web simulator's meshes and URDF.

Inputs
  raw/            STL files exported from the Fusion preview (`gerdoo-assembly-preview`),
                  one per body, in each body's *local* component coordinates (mm), plus
                  raw/manifest.json with the body's world matrix and group.
  elrobot/        ElRobot follower URDF + its STL meshes (norma-core).

Outputs (next to this script's parent)
  meshes/gerdoo/<group>.stl   one binary STL per group, in its URDF link frame (mm)
  meshes/elrobot/*.stl        ElRobot meshes, copied
  gerdoo.urdf                 the whole robot

Frames
  Fusion preview: mm, Y up, front = +Z, +X = robot's LEFT, deck top at y = 0.
  URDF / sim:     m,  Z up, X forward, Y left, Z = 0 on the ground under the wheels.
  sim(p) = (p.z, p.x, p.y + GROUND)  with GROUND = 66.7 mm (wheel bottom at y = -66.7).

Usage
  python3 build_assets.py <raw_dir> <elrobot_dir>
"""
import json
import math
import os
import shutil
import struct
import sys
import xml.etree.ElementTree as ET

GROUND = 66.7  # mm, wheel bottom below the deck top in the preview

# Joint frames, in sim mm (see log 031 for where each number comes from)
WHEEL_Y, WHEEL_Z = 145.65, 33.15          # axle at preview (+-145.65, -33.55, 0); r 33.15
# Neck v1 (log 035): two STS3215s. Pan axis at preview (0, *, 95), horn top y 209.2; tilt axis along
# preview x at (y 236, z 94.5), 20 mm behind the screen face and 26 mm below its centre.
NECK_PAN = (95.0, 0.0, 217.7 + GROUND)      # pan horn top, servo lifted 8.5 mm for its bottom cable sockets
NECK_TILT = (94.5, 0.0, 236.0 + GROUND)
LIDAR = (0.0, 0.0, 319.0 + GROUND)        # C1 base on lidar-holder-v2 (raised 45 mm), preview y 319

# ElRobot base_link -> preview, derived from the preview's STEP placement:
#   preview = (-u.x - 145.68, u.z + 37.6, u.y - 42.49) for the arm at preview x = -145.68
# so in sim: X = u.y - 42.49, Y = -u.x -/+ 145.68, Z = u.z + 37.6 + GROUND  -> rpy (0, 0, -pi/2)
ARM_X, ARM_Y, ARM_Z = -42.49, 145.68, 37.6 + GROUND
# Arm mounts turned 70 deg outward about J1 (log 032): J1 = 0 points 70 deg out, the arms face
# forward at J1 = -70 deg (left) / +70 deg (right). J1 sits 42.49 mm along the arm frame's +Y.
MOUNT_OUT = math.radians(70)
J1_IN_ARM = 42.49

# 1" soft-rubber swivel casters (inventory), on the deck's caster blocks at preview z +-90.
# Block face is 30.2 mm below the deck top, i.e. 36.5 mm above the ground. The listing's casters
# are 37.8 mm tall (log 029), so they would stand 1.3 mm proud of the drive tyres; the tyre size is
# estimated, so the sim fits the caster to the 36.5 mm gap and the log records the mismatch.
CASTER_X = 90.0
CASTER_TOP = -30.2 + GROUND       # 36.5 mm
CASTER_WHEEL_R, CASTER_WHEEL_W = 12.5, 10.0
CASTER_TRAIL = 10.0               # wheel axle behind the swivel axis (typical for 1" casters; measure)

# Printed parts are all black PLA (the user's choice, 2026-10-17); bought parts keep their own colours.
PLA = '0.10 0.10 0.11 1'
SERVO = '0.04 0.04 0.05 1'
STATIC_GROUPS = {
    # group: (rgba, collides with the arms)
    'deck':        (PLA, True),
    'floors':      (PLA, True),
    'posts':       ('0.69 0.55 0.34 1', True),
    'cover_front': (PLA, True),
    'cover_back':  (PLA, True),
    'electronics': ('0.18 0.42 0.29 1', True),
    'sensors':     ('0.16 0.35 0.63 1', True),
    'brain':       ('0.23 0.29 0.35 1', True),
    'armbase':     (PLA, False),  # the arms sit on it
    'drive':       ('0.60 0.62 0.65 1', True),
    'top':         (PLA, True),
    'neck_static': (PLA, True),
    'antennas':    ('0.10 0.10 0.11 1', True),
}
MOVING = {
    # group: (link, origin in sim mm, rgba)
    'wheel_left':  ('wheel_left', (0.0, WHEEL_Y, WHEEL_Z), '0.07 0.07 0.07 1'),
    'wheel_right': ('wheel_right', (0.0, -WHEEL_Y, WHEEL_Z), '0.07 0.07 0.07 1'),
    'neck_pan':    ('neck_pan', NECK_PAN, PLA),
    'neck_tilt':   ('neck_tilt', NECK_TILT, '0.06 0.06 0.07 1'),
    'lidar':       ('lidar', LIDAR, '0.11 0.11 0.12 1'),
}


def read_stl(path):
    b = open(path, 'rb').read()
    if b[:5] == b'solid' and b'facet' in b[:400]:
        tris, cur = [], []
        for line in b.decode('ascii', 'ignore').splitlines():
            line = line.strip()
            if line.startswith('vertex'):
                cur.append(tuple(float(v) for v in line.split()[1:4]))
                if len(cur) == 3:
                    tris.append(cur)
                    cur = []
        return tris
    n = struct.unpack('<I', b[80:84])[0]
    tris = []
    for i in range(n):
        off = 84 + i * 50 + 12
        tris.append([struct.unpack('<3f', b[off + 12 * k:off + 12 * k + 12]) for k in range(3)])
    return tris


def write_stl(path, tris):
    with open(path, 'wb') as f:
        f.write(b'gerdoo sim'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for a, b_, c in tris:
            ux, uy, uz = b_[0] - a[0], b_[1] - a[1], b_[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            f.write(struct.pack('<3f', nx / L, ny / L, nz / L))
            for p in (a, b_, c):
                f.write(struct.pack('<3f', *p))
            f.write(b'\0\0')


def to_sim(m, p):
    x = m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2] + m[0][3]
    y = m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2] + m[1][3]
    z = m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + m[2][3]
    return (z, x, y + GROUND)


def build_meshes(raw, out):
    os.makedirs(out, exist_ok=True)
    manifest = json.load(open(os.path.join(raw, 'manifest.json')))
    groups = {}
    for item in manifest:
        m = item['matrix_mm']
        for t in read_stl(os.path.join(raw, item['file'])):
            groups.setdefault(item['group'], []).append([to_sim(m, p) for p in t])
    stats = {}
    for g, tris in groups.items():
        origin = MOVING[g][1] if g in MOVING else (0.0, 0.0, 0.0)
        tris = [[(p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]) for p in t] for t in tris]
        write_stl(os.path.join(out, g + '.stl'), tris)
        xs = [p[i] for t in tris for p in t for i in range(3)]
        stats[g] = len(tris)
    return stats


def mm(v):
    return ' '.join('%.6g' % (c / 1000.0) for c in v)


def arm_xml(robot, el, prefix, side_sign, ids):
    """Copy ElRobot's links and joints under `prefix`, attached to base_link."""
    nice = {'rev_motor_0%d' % i: 'j%d' % i for i in range(1, 8)}
    nice['rev_motor_08'] = 'gripper'
    nice['rev_motor_08_1'] = 'jaw_a'
    nice['rev_motor_08_2'] = 'jaw_b'
    for link in el.findall('link'):
        new = ET.SubElement(robot, 'link', name=prefix + link.get('name'))
        if link.get('name') == 'base_link':
            continue  # ElRobot's table-clamp base is replaced by gerdoo's own arm base
        vis = link.find('visual')
        if vis is None:
            continue
        v = ET.SubElement(new, 'visual', name=prefix + link.get('name'))
        o = vis.find('origin')
        ET.SubElement(v, 'origin', xyz=o.get('xyz'), rpy=o.get('rpy'))
        g = ET.SubElement(v, 'geometry')
        mesh = vis.find('geometry/mesh')
        ET.SubElement(g, 'mesh', filename='meshes/elrobot/' + os.path.basename(mesh.get('filename')),
                      scale=mesh.get('scale'))
        black = 'ST3215' in link.get('name')
        ET.SubElement(ET.SubElement(v, 'material', name='servo' if black else 'printed'),
                      'color', rgba=SERVO if black else PLA)
    for j in el.findall('joint'):
        name = nice.get(j.get('name'), j.get('name').replace(' ', '_'))
        nj = ET.SubElement(robot, 'joint', name=prefix + name, type=j.get('type'))
        for tag in ('origin', 'axis', 'limit'):
            e = j.find(tag)
            if e is not None:
                ET.SubElement(nj, tag, **e.attrib)
        ET.SubElement(nj, 'parent', link=prefix + j.find('parent').get('link'))
        ET.SubElement(nj, 'child', link=prefix + j.find('child').get('link'))
        mim = j.find('mimic')
        if mim is not None:
            ET.SubElement(nj, 'mimic', joint=prefix + nice.get(mim.get('joint'), mim.get('joint')),
                          multiplier=mim.get('multiplier'), offset=mim.get('offset'))
    mount = ET.SubElement(robot, 'joint', name=prefix + 'mount', type='fixed')
    psi = -math.pi / 2 + side_sign * MOUNT_OUT        # yaw of the arm frame; its +Y is the arm's J1 = 0 direction
    tx = J1_IN_ARM * math.sin(psi)                    # keep J1 on its axis: origin = J1 - Rz(psi) (0, a)
    ty = side_sign * ARM_Y - J1_IN_ARM * math.cos(psi)
    ET.SubElement(mount, 'origin', xyz=mm((tx, ty, ARM_Z)), rpy='0 0 %.6f' % psi)
    ET.SubElement(mount, 'parent', link='base_link')
    ET.SubElement(mount, 'child', link=prefix + 'base_link')
    robot.append(ET.Comment(' %s servo IDs %s ' % (prefix, ids)))


def prim(link, name, geom, xyz, rpy_, rgba):
    v = ET.SubElement(link, 'visual', name=name)
    ET.SubElement(v, 'origin', xyz=mm(xyz), rpy=rpy_)
    g = ET.SubElement(v, 'geometry')
    kind, dims = geom
    if kind == 'box':
        ET.SubElement(g, 'box', size=mm(dims))
    else:
        ET.SubElement(g, 'cylinder', radius='%.6g' % (dims[0] / 1000), length='%.6g' % (dims[1] / 1000))
    ET.SubElement(ET.SubElement(v, 'material', name='m_' + name), 'color', rgba=rgba)


def caster_xml(robot, name, x):
    """Swivel (continuous about Z at the block face) and wheel (continuous about its axle)."""
    steel, rubber, hub = '0.74 0.75 0.77 1', '0.13 0.13 0.14 1', '0.82 0.83 0.85 1'
    axle_z = CASTER_WHEEL_R - CASTER_TOP          # axle height relative to the swivel frame (negative)
    sw = ET.SubElement(robot, 'link', name=name + '_swivel')
    prim(sw, name + '_plate', ('box', (30, 30, 2)), (0, 0, -1), '0 0 0', steel)
    prim(sw, name + '_bearing', ('cyl', (11, 4)), (0, 0, -4), '0 0 0', steel)
    fork_h = -6 - axle_z
    for side in (1, -1):
        prim(sw, name + '_fork_%s' % ('l' if side > 0 else 'r'), ('box', (CASTER_TRAIL + 8, 1.6, fork_h)),
             (-CASTER_TRAIL / 2, side * (CASTER_WHEEL_W / 2 + 1.4), -6 - fork_h / 2), '0 0 0', steel)
    j = ET.SubElement(robot, 'joint', name=name + '_swivel', type='continuous')
    ET.SubElement(j, 'origin', xyz=mm((x, 0, CASTER_TOP)), rpy='0 0 0')
    ET.SubElement(j, 'axis', xyz='0 0 1')
    ET.SubElement(j, 'parent', link='base_link'); ET.SubElement(j, 'child', link=name + '_swivel')
    wl = ET.SubElement(robot, 'link', name=name + '_wheel')
    prim(wl, name + '_tyre', ('cyl', (CASTER_WHEEL_R, CASTER_WHEEL_W)), (0, 0, 0), '%.6f 0 0' % (math.pi / 2), rubber)
    prim(wl, name + '_hub', ('cyl', (5, CASTER_WHEEL_W + 1.2)), (0, 0, 0), '%.6f 0 0' % (math.pi / 2), hub)
    prim(wl, name + '_spoke', ('box', (CASTER_WHEEL_R * 1.5, CASTER_WHEEL_W + 0.4, 2.2)), (0, 0, 0), '0 0 0', hub)
    j = ET.SubElement(robot, 'joint', name=name + '_wheel', type='continuous')
    ET.SubElement(j, 'origin', xyz=mm((-CASTER_TRAIL, 0, axle_z)), rpy='0 0 0')
    ET.SubElement(j, 'axis', xyz='0 1 0')
    ET.SubElement(j, 'parent', link=name + '_swivel'); ET.SubElement(j, 'child', link=name + '_wheel')


def build_urdf(el_urdf, out_path):
    el = ET.parse(el_urdf).getroot()
    robot = ET.Element('robot', name='gerdoo')
    robot.append(ET.Comment(' Generated by sim/web/tools/build_assets.py from the Fusion preview. Z up, X forward. '))
    base = ET.SubElement(robot, 'link', name='base_link')
    for g, (rgba, _) in STATIC_GROUPS.items():
        v = ET.SubElement(base, 'visual', name=g)
        ET.SubElement(v, 'origin', xyz='0 0 0', rpy='0 0 0')
        ET.SubElement(ET.SubElement(v, 'geometry'), 'mesh', filename='meshes/gerdoo/%s.stl' % g, scale='0.001 0.001 0.001')
        ET.SubElement(ET.SubElement(v, 'material', name='m_' + g), 'color', rgba=rgba)
    parents = {'wheel_left': 'base_link', 'wheel_right': 'base_link', 'neck_pan': 'base_link',
               'neck_tilt': 'neck_pan', 'lidar': 'base_link'}
    joints = {
        'wheel_left':  ('continuous', '0 1 0', None),
        'wheel_right': ('continuous', '0 1 0', None),
        'neck_pan':    ('revolute', '0 0 1', (-1.5708, 1.5708)),
        'neck_tilt':   ('revolute', '0 -1 0', (-0.2618, 0.5236)),   # 15 deg down .. 30 deg up
        'lidar':       ('continuous', '0 0 1', None),
    }
    for g, (link, origin, rgba) in MOVING.items():
        l = ET.SubElement(robot, 'link', name=link)
        v = ET.SubElement(l, 'visual', name=g)
        ET.SubElement(v, 'origin', xyz='0 0 0', rpy='0 0 0')
        ET.SubElement(ET.SubElement(v, 'geometry'), 'mesh', filename='meshes/gerdoo/%s.stl' % g, scale='0.001 0.001 0.001')
        ET.SubElement(ET.SubElement(v, 'material', name='m_' + g), 'color', rgba=rgba)
        typ, axis, lim = joints[g]
        parent = parents[g]
        po = MOVING[parent][1] if parent in MOVING else (0, 0, 0)
        j = ET.SubElement(robot, 'joint', name=g, type=typ)
        ET.SubElement(j, 'origin', xyz=mm((origin[0] - po[0], origin[1] - po[1], origin[2] - po[2])), rpy='0 0 0')
        ET.SubElement(j, 'axis', xyz=axis)
        ET.SubElement(j, 'parent', link=parent)
        ET.SubElement(j, 'child', link=link)
        if lim:
            ET.SubElement(j, 'limit', lower=str(lim[0]), upper=str(lim[1]), effort='1', velocity='5')
    for name, x in (('caster_front', CASTER_X), ('caster_back', -CASTER_X)):
        caster_xml(robot, name, x)
    # Firmware: left arm IDs 1-8, right arm IDs 11-18 (log 028). Robot's left = sim +Y.
    arm_xml(robot, el, 'L_', +1, '1-8')
    arm_xml(robot, el, 'R_', -1, '11-18')
    ET.indent(robot, '  ')
    ET.ElementTree(robot).write(out_path, xml_declaration=True, encoding='utf-8')


def main():
    raw, eldir = sys.argv[1], sys.argv[2]
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stats = build_meshes(raw, os.path.join(here, 'meshes', 'gerdoo'))
    edst = os.path.join(here, 'meshes', 'elrobot')
    os.makedirs(edst, exist_ok=True)
    for f in os.listdir(os.path.join(eldir, 'assets')):
        if f.endswith('.stl'):
            shutil.copy(os.path.join(eldir, 'assets', f), edst)
    build_urdf(os.path.join(eldir, 'elrobot_follower.urdf'), os.path.join(here, 'gerdoo.urdf'))
    for g, n in sorted(stats.items()):
        print('%-12s %7d triangles' % (g, n))


if __name__ == '__main__':
    main()
