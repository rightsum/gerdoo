#!/usr/bin/env python3
"""Build a Bambu Studio project for printing gerdoo's 1st layer on a Bambu A1.

  python3 make_print_3mf.py <first_layer.stl> <pods.json> <outdir> [--pla-supports]

- The plate prints deck-top face DOWN (model +Y -> print +Z), centred on the 256 mm bed.
- Four support-enforcer volumes cover the ultrasonic pods: the only overhangs that need support.
- Settings are the user's own A1 project block (TEMPLATE_CONFIG) with these presets, named the way the Bambu Studio
  GUI saves them (preset names that exist on this machine, changes listed in different_settings_to_system):
    machine  Bambu Lab A1 0.4 nozzle
    process  0.16mm High Quality @BBL A1 + structural overrides + PETG interface supports
    filament 1  PolyLite PLA @BBL A1, set for Polymaker PolyLite PLA Pro (black)
    filament 2  the user's "Generic PETG @BBL A1 - Support", for the support interfaces only
- --pla-supports: the same, with all-PLA supports and the stock interface gap.
- Check a file with Bambu Studio's CLI: BambuStudio --slice 0 --outputdir <dir> <file.3mf>, then read result.json.
"""
import json
import os
import struct
import subprocess
import sys
import zipfile

SYS = os.path.expanduser('~/Library/Application Support/BambuStudio/system/BBL')
BAMBU = '/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'
BED = 256.0


def resolve(kind, name):
    out = {}
    while name:
        d = json.load(open(os.path.join(SYS, kind, name + '.json')))
        out = {**d, **out}
        name = d.get('inherits')
    out.pop('inherits', None)
    return out


PROCESS = {
    'name': 'Gerdoo base 0.16 HQ - PLA + PETG interface',
    # walls and shells for a structural plate with heat-set inserts
    'wall_loops': '4', 'wall_generator': 'arachne',
    'top_shell_layers': '6', 'bottom_shell_layers': '5',
    'sparse_infill_density': '25%', 'sparse_infill_pattern': 'gyroid',
    'elefant_foot_compensation': '0.12',
    'seam_position': 'aligned', 'ironing_type': 'no ironing',
    'brim_type': 'no_brim',
    # supports: normal (not tree) and only where enforced. The user switched plates to normal for
    # stability (arm bases log 036, dock sign log 045): trees toppled at the first PETG layer.
    'enable_support': '1', 'support_type': 'normal(manual)', 'support_style': 'default',
    'support_threshold_angle': '50', 'support_on_build_plate_only': '0',
    # PETG on the interfaces, top and bottom: it does not bond to PLA, so no gap is needed
    'support_filament': '0', 'support_interface_filament': '2', 'support_interface_not_for_body': '1',
    # PETG only where the part's surface rests on the support (top); support feet stand on PLA with a normal gap
    'support_interface_top_layers': '2', 'support_interface_bottom_layers': '0',
    'support_top_z_distance': '0', 'support_bottom_z_distance': '0.16',
    'support_interface_spacing': '0', 'support_interface_pattern': 'rectilinear_interlaced',
    'independent_support_layer_height': '0',
    # the plate leaves no room for a prime tower; the A1 purges into its chute
    'enable_prime_tower': '0', 'flush_into_support': '1',
    'curr_bed_type': 'Textured PEI Plate',
}
# Polymaker PolyLite PLA Pro (box: 190-220 C, bed 30-60 C, 30-70 mm/s). Bambu has no PLA Pro profile; its PolyLite PLA
# one is the same maker's tuning (flow 0.95). Bed at the box's 60 rather than Bambu's usual 65 on textured PEI, and the
# flow capped at 12 mm3/s (~165 mm/s at 0.16 x 0.45) so the fast inner moves stay near a standard-speed PLA's comfort.
PLA_PRESET = 'PolyLite PLA @BBL A1'
PLA = {'name': 'PolyLite PLA Pro @BBL A1 (gerdoo)', 'filament_colour': ['#000000'],
       'nozzle_temperature': ['215'], 'nozzle_temperature_initial_layer': ['220'],
       'textured_plate_temp': ['60'], 'textured_plate_temp_initial_layer': ['60'],
       'filament_max_volumetric_speed': ['12']}
