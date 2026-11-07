#!/usr/bin/env python3
"""Export one STL per part from a Bambu Studio plate (.3mf), in its print orientation.

  python3 export_print_stls.py <plate.3mf> <outdir> [--skip NAME_SUBSTRING ...]

- Each object on the plate becomes one binary STL, oriented as it sits on the plate (so it can be
  printed as-is on any printer). Its footprint is centred on X/Y = 0 and it rests on Z = 0.
- Only real geometry is kept: support enforcers/blockers and modifier volumes are dropped.
- File names come from the object's name, up to its first " (" ("front cover v12 (standing...)"
  -> front-cover-v12.stl). Identical parts (separator #1..#4) are written once; the printed
  manifest gives the count.
- Prints one line per STL: file, count, triangles, size in mm (x, y, z).
"""
import argparse
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

NS = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
P_PATH = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path'


def parse_transform(text):
    """3MF transform 'm00 m01 m02 m10 m11 m12 m20 m21 m22 m30 m31 m32' -> 4x4 (row-vector convention)."""
    m = np.eye(4)
    if text:
        v = [float(x) for x in text.split()]
        m[:3, :3] = np.array(v[:9]).reshape(3, 3)
        m[3, :3] = v[9:12]
    return m


def load_models(z):
    """Every .model file in the package -> {path: {object id: element}}."""
    out = {}
    for name in z.namelist():
        if name.endswith('.model'):
            root = ET.fromstring(z.read(name))
            out['/' + name] = {o.get('id'): o for o in root.iter('{%s}object' % NS['m'])}
    return out


def part_subtypes(z):
    """model_settings.config: part id -> subtype, object id -> display name."""
    sub, names = {}, {}
    try:
        cfg = ET.fromstring(z.read('Metadata/model_settings.config'))
    except KeyError:
        return sub, names
    for obj in cfg.iter('object'):
        for md in obj.findall('metadata'):
            if md.get('key') == 'name':
                names[obj.get('id')] = md.get('value')
        for part in obj.findall('part'):
            sub[part.get('id')] = part.get('subtype', 'normal_part')
    return sub, names


def collect(models, path, oid, xf, sub, out):
    """Append the transformed triangles of object `oid` (and its components) to `out`."""
    obj = models[path][oid]
    mesh = obj.find('m:mesh', NS)
    if mesh is not None:
        if sub.get(oid, 'normal_part') != 'normal_part':
            return
        verts = np.array([[float(v.get(a)) for a in 'xyz'] for v in mesh.find('m:vertices', NS)])
        tris = np.array([[int(t.get(k)) for k in ('v1', 'v2', 'v3')] for t in mesh.find('m:triangles', NS)])
        hv = np.hstack([verts, np.ones((len(verts), 1))]) @ xf
        out.append(hv[:, :3][tris])
        return
    comps = obj.find('m:components', NS)
    for c in (comps if comps is not None else []):
        cpath = c.get(P_PATH, path)
        if sub.get(c.get('objectid'), 'normal_part') != 'normal_part':
            continue
        collect(models, cpath, c.get('objectid'), parse_transform(c.get('transform')) @ xf, sub, out)


def write_stl(path, tris, header):
    tris = tris.astype(np.float32)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    rec = np.zeros(len(tris), dtype=[('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
    rec['n'], rec['v'] = n, tris
    with open(path, 'wb') as f:
        f.write(header.encode('ascii', 'replace')[:80].ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        f.write(rec.tobytes())


def slug(name):
    base = name.split(' (')[0]
    base = re.sub(r'\s*#\d+$', '', base)          # "separator hex 77 #3" -> "separator hex 77"
    base = re.sub(r'\.stl$', '', base, flags=re.I)
    return re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plate')
    ap.add_argument('outdir')
    ap.add_argument('--skip', nargs='*', default=[], help='drop objects whose name contains any of these')
    a = ap.parse_args()

    z = zipfile.ZipFile(a.plate)
    models = load_models(z)
    sub, names = part_subtypes(z)
    root = ET.fromstring(z.read('3D/3dmodel.model'))
    os.makedirs(a.outdir, exist_ok=True)

    seen = {}   # geometry hash -> [file, count]
    for item in root.find('m:build', NS):
        oid = item.get('objectid')
        name = names.get(oid, f'object {oid}')
        if any(s.lower() in name.lower() for s in a.skip):
            print(f'  skipped: {name}', file=sys.stderr)
            continue
        parts = []
        collect(models, item.get(P_PATH, '/3D/3dmodel.model'), oid, parse_transform(item.get('transform')), sub, parts)
        if not parts:
            continue
        tris = np.concatenate(parts)
        lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
        tris = tris - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
        # same part turned on the plate (a hex separator at another angle) counts as identical:
        # compare rotation-free numbers, not coordinates
        cr = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        area = 0.5 * np.linalg.norm(cr, axis=1).sum()
        vol = np.einsum('ij,ij->i', tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum() / 6
        key = (len(tris), round(area, 1), round(vol, 1), round(float(hi[2] - lo[2]), 2))
        if key in seen:
            seen[key][1] += 1
            continue
        fname = slug(name) + '.stl'
        i = 2
        while any(v[0] == fname for v in seen.values()):
            fname = f'{slug(name)}-{i}.stl'
            i += 1
        write_stl(os.path.join(a.outdir, fname), tris, f'gerdoo: {name}')
        seen[key] = [fname, 1, len(tris), hi - lo]

    for fname, count, ntri, size in seen.values():
        # "coil pad 01" x12 -> coil-pad.stl: the index only named the first copy
        if count > 1 and re.search(r'-0?1\.stl$', fname):
            new = re.sub(r'-0?1\.stl$', '.stl', fname)
            os.replace(os.path.join(a.outdir, fname), os.path.join(a.outdir, new))
            fname = new
        print(f'{fname}\tx{count}\t{ntri} tris\t{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm')


if __name__ == '__main__':
    main()
