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

# Boxes are built from real Interval objects so the sweep exercises endpoint
# OPENNESS, not just the closed case. Without that, "(x<1)||(x>1)" and "true"
# look like the same region and the properties below are vacuous where it
# matters most.


def _contains(interval, value):
    return ((value > interval.l if interval.lo else value >= interval.l) and
            (value < interval.r if interval.ro else value <= interval.r))


def _paths_2d(boxes):
    return [Path({0: {"x": [x], "y": [y]}}) for (x, y) in boxes]


def _points_2d(boxes):
    return frozenset((a, b) for a in LATTICE for b in LATTICE
                     if any(_contains(x, a) and _contains(y, b) for (x, y) in boxes))


def _canon_boxes_2d(boxes):
    return [(cell.timeline[0]["x"][0], cell.timeline[0]["y"][0])
            for cell in canonicalize(_paths_2d(boxes))]


def _random_interval(degenerate_probability):
    lo = random.randint(0, N - 1)
    if random.random() < degenerate_probability:
        return Interval(lo, lo)                       # an "==" atom
    hi = random.randint(lo + 1, N)
    return Interval(lo, hi, random.random() < 0.5, random.random() < 0.5)


def _random_2d(degenerate_probability):
    return [(_random_interval(degenerate_probability),
             _random_interval(degenerate_probability))
            for _ in range(random.randint(1, 4))]


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
        return [Path({0: {"x": [a], "y": [b]},
                      1: {"x": [c], "y": [Interval(-math.inf, math.inf)]}})
                for (a, b, c) in boxes]

    def points(boxes):
        return frozenset((i, j, k)
                         for i in LATTICE for j in LATTICE for k in LATTICE
                         if any(_contains(a, i) and _contains(b, j) and _contains(c, k)
                                for (a, b, c) in boxes))

    def canon_points(boxes):
        return points([(cell.timeline[0]["x"][0], cell.timeline[0]["y"][0],
                        cell.timeline[1]["x"][0])
                       for cell in canonicalize(paths(boxes))])

    def random_boxes():
        return [tuple(_random_interval(0.0) for _ in range(3))
                for _ in range(random.randint(1, 4))]

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
