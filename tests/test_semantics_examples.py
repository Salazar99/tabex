"""Semantic-correctness examples for parse_graph.py's standardize().

Unlike test_dot_examples.py (regression: "output didn't change"), these
tests check the output against the actual STL meaning of the formula that
produced it, with the reasoning spelled out in each test.
"""
import math

import pytest

from conftest import EXAMPLES_DIR, REPO_ROOT, stlsat_available
from parse_graph import (
    build_tree_from_dot,
    discover_all_variables,
    generate_signal_space_from_formula,
    standardize,
)


def value_in_pieces(value, pieces):
    # A slot's interval list is read as a union: `value` satisfies the slot
    # if it falls inside any one piece.
    return any(iv.l <= value <= iv.r for iv in pieces)


def signal_space_from_dot_fixture(dot_name):
    content = (EXAMPLES_DIR / dot_name).read_text(encoding="utf-8")
    root = build_tree_from_dot(content)
    all_vars = discover_all_variables(content)
    return standardize(root, all_vars)


def test_G_requires_the_atom_at_every_instant_in_bound():
    # G[0,2] x > 0 means x(t) > 0 for ALL t in [0,2]. No disjunction/eventuality
    # choice point exists in this formula, so there should be exactly one path,
    # and it must require x in (0, inf) at every one of t=0,1,2 -- nothing more,
    # nothing less.
    paths = signal_space_from_dot_fixture("graph_G.dot")
    assert len(paths) == 1
    path = paths[0]
    assert set(path.timeline.keys()) == {0, 1, 2}
    for t in (0, 1, 2):
        pieces = path.timeline[t]["x"]
        assert all(iv.to_tuple() == (0.0, math.inf) for iv in pieces)


def test_F_partitions_into_disjoint_earliest_witness_paths():
    # F[0,2] x >= 0 means EXISTS t in [0,2] with x(t) >= 0. The tableau
    # enumerates one path per "earliest witness instant" (t=0, t=1, or t=2):
    # each path only constrains its own witness instant, leaves later instants
    # free, and forces earlier instants to the negation (x < 0) so the three
    # paths are disjoint (no double-counting the same satisfying trace).
    paths = signal_space_from_dot_fixture("graph_F_gex.dot")
    assert len(paths) == 3

    def in_path(path, signal):
        return all(value_in_pieces(signal[t], path.timeline[t]["x"]) for t in (0, 1, 2))

    # One concrete trace per true earliest-witness instant, plus one that
    # never satisfies x>=0 at all.
    witness_at_0 = {0: 1, 1: -1, 2: -1}
    witness_at_1 = {0: -1, 1: 1, 2: -1}
    witness_at_2 = {0: -1, 1: -1, 2: 1}
    never_satisfied = {0: -1, 1: -1, 2: -1}

    owners = []
    for signal in (witness_at_0, witness_at_1, witness_at_2):
        matches = [i for i, p in enumerate(paths) if in_path(p, signal)]
        assert len(matches) == 1, f"{signal} should be admitted by exactly one path, got {matches}"
        owners.append(matches[0])

    # Soundness: a distinct path owns each of the 3 witness scenarios (no
    # overlap between paths for these representative traces).
    assert len(set(owners)) == 3

    # Soundness: the non-satisfying trace is admitted by NO path.
    assert not any(in_path(p, never_satisfied) for p in paths)


def test_disjunction_merge_produces_a_correct_union_not_intersection():
    # F[0,2] (x>0 || x==0) is semantically F[0,2] x>=0. At the disjunction's
    # choice point, standardize() merges the two sibling branches (x>0, x==0)
    # into ONE path whose slot is a *list* of two Interval pieces -- this only
    # matches the formula if that list means union (either piece satisfies),
    # not intersection.
    paths = signal_space_from_dot_fixture("graph_F_g_or_eqx.dot")
    witness_path = next(
        p for p in paths
        if value_in_pieces(0.0, p.timeline[0]["x"]) and value_in_pieces(2.0, p.timeline[0]["x"])
    )
    pieces = witness_path.timeline[0]["x"]
    assert len(pieces) == 2

    assert value_in_pieces(0.0, pieces)      # satisfies via the x==0 disjunct
    assert value_in_pieces(2.0, pieces)      # satisfies via the x>0 disjunct
    assert not value_in_pieces(-1.0, pieces)  # satisfies neither disjunct -> correctly excluded


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_conjunction_on_one_node_is_correctly_intersected():
    # G[0,2] (x > 0 && x < 5) is semantically x in (0,5) at every t in [0,2].
    # standardize() also builds interval *lists* by appending a parent
    # obligation's constraint onto its single child's list (a genuinely
    # different code path from the disjunction merge above) -- if that list
    # were ever read as a union instead of an intersection, this formula
    # would wrongly resolve to "all reals" instead of (0,5). In practice this
    # doesn't happen: node_own_constraints() intersects same-variable "&&"
    # clauses *within one node's formula string* before the list-accumulation
    # step ever runs, and stlsat's tableau never splits "&&" across separate
    # tree nodes -- so every piece the list accumulates for a single
    # conjunction turns out identical (see README's Testing section for the
    # caveat this leaves for a hypothetical future consumer of the raw list).
    paths = generate_signal_space_from_formula("G[0,2] (x > 0 && x < 5)", tabex_root=REPO_ROOT)
    assert len(paths) == 1
    for t in (0, 1, 2):
        pieces = paths[0].timeline[t]["x"]
        assert all(iv.to_tuple() == (0.0, 5.0) for iv in pieces)