# High Speed Matte PETG, black (label: 230-240 C at 50-100 mm/s, bed 70-80 C, spool good to 70 C). Interface runs in that
# slow band, and a cooler PETG bonds less to the PLA, so 240 instead of Generic PETG's 255. The PETG never touches the
# bed (no bottom interface); its textured-plate value only has to agree with the PLA's.
PETG = {'name': 'PETG support interface @BBL A1 (gerdoo)', 'filament_colour': ['#000000'],
        'nozzle_temperature': ['240'], 'nozzle_temperature_initial_layer': ['240'],
        'hot_plate_temp': ['65'], 'hot_plate_temp_initial_layer': ['65'],
        'textured_plate_temp': ['60'], 'textured_plate_temp_initial_layer': ['60'],
        'eng_plate_temp': ['65'], 'eng_plate_temp_initial_layer': ['65'],
        'supertack_plate_temp': ['65'], 'supertack_plate_temp_initial_layer': ['65']}


def write_presets(outdir):
    """User presets in Bambu Studio's own format: differences only, `inherits` a system preset."""
    m = resolve('machine', 'Bambu Lab A1 0.4 nozzle')
    m['from'] = 'system'
    p = {'type': 'process', 'from': 'User', 'inherits': '0.16mm High Quality @BBL A1', 'version': '2.4.0.10'}
    p.update(PROCESS); p['print_settings_id'] = p['name']
    f1 = {'type': 'filament', 'from': 'User', 'inherits': PLA_PRESET, 'version': '2.4.0.10'}
    f1.update(PLA); f1['filament_settings_id'] = [f1['name']]
    f2 = {'type': 'filament', 'from': 'User', 'inherits': 'Generic PETG @BBL A1', 'version': '2.4.0.10'}
    f2.update(PETG); f2['filament_settings_id'] = [f2['name']]
    paths = {}
    for key, d in (('machine', m), ('process', p), ('pla', f1), ('petg', f2)):
        path = os.path.join(outdir, 'preset_%s.json' % key)
        json.dump(d, open(path, 'w'), indent=1)
        paths[key] = path
    return paths


def read_stl(path):
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[80:84])[0]
    for i in range(n):
        off = 84 + i * 50 + 12
        yield [struct.unpack('<3f', b[off + 12 * k:off + 12 * k + 12]) for k in range(3)]


def indexed(tris):
    verts, index, faces = [], {}, []
    for t in tris:
        f = []
        for p in t:
            key = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
            if key not in index:
                index[key] = len(verts); verts.append(key)
            f.append(index[key])
        if len(set(f)) == 3:
            faces.append(f)
    return verts, faces


