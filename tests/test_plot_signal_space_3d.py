from plotting.plot_signal_space_3d import coverage, grid
from similarity.reference_semantics import parse, signal_space, variables


def test_bounded_eventually_gives_a_3x3x3_arrangement():
    """F[0,2](x in (1,5)) is three orthogonal slabs: 3 cuts per axis, 27 cells.

    The counts are the whole cover-not-partition story in one line -- 8 corner
    cells lie outside R, and the centre cube (1,5)^3 is covered three times.
    """
    tree = parse("F[0,2](x>1 && x<5)")
    paths = signal_space(tree, sorted(variables(tree)))
    axes = sorted((t, v) for t in paths[0].timeline for v in paths[0].timeline[t])
    counts = coverage(paths, axes, grid(paths, axes, 6.0))

    assert counts.shape == (3, 3, 3)
    assert {n: int((counts == n).sum()) for n in range(4)} == {0: 8, 1: 12, 2: 6, 3: 1}
