#!/usr/bin/env python3
"""Build a Bambu A1 project with several parts on one plate, from STLs exported out of Fusion.

  python3 make_plate_3mf.py <plate.json> <out.3mf>

plate.json:
  {"name": "...", "process": {overrides}, "objects": [
     {"name": "...", "stl": "path.stl", "map": "x,-z,y", "at": [X, Y],
      "enforcers": [[x0, x1, y0, y1, z0, z1], ...]}          # boxes in the STL's own coordinates
  ]}

- "map" turns the STL's axes into print axes (X, Y, Z up); "x,-z,y" stands a preview-frame part (Y up) upright.
- Each object is centred on its footprint, put on the bed (Z = 0) and placed at "at" (bed mm).
- Settings come from make_print_3mf.project_config(): the user's PolyLite PLA Pro in slot 1 and their
  "Generic PETG @BBL A1 - Support" (black, 240 C) as the support interface in slot 2. PETG interface is the default
  for anything supported (log 033).
"""
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_print_3mf as base  # noqa: E402


def axis_map(spec):
    out = []
    for s in spec.split(','):
        s = s.strip()
        sign = -1.0 if s.startswith('-') else 1.0
        out.append((sign, 'xyz'.index(s[-1])))
    return lambda p: tuple(sign * p[i] for sign, i in out)


def build(spec, out):
    objects = []
    for o in spec['objects']:
        f = axis_map(o.get('map', 'x,-z,y'))
        # "stl" may be a list: overlapping bodies of one part (Bambu unions the parts of an object)
        stls = o['stl'] if isinstance(o['stl'], list) else [o['stl']]
        meshes = [base.indexed([f(p) for p in t] for t in base.read_stl(s)) for s in stls]
        xs = [v[0] for m in meshes for v in m[0]]; ys = [v[1] for m in meshes for v in m[0]]; zs = [v[2] for m in meshes for v in m[0]]
        cx, cy, z0 = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)
        shift = lambda p: (p[0] - cx, p[1] - cy, p[2] - z0)
        parts = [(o['name'] if len(meshes) == 1 else '%s (%s)' % (o['name'], os.path.basename(s)[:-4]), 'normal_part',
                  [shift(v) for v in verts], faces) for s, (verts, faces) in zip(stls, meshes)]
        n_bodies = len(parts)
        faces = [t for m in meshes for t in m[1]]
        for i, e in enumerate(o.get('enforcers', [])):
            c = [f((x, y, z)) for x in e[0:2] for y in e[2:4] for z in e[4:6]]
            c = [shift(p) for p in c]
            bx = [p[0] for p in c]; by = [p[1] for p in c]; bz = [p[2] for p in c]
            v, fc = base.box(min(bx), max(bx), min(by), max(by), max(0.0, min(bz)), max(bz))
            parts.append(('support enforcer %d' % (i + 1), 'support_enforcer', v, fc))
        size = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - z0)
        objects.append((o['name'], o['at'], parts, size))
        print('%-34s %6.1f x %6.1f x %5.1f mm at X %5.1f Y %5.1f, %d triangles, %d enforcers'
              % (o['name'][:34], size[0], size[1], size[2], o['at'][0], o['at'][1], len(faces), len(parts) - n_bodies))
        hx, hy = size[0] / 2, size[1] / 2
        assert 2 <= o['at'][0] - hx and o['at'][0] + hx <= base.BED - 2 and 2 <= o['at'][1] - hy and o['at'][1] + hy <= base.BED - 2, 'off the bed'
        # the outline, not the bounding box: a round plate (2nd floor, R125) can fill the bed and still clear the corner
        assert not any(p[0] + o['at'][0] > 226 and p[1] + o['at'][1] > 224 for part in parts[:n_bodies] for p in part[2]), 'in the A1 head-wrap detection corner'
    model = ['<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
             'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
             ' <metadata name="Application">BambuStudio-02.04.00.70</metadata>\n'
             ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
             ' <metadata name="Title">%s</metadata>\n <resources>\n' % spec['name']]
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>\n<config>\n']
    items, inst = [], []
    oid = 0
    for name, at, parts, size in objects:
        first = oid + 1
        for _, _, v, f in parts:
            oid += 1
            model.append(base.mesh_xml(oid, v, f))
        oid += 1
        comp = oid
        model.append('  <object id="%d" type="model">\n   <components>\n' % comp)
        model += ['    <component objectid="%d"/>\n' % i for i in range(first, comp)]
        model.append('   </components>\n  </object>\n')
        items.append('  <item objectid="%d" transform="1 0 0 0 1 0 0 0 1 %.3f %.3f 0" printable="1"/>\n' % (comp, at[0], at[1]))
        cfg.append('  <object id="%d">\n    <metadata key="name" value="%s"/>\n    <metadata key="extruder" value="1"/>\n' % (comp, name))
        for i, (pname, sub, _, _) in enumerate(parts):
            cfg.append('    <part id="%d" subtype="%s">\n      <metadata key="name" value="%s"/>\n'
                       '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                       '      <metadata key="extruder" value="1"/>\n    </part>\n' % (first + i, sub, pname))
        cfg.append('  </object>\n')
        inst.append('    <model_instance>\n      <metadata key="object_id" value="%d"/>\n'
                    '      <metadata key="instance_id" value="0"/>\n    </model_instance>\n' % comp)
    model.append(' </resources>\n <build>\n')
    model += items
    model.append(' </build>\n</model>\n')
    cfg.append('  <plate>\n    <metadata key="plater_id" value="1"/>\n    <metadata key="plater_name" value="%s"/>\n'
               '    <metadata key="locked" value="false"/>\n    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
               '    <metadata key="filament_maps" value="1 1"/>\n' % spec['name'])
    cfg += inst
    cfg.append('  </plate>\n</config>\n')
    pc = base.project_config()
    for k, v in spec.get('process', {}).items():
        pc[k] = v
    hq = base.resolve('process', '0.16mm High Quality @BBL A1')
    merged = dict(base.PROCESS); merged.update(spec.get('process', {}))
    pc['different_settings_to_system'][0] = ';'.join(sorted(k for k in merged if k != 'name' and k in hq and k in pc and str(hq[k]) != str(merged[k])))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                   ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                   ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n</Types>\n')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                   ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
        z.writestr('3D/3dmodel.model', ''.join(model))
        z.writestr('Metadata/model_settings.config', ''.join(cfg))
        z.writestr('Metadata/project_settings.config', json.dumps(pc, indent=4))
    print('wrote', out, round(os.path.getsize(out) / 1e6, 1), 'MB')


if __name__ == '__main__':
    build(json.load(open(sys.argv[1])), sys.argv[2])
