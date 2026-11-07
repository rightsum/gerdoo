"""Place the movable objects of a plate spec around the fixed ones with a minimum clearance (densified outlines)."""
import sys, math, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import make_print_3mf as b, make_plate_3mf as p
spec_path, resolved_path, lim = sys.argv[1], sys.argv[2], float(sys.argv[3])
movable = sys.argv[4].split('|')
spec = json.load(open(resolved_path))
objs = {o['name']: o for o in spec['objects']}
cache = {}
def base_pts(o):
    if o['name'] in cache: return cache[o['name']]
    f = p.axis_map(o['map'])
    T = [[f(q) for q in t] for t in b.read_stl(o['stl'])]
    V = [q for t in T for q in t]
    cx = (min(v[0] for v in V) + max(v[0] for v in V)) / 2; cy = (min(v[1] for v in V) + max(v[1] for v in V)) / 2
    pts = set()
    for t in T:
        for i in range(3):
            a, c = t[i], t[(i + 1) % 3]
            n = max(1, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.8))
            for k in range(n + 1):
                pts.add((round(a[0] + (c[0] - a[0]) * k / n - cx, 1), round(a[1] + (c[1] - a[1]) * k / n - cy, 1)))
    cache[o['name']] = list(pts); return cache[o['name']]
def place(o, at):
    return [(x + at[0], y + at[1]) for x, y in base_pts(o)]
def grid(pts):
    g = {}
    for x, y in pts: g.setdefault((int(x // 3), int(y // 3)), []).append((x, y))
    return g
def mind(a, g, lim):
    best = 1e9
    for x, y in a[::2]:
        k = (int(x // 3), int(y // 3))
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                for q in g.get((k[0] + dx, k[1] + dy), []):
                    d = math.hypot(x - q[0], y - q[1])
                    if d < best:
                        best = d
                        if best < lim: return best
    return best
def inbed(a):
    return all(2 <= x <= 254 and 2 <= y <= 254 and not (x > 226 and y > 224) for x, y in a)
fixed = [n for n in objs if n not in movable]
G = grid([q for n in fixed for q in place(objs[n], objs[n]['at'])])
cands = {}
for n in movable:
    cands[n] = []
    for X in range(4, 254, 3):
        for Y in range(4, 254, 3):
            a = place(objs[n], (X, Y))
            if inbed(a) and mind(a, G, lim) >= lim:
                cands[n].append(((X, Y), a))
    print(n, len(cands[n]), 'spots')
def solve(i, placed_pts):
    if i == len(movable): return []
    g = grid(placed_pts)
    for at, a in cands[movable[i]]:
        if not placed_pts or mind(a, g, lim) >= lim:
            r = solve(i + 1, placed_pts + a)
            if r is not None: return [at] + r
    return None
sol = solve(0, [])
print('solution', sol)
if sol:
    s2 = json.load(open(spec_path))
    for o in s2['objects']:
        if o['name'] in movable: o['at'] = list(sol[movable.index(o['name'])])
    json.dump(s2, open(spec_path, 'w'), indent=1)