def box(x0, x1, y0, y1, z0, z1):
    v = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    f = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
         (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return v, f


def mesh_xml(oid, verts, faces):
    out = ['  <object id="%d" type="model">\n   <mesh>\n    <vertices>\n' % oid]
    out += ['     <vertex x="%.4f" y="%.4f" z="%.4f"/>\n' % v for v in verts]
    out.append('    </vertices>\n    <triangles>\n')
    out += ['     <triangle v1="%d" v2="%d" v3="%d"/>\n' % tuple(f) for f in faces]
    out.append('    </triangles>\n   </mesh>\n  </object>\n')
    return ''.join(out)


def build_input_3mf(stl, pods_json, path):
    # print orientation: deck top on the plate (model +Y, the robot's underside, prints upwards), then turned 90 deg
    # about Z so the rear ultrasonic pod (it overhangs the plate edge and needs supports from the bed) sits at the
    # bed's left edge, clear of the A1's purge / calibration line along the front (Y 0..1).
    #   X = -z, Y = -x, Z = y
    tris = ([(-p[2], -p[0], p[1]) for p in t] for t in read_stl(stl))
    verts, faces = indexed(tris)
    zmin = min(v[2] for v in verts)
    verts = [(x, y, z - zmin) for x, y, z in verts]
    pods = json.load(open(pods_json))['clusters_mm']
    big = []
    for c in pods:   # keep the outer cluster of each pod
        if not any(o is not c and o[0] <= c[0] and c[1] <= o[1] and o[4] <= c[4] and c[5] <= o[5] for o in pods):
            big.append(c)
    parts = [('first layer (deck top on the plate)', 'normal_part', verts, faces)]
    for i, c in enumerate(big):
        x0, x1, y0, y1, z0, z1 = c
        v, f = box(-z1 - 2.5, -z0 + 2.5, -x1 - 2.5, -x0 + 2.5, y0 - 1.0 - zmin, y1 + 1.5 - zmin)
        parts.append(('support enforcer: ultrasonic pod %d' % (i + 1), 'support_enforcer', v, f))
    model = ['<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
             'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
             ' <metadata name="Application">BambuStudio-02.04.00.70</metadata>\n'
             ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
             ' <metadata name="Title">gerdoo 1st layer</metadata>\n <resources>\n']
    for i, (_, _, v, f) in enumerate(parts):
        model.append(mesh_xml(i + 1, v, f))
    comp = len(parts) + 1
    model.append('  <object id="%d" type="model">\n   <components>\n' % comp)
    model += ['    <component objectid="%d"/>\n' % (i + 1) for i in range(len(parts))]
    model.append('   </components>\n  </object>\n </resources>\n <build>\n')
    model.append('  <item objectid="%d" transform="1 0 0 0 1 0 0 0 1 %.3f %.3f 0" printable="1"/>\n' % (comp, BED / 2, BED / 2))
    model.append(' </build>\n</model>\n')
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <object id="%d">\n' % comp,
           '    <metadata key="name" value="gerdoo 1st layer"/>\n    <metadata key="extruder" value="1"/>\n']
    for i, (name, sub, v, f) in enumerate(parts):
        cfg.append('    <part id="%d" subtype="%s">\n      <metadata key="name" value="%s"/>\n'
                   '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                   '      <metadata key="extruder" value="1"/>\n    </part>\n' % (i + 1, sub, name))
    cfg.append('  </object>\n  <plate>\n    <metadata key="plater_id" value="1"/>\n    <metadata key="plater_name" value="gerdoo 1st layer"/>\n'
               '    <metadata key="locked" value="false"/>\n    <model_instance>\n      <metadata key="object_id" value="%d"/>\n'
               '      <metadata key="instance_id" value="0"/>\n    </model_instance>\n  </plate>\n</config>\n' % comp)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                   ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                   ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n</Types>\n')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                   ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
        z.writestr('3D/3dmodel.model', ''.join(model))
        z.writestr('Metadata/model_settings.config', ''.join(cfg))
    xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
    print('plate %d triangles, size %.1f x %.1f x %.1f mm; %d enforcers' % (len(faces), max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), len(parts) - 1))


TEMPLATE_CONFIG = os.path.expanduser('~/Documents/3d models/down-panel.3mf')   # the user's own A1 project: a complete,
                                                                               # version-matched settings block


# the user's own Bambu Studio preset: Generic PETG with every plate type at 65 C, the same values as PETG below
PETG_USER_PRESET = 'Generic PETG @BBL A1 - Support'


# supports all PLA: the interface keys go back to the stock 0.16 HQ values (a normal Z gap)
PLA_ONLY_RESET = ('support_interface_filament', 'support_top_z_distance', 'support_bottom_z_distance',
                  'support_interface_spacing', 'support_interface_pattern')


