"""Voxel check for regions printed in air (no material below within 45 deg). Frame: y up. Usage: floating.py file.stl"""
import sys, math
import numpy as np
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import make_print_3mf as b
from collections import defaultdict
T = np.array(list(b.read_stl(sys.argv[1])), dtype=float)
h = 0.5
x0, x1 = T[:, :, 0].min(), T[:, :, 0].max(); z0, z1 = T[:, :, 2].min(), T[:, :, 2].max(); y0, y1 = T[:, :, 1].min(), T[:, :, 1].max()
nx = int((x1 - x0) / h) + 1; nz = int((z1 - z0) / h) + 1; ny = int((y1 - y0) / h) + 1
vox = np.zeros((nx, nz, ny), dtype=bool)
tx0 = ((T[:, :, 0].min(1) - x0) / h).astype(int); tx1 = ((T[:, :, 0].max(1) - x0) / h).astype(int)
tz0 = ((T[:, :, 2].min(1) - z0) / h).astype(int); tz1 = ((T[:, :, 2].max(1) - z0) / h).astype(int)
bins = defaultdict(list)
for i in range(len(T)):
    for a in range(tx0[i], tx1[i] + 1):
        for c in range(tz0[i], tz1[i] + 1):
            bins[(a, c)].append(i)
for (a, c), idx in bins.items():
    px = x0 + (a + 0.5) * h; pz = z0 + (c + 0.5) * h
    tri = T[idx]; A = tri[:, 0]; B = tri[:, 1]; C = tri[:, 2]
    v0x = C[:, 0] - A[:, 0]; v0z = C[:, 2] - A[:, 2]; v1x = B[:, 0] - A[:, 0]; v1z = B[:, 2] - A[:, 2]; v2x = px - A[:, 0]; v2z = pz - A[:, 2]
    d00 = v0x * v0x + v0z * v0z; d01 = v0x * v1x + v0z * v1z; d11 = v1x * v1x + v1z * v1z; d20 = v2x * v0x + v2z * v0z; d21 = v2x * v1x + v2z * v1z
    den = d00 * d11 - d01 * d01; ok = np.abs(den) > 1e-12
    u = np.where(ok, (d11 * d20 - d01 * d21) / np.where(ok, den, 1), -1); v = np.where(ok, (d00 * d21 - d01 * d20) / np.where(ok, den, 1), -1)
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1)
    if not hit.any(): continue
    ys = np.unique(np.round(np.sort((A[:, 1] + u * (C[:, 1] - A[:, 1]) + v * (B[:, 1] - A[:, 1]))[hit]), 4))
    for k in range(0, len(ys) - 1, 2):
        k0 = int(math.ceil((ys[k] - y0) / h - 0.5)); k1 = int(math.floor((ys[k + 1] - y0) / h - 0.5))
        if k1 >= k0: vox[a, c, k0:k1 + 1] = True
below = np.zeros_like(vox); below[:, :, 1:] = vox[:, :, :-1]
pad = np.pad(below, ((1, 1), (1, 1), (0, 0)))
nb = np.zeros_like(vox)
for da in (0, 1, 2):
    for dc in (0, 1, 2):
        nb |= pad[da:da + nx, dc:dc + nz, :]
uns = vox & ~nb; uns[:, :, 0] = False
S_ = set(map(tuple, np.argwhere(uns))); seen = set(); clusters = []
for p in list(S_):
    if p in seen: continue
    stack = [p]; seen.add(p); mem = []
    while stack:
        q = stack.pop(); mem.append(q)
        for d in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]:
            r = (q[0] + d[0], q[1] + d[1], q[2] + d[2])
            if r in S_ and r not in seen: seen.add(r); stack.append(r)
    m = np.array(mem)
    clusters.append((len(mem), x0 + m[:, 0].min() * h, x0 + m[:, 0].max() * h, y0 + m[:, 2].min() * h, y0 + m[:, 2].max() * h, z0 + m[:, 1].min() * h, z0 + m[:, 1].max() * h))
clusters.sort(reverse=True)
for c in clusters[:int(sys.argv[2]) if len(sys.argv) > 2 else 10]:
    print('unsupported %4d cells (%.1f mm2)  x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f' % (c[0], c[0] * h * h, c[1], c[2], c[3], c[4], c[5], c[6]))
