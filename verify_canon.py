"""Randomised verification of similarity/canon.py.

Three properties, in the order they matter:

  losslessness  union(canonicalize(P)) == union(P)      <- soundness rests on this
  canonicality  same region  => identical cell list      <- what fixes the L-shape
  injectivity   different region => different cell list  <- never observed to fail

Run from the repo root:  python verify_canon.py
"""
import math
import random
import sys

sys.path.insert(0, ".")
from parse_graph import Interval, Path            # noqa: E402
from similarity.canon import canonicalize, cell_key  # noqa: E402

N = 4
LATTICE = [i * 0.5 for i in range(0, 2 * N + 1)]   # half-integers: a point box
                                                   # [5,5] is distinguishable
                                                   # from an interval


def _paths_2d(boxes):
    return [Path({0: {"x": [Interval(x0, x1)], "y": [Interval(y0, y1)]}})
            for (x0, x1, y0, y1) in boxes]


def _points_2d(boxes):
    return frozenset((a, b) for a in LATTICE for b in LATTICE
                     if any(x0 <= a <= x1 and y0 <= b <= y1 for (x0, x1, y0, y1) in boxes))


def _canon_boxes_2d(boxes):
    out = []
    for cell in canonicalize(_paths_2d(boxes)):
        x = cell.timeline[0]["x"][0]
        y = cell.timeline[0]["y"][0]
        out.append((x.l, x.r, y.l, y.r))
    return out


def _random_2d(degenerate_probability):
    boxes = []
    for _ in range(random.randint(1, 4)):
        x0 = random.randint(0, N - 1)
        x1 = x0 if random.random() < degenerate_probability else random.randint(x0 + 1, N)
        y0 = random.randint(0, N - 1)
        y1 = y0 if random.random() < degenerate_probability else random.randint(y0 + 1, N)
        boxes.append((x0, x1, y0, y1))
    return boxes


def check_losslessness(trials=15000):
    print("losslessness  (union of canonical cells == original region)")
    for label, probability in (("no == atoms", 0.0), ("== at 45%", 0.45), ("== at 80%", 0.8)):
        random.seed(13)
        over = under = 0
        for _ in range(trials):
            boxes = _random_2d(probability)
            got, want = _points_2d(_canon_boxes_2d(boxes)), _points_2d(boxes)
            over += bool(got - want)
            under += bool(want - got)
        status = "ok" if over == under == 0 else "FAIL"
        print(f"  {label:12}  over-covers {over:5}  under-covers {under:5}  /{trials}   {status}")


def check_canonicality(trials=15000, degenerate_probability=0.45):
    print("canonicality  (same region => identical cell list)  and  injectivity")
    for label, probability in (("no == atoms", 0.0), ("== atoms", degenerate_probability)):
        random.seed(5)
        by_region = {}
        for _ in range(trials):
            boxes = _random_2d(probability)
            forms = by_region.setdefault(_points_2d(boxes), set())
            forms.add(frozenset(cell_key(c) for c in canonicalize(_paths_2d(boxes))))
        ambiguous = sum(1 for forms in by_region.values() if len(forms) > 1)
        seen, collisions = {}, 0
        for region, forms in by_region.items():
            form = next(iter(forms))
            if seen.get(form, region) != region:
                collisions += 1
            seen[form] = region
        status = "ok" if ambiguous == collisions == 0 else "FAIL"
        print(f"  {label:12}  regions {len(by_region):6}  >1 form {ambiguous:5}"
              f"  collisions {collisions:5}   {status}")


def check_3d(trials=12000):
    print("cross-axis independence  (three axes over two instants)")

    def paths(boxes):
        return [Path({0: {"x": [Interval(a0, a1)], "y": [Interval(b0, b1)]},
                      1: {"x": [Interval(c0, c1)], "y": [Interval(-math.inf, math.inf)]}})
                for (a0, a1, b0, b1, c0, c1) in boxes]

    def points(boxes):
        return frozenset((i, j, k)
                         for i in range(N) for j in range(N) for k in range(N)
                         if any(a0 <= i < a1 and b0 <= j < b1 and c0 <= k < c1
                                for (a0, a1, b0, b1, c0, c1) in boxes))

    def canon_points(boxes):
        out = []
        for cell in canonicalize(paths(boxes)):
            a, b = cell.timeline[0]["x"][0], cell.timeline[0]["y"][0]
            d = cell.timeline[1]["x"][0]
            out.append((a.l, a.r, b.l, b.r, d.l, d.r))
        return points(out)

    def random_boxes():
        out = []
        for _ in range(random.randint(1, 4)):
            values = []
            for _ in range(3):
                lo = random.randint(0, N - 1)
                values += [lo, random.randint(lo + 1, N)]
            out.append(tuple(values))
        return out

    random.seed(11)
    lossy, by_region = 0, {}
    for _ in range(trials):
        boxes = random_boxes()
        if canon_points(boxes) != points(boxes):
            lossy += 1
        by_region.setdefault(points(boxes), set()).add(
            frozenset(cell_key(c) for c in canonicalize(paths(boxes))))
    ambiguous = sum(1 for forms in by_region.values() if len(forms) > 1)
    status = "ok" if lossy == ambiguous == 0 else "FAIL"
    print(f"  regions {len(by_region):6}  lossy {lossy:5}  >1 form {ambiguous:5}   {status}")


if __name__ == "__main__":
    check_losslessness()
    check_canonicality()
    check_3d()