def project_config(pla_only=False):
    """Full project settings: the user's A1 project block with the process and two filaments replaced."""
    with zipfile.ZipFile(TEMPLATE_CONFIG) as z:
        c = json.loads(z.read('Metadata/project_settings.config'))
    n_old = len(c['filament_settings_id'])
    hq = resolve('process', '0.16mm High Quality @BBL A1')
    process = dict(PROCESS)
    if pla_only:
        process.update({k: hq[k] for k in PLA_ONLY_RESET})
    proc = dict(hq); proc.update(process)
    for k, v in proc.items():
        if k in c and k not in ('name', 'inherits', 'from', 'type', 'instantiation', 'setting_id', 'compatible_printers'):
            c[k] = v
    # The Bambu Studio GUI only applies a project's settings when its preset names exist on this machine; an unknown
    # name falls back to the stock preset and drops every change (the CLI applies them regardless). So, like the GUI's
    # own saves: system names plus the changed keys in different_settings_to_system, which open as unsaved changes.
    c['print_settings_id'] = '0.16mm High Quality @BBL A1'
    pla_sys = resolve('filament', PLA_PRESET); pla = dict(pla_sys); pla.update(PLA)
    petg_sys = resolve('filament', 'Generic PETG @BBL A1'); petg = dict(petg_sys); petg.update(PETG)
    fil_keys = [k for k, v in c.items() if isinstance(v, list) and len(v) == n_old and k not in ('wipe_tower_x', 'wipe_tower_y')]
    def one(preset, k, fallback):
        v = preset.get(k)
        if v is None: return fallback
        return v[0] if isinstance(v, list) else v
    for k in fil_keys:
        old = c[k]
        if old == [str(i + 1) for i in range(n_old)]:
            c[k] = ['1', '2']; continue
        c[k] = [one(pla, k, old[0]), one(petg, k, old[-1])]
    c['filament_settings_id'] = [PLA_PRESET, PETG_USER_PRESET]
    c['filament_ids'] = [one(pla, 'filament_id', 'GFL99'), one(petg, 'filament_id', 'GFG99')]
    c['filament_colour'] = [PLA['filament_colour'][0], PETG['filament_colour'][0]]
    c['filament_map'] = ['1', '1']
    c['flush_volumes_matrix'] = ['0', '170', '170', '0']   # support interface: a little PLA in the PETG is harmless
    c['flush_volumes_vector'] = ['140', '140', '140', '140']
    c['inherits_group'] = ['', '', 'Generic PETG @BBL A1', '']
    def diff(sys_preset, over):
        skip = ('name', 'filament_colour')
        return ';'.join(sorted(k for k in over if k not in skip and k in sys_preset and k in c and str(sys_preset[k]) != str(over[k])))
    c['different_settings_to_system'] = [diff(hq, process), diff(pla_sys, PLA), diff(petg_sys, PETG), '']
    # no prime tower: Bambu 2.8's tower (~55 x 55 with ribs) has no room next to a 250 mm plate. The A1 flushes and
    # wipes in its chute on every swap, and the swaps only feed PETG to the support interfaces.
    c['enable_prime_tower'] = '0'
    c['flush_into_infill'] = '1'; c['flush_into_support'] = '1'
    bad = [k for k, v in c.items() if isinstance(v, list) and len(v) == n_old and k in fil_keys]
    assert not bad, bad
    return c


def build_project(stl, pods_json, out, pla_only=False):
    tmp = out + '.parts.3mf'
    build_input_3mf(stl, pods_json, tmp)
    cfg = project_config(pla_only)
    with zipfile.ZipFile(tmp) as zin, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'Metadata/model_settings.config':
                data = data.replace(b'<metadata key="locked" value="false"/>',
                                    b'<metadata key="locked" value="false"/>\n    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
                                    b'    <metadata key="filament_maps" value="1 1"/>')
            z.writestr(item, data)
        z.writestr('Metadata/project_settings.config', json.dumps(cfg, indent=4))
    os.remove(tmp)
    return cfg


def main():
    stl, pods, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    pla_only = '--pla-supports' in sys.argv[4:]
    out = os.path.join(outdir, 'gerdoo_1st_layer_A1_PLA-supports-only.3mf' if pla_only else 'gerdoo_1st_layer_A1.3mf')
    cfg = build_project(stl, pods, out, pla_only)
    print('wrote', out, round(os.path.getsize(out) / 1e6, 1), 'MB')
    for k in ('print_settings_id', 'printer_settings_id', 'filament_settings_id', 'curr_bed_type', 'layer_height', 'wall_loops',
              'wall_generator', 'sparse_infill_density', 'support_type', 'support_style', 'support_interface_filament',
              'support_top_z_distance', 'support_bottom_z_distance', 'enable_prime_tower', 'wipe_tower_x', 'wipe_tower_y',
              'nozzle_temperature', 'textured_plate_temp', 'outer_wall_speed', 'elefant_foot_compensation'):
        print('  %-28s %s' % (k, cfg.get(k)))


if __name__ == '__main__':
    main()
