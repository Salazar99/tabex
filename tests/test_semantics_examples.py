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
    canonical_atoms,
    discover_all_variables,
    generate_signal_space_from_formula,
    intersect_piece_lists,
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


def test_negated_atoms_flip_their_operator_instead_of_being_dropped():
    # stlsat prints a negated atom with the "!" glued to the variable and the
    # operator NOT flipped: "!(x<0)" comes out as the label "(!x < 0)". If the
    # "!" isn't handled the clause matches no atom pattern and is silently
    # discarded, leaving the variable fully unconstrained -- so "!(x<0)" would
    # read as "any x" rather than "x >= 0".
    INF = math.inf
    assert canonical_atoms("(!x < 0)")["x"][0].to_tuple() == (0.0, INF)
    assert canonical_atoms("(!x <= 0)")["x"][0].to_tuple() == (0.0, INF)
    assert canonical_atoms("(!x > 0)")["x"][0].to_tuple() == (-INF, 0.0)
    assert canonical_atoms("(!x >= 0)")["x"][0].to_tuple() == (-INF, 0.0)
    # Negating "==" gives "!=", which is a *union* of two half-lines, so a
    # constraint has to be a list of pieces rather than a single interval.
    assert [iv.to_tuple() for iv in canonical_atoms("(!x == 5)")["x"]] == [(-INF, 5.0), (5.0, INF)]


def test_negated_bounds_reconstruct_the_same_interval_as_plain_ones():
    # !(x<0) && !(x>10) is semantically x in [0,10] -- the whole point of
    # flipping the operator rather than dropping the clause.
    pieces = canonical_atoms("(!x < 0)")["x"]
    other = canonical_atoms("(!x > 10)")["x"]
    combined = intersect_piece_lists(pieces, other)
    assert [iv.to_tuple() for iv in combined] == [(0.0, 10.0)]


def test_deferred_obligation_asserts_nothing_at_its_own_instant():
    # An "O"-marked formula was already unfolded WITHOUT success at this
    # instant, so it constrains nothing now -- its atoms belong to the
    # instants it defers to. Stripping the prefix and reading the inner
    # conjuncts instead leaks "x > 0" into the continuation branch, which is
    # what made F[0,1](G[0,1] x>0) and F[0,1](x>0 && G[1,1] x>0) -- provably
    # equivalent -- extract differently.
    assert canonical_atoms("OF[0,1] (x > 0 && G[1,1] x > 0)") == {}
    assert canonical_atoms("OG[0,2] x > 0") == {}
    assert canonical_atoms("O(x > 0 U[0,4] (y > 3))") == {}
    # G asserts its body now (persistence); F does not (it splits).
    assert canonical_atoms("G[0,2] x > 0")["x"][0].to_tuple() == (0.0, math.inf)
    assert canonical_atoms("F[0,2] x >= 0") == {}


def test_nested_conjunction_is_not_mis_split_on_a_nested_disjunction():
    # "&&" must be split at paren depth 0 only: the nested "(y > 1 || y < -1)"
    # is a disjunction this node doesn't own, but "x > 0" beside it is a real
    # top-level conjunct and must survive.
    atoms = canonical_atoms("(x > 0 && (y > 1 || y < -1))")
    assert atoms["x"][0].to_tuple() == (0.0, math.inf)
    assert "y" not in atoms


def test_n_ary_disjunction_merges_all_branches_not_just_a_pair():
    # (x>=0 && x<=5) || (x==5 || (x>=5 && x<=10)) is semantically x in [0,10].
    # STLSAT flattens this 3-way "||" into ONE tableau node with 3 children
    # (not nested binary splits), so this exercises standardize()'s N-ary
    # generalization of the same-instant/same-variable merge rule -- if it
    # silently dropped a branch instead of unioning all of them, this would
    # wrongly exclude part of [0,10].
    paths = signal_space_from_dot_fixture("graph_or3.dot")
    assert len(paths) == 1
    pieces = paths[0].timeline[0]["x"]
    for value in (0.0, 2.5, 5.0, 7.5, 10.0):
        assert value_in_pieces(value, pieces)
    assert not value_in_pieces(-0.1, pieces)
    assert not value_in_pieces(10.1, pieces)
