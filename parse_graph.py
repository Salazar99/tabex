import os
import re
import subprocess
import sys
import tempfile
import pathlib
from fractions import Fraction

import pydot

#debug flags
dbg = False
debug_only_tree = False

# Print the parsed tree in a readable format 
def pretty_print_tree(node, indent=0):
    if node is None:
        print(' ' * indent + '<empty>')
        return
    props = ', '.join(f"{k}={v}" for k, v in node.properties.items()) if node.properties else ''
    formulas = ', '.join(node.formulas) if getattr(node, 'formulas', None) else ''
    print(' ' * indent + f"Node {node.id} t={node.t} label={repr(node.label)}")
    if props:
        print(' ' * (indent + 2) + f"properties: {props}")
    if formulas:
        print(' ' * (indent + 2) + f"formulas: {formulas}")
    for child in node.children:
        pretty_print_tree(child, indent + 4)
        
def _endpoint(value):
    """An interval endpoint: an exact Fraction, or a float infinity.

    Fraction and float compare exactly against each other in Python, so the
    rest of the pipeline needs no special handling -- only construction does.
    """
    if isinstance(value, Fraction):
        return value
    if value in (float('inf'), float('-inf')):
        return value
    return Fraction(str(value)) if isinstance(value, (str, float)) else Fraction(value)


class Interval:
    # Endpoints carry their own openness (`lo`/`ro`: True = OPEN at that end).
    # Without it "y < 0" and "y > 0" both become bounds touching at 0 and their
    # intersection is the non-empty point [0,0], so a contradictory branch --
    # which stlsat writes to the DOT before Z3 rejects it -- survives
    # standardize()'s rejected-branch filter as a spurious degenerate cell.
    #
    # A finite endpoint is an EXACT rational, not a float. Rounding "1/3" to
    # binary64 would make the interval denote {x : x > float(1/3)} -- a
    # different subset of R, since float(1/3) < 1/3 -- and, worse, would let two
    # distinct endpoints collapse onto one breakpoint. A box endpoint that is
    # not a breakpoint is exactly what the dichotomy lemma forbids, so the
    # canonical form's proof depends on this being exact.
    #
    # Nothing downstream can reintroduce rounding: every use of `l`/`r` in the
    # region pipeline compares or copies them, never combines them
    # arithmetically, so the endpoints appearing anywhere are always a subset of
    # those the atoms introduced. See FORMAL_PROOFS.md.
    __slots__ = ("l", "r", "lo", "ro")

    def __init__(self, l, r, lo=False, ro=False):
        self.l = _endpoint(l)
        self.r = _endpoint(r)
        # An infinite end is unreachable, so it is always open.
        self.lo = bool(lo) or self.l == float('-inf')
        self.ro = bool(ro) or self.r == float('inf')

    def is_empty(self):
        # A single point survives only when closed on both sides: (0,0], [0,0)
        # and (0,0) all admit no value.
        return self.l > self.r or (self.l == self.r and (self.lo or self.ro))

    def intersect(self, other):
        if self.l > other.l:
            nl, nlo = self.l, self.lo
        elif self.l < other.l:
            nl, nlo = other.l, other.lo
        else:
            nl, nlo = self.l, self.lo or other.lo
        if self.r < other.r:
            nr, nro = self.r, self.ro
        elif self.r > other.r:
            nr, nro = other.r, other.ro
        else:
            nr, nro = self.r, self.ro or other.ro
        result = Interval(nl, nr, nlo, nro)
        return None if result.is_empty() else result

    def __repr__(self):
        l_str = "-inf" if self.l == float('-inf') else str(self.l)
        r_str = "inf" if self.r == float('inf') else str(self.r)
        return f"{'(' if self.lo else '['}{l_str}, {r_str}{')' if self.ro else ']'}"

    def to_tuple(self):
        return (self.l, self.r, self.lo, self.ro)

    def __eq__(self, other):
        return isinstance(other, Interval) and self.to_tuple() == other.to_tuple()

    def __hash__(self):
        return hash(self.to_tuple())


def merge_pieces(pieces):
    # Collapse overlapping/touching Interval pieces into a minimal disjoint
    # set, so duplicate/overlapping pieces (e.g. [[0,inf],[0,inf]]) don't
    # double-count length or get treated as distinct alternatives.
    # Empty pieces (the marker intersect_piece_lists returns for contradictory
    # bounds) are dropped: they admit no value, so they must not survive as an
    # alternative.
    #
    # Two pieces meeting at b only touch when at least one of them is CLOSED
    # there -- "(-inf,1)" and "(1,inf)" leave a hole at 1 and stay separate,
    # which is what makes "(x<1) || (x>1)" different from "true".
    merged = []
    for iv in sorted((p for p in pieces if not p.is_empty()), key=lambda p: (p.l, p.lo)):
        if merged and (iv.l < merged[-1].r or
                       (iv.l == merged[-1].r and not (iv.lo and merged[-1].ro))):
            last = merged[-1]
            if iv.r > last.r or (iv.r == last.r and last.ro and not iv.ro):
                merged[-1] = Interval(last.l, iv.r, last.lo, iv.ro)
        else:
            merged.append(Interval(iv.l, iv.r, iv.lo, iv.ro))
    return merged

#A path is a sequence of time-interval mappings for each variable
class Path:
    def __init__(self, timeline):
        # timeline: {t: {var: Interval}}
        self.timeline = timeline

    def copy(self):
        new_tl = {t: {v: list(pieces) for v, pieces in slot.items()}
                  for t, slot in self.timeline.items()}
        return Path(new_tl)

class Node:
    def __init__(self, node_id, t, label, properties, formulas):
        self.id = node_id
        self.t = t
        self.properties = properties
        self.label = label
        self.children = []
        self.intervals = {} # Populated by your parser
        self.paths = []     # Used for the standardization algorithm
        self.formulas = formulas  # Field to memorize the identifying formulas

def parse_tableau(graph):
    nodes = {}

    # Optimized to ignore (N) or (N) -> (Y) and capture the actual formula
    formula_strip_pattern = re.compile(r'\(.*?\)(?:\s*→\s*\(.*?\))?\s*\|\s*(.*)')
    ineq_pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|>|<|==)\s*([+-]?\d+(?:\.\d+)?)')

    for dot_node in graph.get_nodes():
        label_attr = dot_node.get_label()
        if label_attr is None:
            continue  # skip pydot artifacts / nodes without a label

        node_id = dot_node.get_name().strip('"')
        label_text = label_attr.strip('"')

        t_match = re.search(r'\bt\s*=\s*(\d+)', label_text, re.IGNORECASE)
        t = int(t_match.group(1)) if t_match else 0

        node_properties = {}
        node_formulas = []

        for line in label_text.split('\n'):
            # Only process lines that contain the formula structure
            strip_match = formula_strip_pattern.search(line)
            if not strip_match:
                continue
            
            formula_part = strip_match.group(1).strip()
            
            #Match Node's formula. 
            #If the formula contains temporal operators with intervals,
            #Check if Node time is within the specified interval. If not, mark node as strict undefined
            f_match = re.match(r'^(O)?F\[(\d+),(\d+)\]', formula_part)
            if f_match:
                a, b = int(f_match.group(2)), int(f_match.group(3))
                if not (a <= t <= b):
                    formula_part = f"UNDEF"
            g_match = re.match(r'^(O)?G\[(\d+),(\d+)\]', formula_part)
            if g_match:
                a, b = int(g_match.group(2)), int(g_match.group(3))
                if not (a <= t <= b):
                    formula_part = f"UNDEF"
            u_match = re.match(r'^(O)?U\[(\d+),(\d+)\]', formula_part)
            if u_match:
                a, b = int(u_match.group(2)), int(u_match.group(3))
                if not (a <= t <= b):
                    formula_part = f"UNDEF"
                
            # Memorize the clean formula
            node_formulas.append(formula_part)
            
            # Rule 3: Capture Raw Constraints
            
            found_ineqs = ineq_pattern.findall(formula_part)
            for var, op, val in found_ineqs:
                if var not in ('F', 'OF', 'G', 'OG'):
                    if var not in node_properties:
                        node_properties[var] = []
                    if formula_part != "UNDEF":    
                        node_properties[var].append(f"{op}{val}")
                    else:
                        node_properties[var].append("UNDEF")

        nodes[node_id] = {
            'id': node_id,
            't': t,
            'properties': node_properties,
            'formulas': node_formulas,
            'label': label_text
        }

    return {
        'nodes': nodes,
        'sorted_node_ids': sorted(nodes.keys(), key=lambda x: int(re.search(r'\d+', x).group())),
    }
    
def build_tree_from_dot(dot_content):
    # 1. Parse the DOT structure once with a real DOT parser (pydot)
    graph = pydot.graph_from_dot_data(dot_content)[0]

    # 2. Reuse existing tableau parsing logic to get raw node data
    tableau_data = parse_tableau(graph)
    raw_nodes = tableau_data['nodes']

    # 3. Create Node objects
    tree_nodes = {}
    for nid, data in raw_nodes.items():
        # Correctly passing the real label from the parsed data
        tree_nodes[nid] = Node(data['id'], data['t'], label=data.get('label', ''), properties=data['properties'], formulas=data['formulas'])


    # 4. Create structural edges
    # Standard DOT uses "--" for undirected graphs, usually representing
    # parent-child flow in tableau construction
    # Track children to identify the root
    has_parent = set()

    for edge in graph.get_edges():
        parent_id = edge.get_source().strip('"')
        child_id = edge.get_destination().strip('"')
        if parent_id in tree_nodes and child_id in tree_nodes:
            tree_nodes[parent_id].children.append(tree_nodes[child_id])
            has_parent.add(child_id)
            
    # 4. Identify Root (node with no parent)
    root = None
    for nid in tree_nodes:
        if nid not in has_parent:
            root = tree_nodes[nid]
            break
            
    return root


class UnsupportedFormula(ValueError):
    """A tableau label outside the fragment the extraction can represent.

    Raised rather than returning {} because {} already means "constrains
    nothing at this instant" -- a real answer for F, U, O-marked obligations
    and branching connectives. A silently dropped label is indistinguishable
    from a genuinely free one, so it widens the signal space to all of R and
    the pipeline reports a confident, wrong answer. See README's
    "Supported fragment".
    """


# Canonicalization of stlsat's formula-label strings into the atomic
# constraints a node asserts AT ITS OWN INSTANT. stlsat prints a negated
# atom with the "!" glued to the variable and the operator NOT flipped
# ("!(x<0)" -> "(!x < 0)"), so the flip has to happen here.
NEGATED_OP = {'>': '<=', '>=': '<', '<': '>=', '<=': '>', '==': '!=', '!=': '=='}
# A constant may be an integer, a decimal, or a RATIONAL: stlsat's AExpr::Num
# is a Ratio<i64> and prints as "3/2". Matching only integers and decimals made
# "x > 5" work while "x > 3/2" silently fell through to "unconstrained".
_CONST = r'[+-]?\d+(?:\.\d+)?(?:/\d+)?'
_ATOM = re.compile(
    rf'^(!\s*)?([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|!=|==|>|<)\s*({_CONST})$')
_TEMPORAL = re.compile(r'^(O?)([FG])\[(\d+),(\d+)\]\s*')
_O_MARK = re.compile(r'^O(?=[\(A-Za-z])')
# Shapes that legitimately assert nothing at this instant, and so must NOT be
# mistaken for something we failed to parse.
_UNTIL = re.compile(r'\bU\[\d+,\d+\]')
_RELEASE = re.compile(r'\bR\[\d+,\d+\]')


def split_top_level(text, sep):
    # Split on `sep` only where parenthesis depth is 0, so a nested
    # "(a && b)" inside a larger formula is not mis-split.
    parts, depth, current, i = [], 0, [], 0
    while i < len(text):
        c = text[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        if depth == 0 and text.startswith(sep, i):
            parts.append(''.join(current))
            current = []
            i += len(sep)
            continue
        current.append(c)
        i += 1
    parts.append(''.join(current))
    return [p.strip() for p in parts]


def strip_outer_parens(text):
    # Only strip parens that genuinely wrap the whole string: "(a) && (b)"
    # must keep its outer characters.
    text = text.strip()
    while text.startswith('(') and text.endswith(')'):
        depth = 0
        for i, c in enumerate(text):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0 and i != len(text) - 1:
                    return text
        text = text[1:-1].strip()
    return text


def atom_to_pieces(op, val):
    # A constraint is a *list* of Interval pieces (read as a union), because
    # "!=" is two disjoint half-lines -- written directly, or produced by
    # negating "==". Strict operators produce OPEN endpoints, so "x>0 && x<=0"
    # comes out empty instead of collapsing to the point [0,0].
    if op not in NEGATED_OP:
        # There used to be a catch-all "return everything" here, which is the
        # exact failure mode UnsupportedFormula exists to prevent: an operator
        # we cannot read became the widest possible claim.
        raise UnsupportedFormula(
            f"unsupported comparison operator {op!r}; the fragment allows "
            f"{sorted(NEGATED_OP)}. See README's 'Supported fragment'.")
    # Kept EXACT. Rounding here would make the interval denote a different set
    # of reals than the atom does, and could collapse two distinct endpoints
    # onto one breakpoint -- see Interval.
    v = Fraction(str(val))
    if op == '>':
        return [Interval(v, float('inf'), lo=True)]
    if op == '>=':
        return [Interval(v, float('inf'))]
    if op == '<':
        return [Interval(float('-inf'), v, ro=True)]
    if op == '<=':
        return [Interval(float('-inf'), v)]
    if op == '==':
        return [Interval(v, v)]
    return [Interval(float('-inf'), v, ro=True), Interval(v, float('inf'), lo=True)]


def intersect_piece_lists(a, b):
    out = [iv for x in a for y in b if (iv := x.intersect(y)) is not None]
    # An empty result means genuinely contradictory bounds; keep an explicit
    # empty interval rather than [] (which would read as "unconstrained").
    return out or [Interval(float('inf'), float('-inf'))]


def canonical_atoms(formula, t, relative=False):
    # One formula label -> {var: [Interval, ...]} it asserts AT INSTANT `t`.
    #
    # Nesting needs care, because the two levels of a label are anchored
    # differently. stlsat REBASES an inner operator only when it unfolds the
    # outer one -- "G[0,1](G[0,1] x>0)" becomes "G[1,2] x>0" at t=1 -- so in an
    # un-unfolded label:
    #
    #   * the OUTERMOST interval is absolute: "G[a,b] phi" constrains this node
    #     exactly while a <= t <= b (`relative=False`);
    #   * an interval BELOW a temporal operator is still relative to it, so
    #     "G[c,d] phi" there constrains the *current* instant only when its
    #     window starts at 0 (`relative=True`).
    #
    # Reading a nested window as absolute is what makes "G[1,1] G[1,2] P" at
    # t=1 wrongly assert P now, when P is really required on [2,3].
    # Boolean connectives do not change the anchor -- only passing through a
    # temporal operator does.
    text = strip_outer_parens(formula)
    if not text or text == 'UNDEF':
        return {}
    # An "O"-marked obligation was already unfolded WITHOUT success at this
    # instant, so it asserts nothing now -- its atoms belong to the instants
    # it defers to. Stripping the prefix and reading the inner conjuncts
    # instead would wrongly constrain the continuation branch.
    if _O_MARK.match(text):
        return {}
    m = _TEMPORAL.match(text)
    if m:
        # G[a,b] phi asserts phi now, but only while t is inside [a,b].
        # F[a,b] phi asserts nothing now -- it splits into a witness /
        # continuation pair, and so does "U".
        if m.group(1) == 'O' or m.group(2) == 'F':
            return {}
        lower, upper = int(m.group(3)), int(m.group(4))
        covers_now = lower == 0 if relative else lower <= t <= upper
        if not covers_now:
            return {}
        # Recurse rather than stop: the body may be another temporal that this
        # G is the only carrier of. Measured on random nested formulas, a
        # nested temporal is the sole source of a constraint at roughly a
        # quarter of the nodes that carry one, so giving up here silently
        # leaves those instants unconstrained.
        return canonical_atoms(text[m.end():], t, relative=True)
    if len(split_top_level(text, '||')) > 1:
        return {}  # disjuncts are already separate children
    if len(split_top_level(text, '->')) > 1:
        return {}  # "A -> B" is "!A || B": the same branching case as "||"
    result = {}
    for clause in split_top_level(text, '&&'):
        clause = strip_outer_parens(clause)
        atom = _ATOM.match(clause)
        if atom:
            neg, var, op, val = atom.groups()
            pieces = atom_to_pieces(NEGATED_OP[op] if neg else op, val)
        elif clause != text:
            pieces_by_var = canonical_atoms(clause, t, relative)  # nested group / temporal conjunct
            for var, pieces in pieces_by_var.items():
                result[var] = intersect_piece_lists(result[var], pieces) if var in result else pieces
            continue
        elif _asserts_nothing_here(clause):
            continue
        else:
            # Everything the fragment cannot represent lands here. Returning {}
            # would say "this instant is unconstrained", which is the widest
            # possible claim -- so an unparsed atom silently turns the signal
            # space into all of R.
            raise UnsupportedFormula(f"{_why_unsupported(clause)} (at t={t}). "
                                     f"See README's 'Supported fragment'.")
        result[var] = intersect_piece_lists(result[var], pieces) if var in result else pieces
    return result


def _asserts_nothing_here(clause):
    # Shapes that genuinely constrain nothing at this instant, and so must not
    # be mistaken for something we failed to parse. Everything here is either
    # vacuous or resolved by the tableau's own branching.
    if clause == 'true':
        return True
    if _UNTIL.search(clause):
        # An until splits into witness / continuation children, and its
        # invariant reaches us as a sibling "G[0,a] phi" conjunct.
        return True
    return False


def _why_unsupported(clause):
    # A specific diagnosis beats "unparsed": the caller needs to know whether
    # they hit a scope boundary or a bug.
    if clause == 'false':
        return (f"{clause!r} admits no signal, but the signal space has no way "
                f"to say 'empty' for an unnamed variable")
    if _RELEASE.search(clause):
        return (f"{clause!r} still contains a release operator, which stlsat "
                f"should have rewritten into F/U/G before emitting the graph")
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', clause):
        return (f"{clause!r} is a boolean atom; the signal space models "
                f"real-valued signals only")
    return (f"cannot represent {clause!r}: the signal space is a union of "
            f"per-variable intervals, so an atom must be "
            f"'variable op constant' (a relation between variables, an "
            f"arithmetic term or an absolute value is not a box)")


def collect_times(root):
    # Every discrete instant this formula's tableau mentions.
    times = set()
    def walk(n):
        times.add(n.t)
        for c in n.children:
            walk(c)
    walk(root)
    return times


# A formula label that still holds an undischarged temporal obligation.
#
# In a fully unrolled tableau every leaf carries ATOMS ONLY -- check any of
# graph_examples/*.dot: graph_G.dot ends at "x > 0", graph_U.dot at
# "x > 0, y > 3". So a leaf that still names F, G or U is a branch stlsat
# stopped expanding, not a branch it completed.
_PENDING = re.compile(r'(?:^|[\s(])O?[FGU]\[\d+,\d+\]|^O(?=\()')


def prune_incomplete(node):
    # stlsat stops expanding a branch the moment it knows the branch is dead,
    # so the DOT contains childless nodes that were never COMPLETED -- for the
    # unsatisfiable "F[0,1](x>1 && x<0) && ((y>0)||(y<=0))" it ends with a
    # childless node whose only formula is still "F[0,1] (x > 1 && x < 0)".
    # canonical_atoms() reads an F as asserting nothing now, so that node would
    # extract as a fully UNCONSTRAINED path and an unsatisfiable formula would
    # come out with a non-empty signal space.
    #
    # A complete branch has discharged every eventuality: its leaf carries
    # atoms, or UNDEF, and nothing else. Returns True when `node` is dead --
    # and a node all of whose children died is dead too, which is what makes
    # emptiness propagate to the root without consulting stlsat's own SAT
    # verdict (which is order-dependent and sometimes wrong).
    if not node.children:
        return any(formula.strip() != 'UNDEF' and _PENDING.search(formula.strip())
                   for formula in node.formulas)
    node.children = [c for c in node.children if not prune_incomplete(c)]
    return not node.children


def complement_of(intervals):
    # Complement of the union of `intervals` (a witness constraint, possibly a merged
    # multi-piece signal set), computed exactly via De Morgan: complement(A u B u ...)
    # = complement(A) n complement(B) n ..., reusing Interval.intersect. This avoids
    # over-approximating by merging unrelated ranges (e.g. complementing (0,inf) yields
    # (-inf,0], not the whole real line).
    #
    # The complement FLIPS each endpoint's openness: not(v, inf) is
    # (-inf, v], so the two never overlap at v.
    # An EMPTY input means "nothing is required", whose complement is the whole
    # line. An empty RESULT means the input already covered the line, whose
    # complement is nothing at all. Conflating the two used to hand a
    # tautological witness an unconstrained continuation instead of killing the
    # branch -- the widest possible answer where the right one was "no branch".
    if not intervals:
        return [Interval(float('-inf'), float('inf'))]
    per_interval_complements = []
    for iv in intervals:
        pieces = []
        if iv.l != float('-inf'):
            pieces.append(Interval(float('-inf'), iv.l, ro=not iv.lo))
        if iv.r != float('inf'):
            pieces.append(Interval(iv.r, float('inf'), lo=not iv.ro))
        per_interval_complements.append(pieces)
    result = per_interval_complements[0]
    for pieces in per_interval_complements[1:]:
        result = [inter for a in result for b in pieces if (inter := a.intersect(b)) is not None]
    return result


def negate_witness_boxes(boxes):
    # not(W1 or ... or Wk) = AND_j (OR_var not Wj[var]).
    #
    # Negating each variable of a MERGED witness bucket instead -- which is
    # what pooling every witness timeline into one {var: pieces} map did --
    # destroys the correlation between variables and between alternatives.
    # For "F[0,1]((x>0 && y>0) || (x<0 && y<0))" the two witness boxes pool
    # into x: [[0,inf],[-inf,0]], whose complement is the degenerate point
    # x==0, and both continuation branches vanish.
    #
    # So distribute the conjunction of disjunctions into a list of
    # alternative slots, one continuation path per combination.
    alternatives = [{}]
    for box in boxes:
        if not box:
            continue  # a witness that asserts nothing carries no information
        expanded = []
        for alternative in alternatives:
            for var, pieces in box.items():
                complement = complement_of(merge_pieces(pieces))
                merged = dict(alternative)
                merged[var] = (intersect_piece_lists(merged[var], complement)
                               if var in merged else complement)
                expanded.append(merged)
        # Dedup and drop contradictory alternatives as we go -- the raw
        # product is |vars|**|boxes| and blows up without this.
        seen = {}
        for alternative in expanded:
            if any(not merge_pieces(pieces) for pieces in alternative.values()):
                continue
            key = tuple(sorted((var, iv.to_tuple())
                               for var, pieces in alternative.items()
                               for iv in merge_pieces(pieces)))
            seen.setdefault(key, alternative)
        alternatives = list(seen.values())
        if not alternatives:
            break
    return alternatives


#Traverse the tree and standardize paths based on the discovered nodes
def standardize(root, all_vars, all_times=None):
    # `all_times` defaults to this formula's own instants. A comparison
    # between two formulas passes the *joint* time domain, for the same
    # reason it passes the joint variable set: padding an instant with
    # [-inf, +inf] does not change the region, but leaving it out gives the
    # two sides different time domains, which Path_sim's |T1 u T2|
    # denominator then charges as disagreement even when the formulas are
    # equivalent. Canonicalisation plus trimming remove the padding again.
    if prune_incomplete(root):
        return []  # every branch was rejected -- L(phi) is empty
    # After pruning, so an instant only reachable through a dead branch does
    # not survive as a padded column.
    all_times = set(collect_times(root)) if all_times is None else set(all_times)

    def node_own_constraints(node):
        # Constraints this node asserts at its own instant, as
        # {var: [Interval, ...]} (a union of pieces). All the parsing cases
        # -- negated atoms, O-marked deferred obligations, G vs F prefixes,
        # top-level "||"/"&&" -- live in canonical_atoms() above.
        result = {}
        for formula in node.formulas:
            for var, pieces in canonical_atoms(formula, node.t).items():
                result[var] = intersect_piece_lists(result[var], pieces) if var in result else pieces
        return result

    def is_leaf(node):
        return not node.children

    def recurse(node):
        # Returns a list of sparse timelines: [{t: {var: [Interval, ...]}}, ...]
        if is_leaf(node):
            slot = {var: list(pieces) for var, pieces in node_own_constraints(node).items()}
            return [{node.t: slot}]

        if len(node.children) == 1:
            child_tls = recurse(node.children[0])
            own = node_own_constraints(node)
            if not own:
                return child_tls
            result = []
            for tl in child_tls:
                new_tl = {t: dict(v) for t, v in tl.items()}
                slot = dict(new_tl.get(node.t, {}))
                for var, pieces in own.items():
                    # Algorithm 1 line 19: a node's own bound INTERSECTS what
                    # its child already requires (both must hold at this
                    # instant) -- appending would read the slot's piece list
                    # as a union and wrongly widen the region, e.g. turning
                    # "x<=2 && x>0" into all of R.
                    slot[var] = intersect_piece_lists(slot[var], pieces) if var in slot else list(pieces)
                new_tl[node.t] = slot
                result.append(new_tl)
            return result

        # N >= 2 children. STLSAT flattens an n-ary disjunction (A || B || C)
        # into one node with N children rather than nested binary splits, so
        # Definition 4's binary combination rules are generalized here by
        # associativity of "or" (A || B || C == A || (B || C)).
        #
        # Classification is PER TIMELINE, not per child: one child can return
        # several alternative timelines and only some of them advance, and
        # marking the whole group as advancing would then hand a witness
        # timeline to the continuation branch below.
        timelines = [tl for c in node.children for tl in recurse(c)]
        advances = [any(t > node.t for t in tl) for tl in timelines]

        if not any(advances) or all(advances):
            # A plain disjunction at this instant, or several continuations
            # with no witness among them: either way the alternatives are a
            # union, which is exactly a list of separate paths. canonicalize()
            # merges whatever is mergeable, so there is nothing to pre-merge
            # here.
            return timelines

        # Some alternatives stay at this instant (witness), others advance in
        # time (continuation): a continuation implies NO witness holds yet.
        witness_tls = [tl for tl, adv in zip(timelines, advances) if not adv]
        continue_tls = [tl for tl, adv in zip(timelines, advances) if adv]
        alternatives = negate_witness_boxes([tl.get(node.t, {}) for tl in witness_tls])
        adjusted = []
        for tl in continue_tls:
            for alternative in (alternatives or [{}]):
                new_tl = {t: dict(v) for t, v in tl.items()}
                slot = dict(new_tl.get(node.t, {}))
                for var, complement in alternative.items():
                    # Intersect, don't overwrite: whatever this instant already
                    # requires (e.g. an Until's invariant) still has to hold.
                    slot[var] = (intersect_piece_lists(slot[var], complement)
                                 if var in slot else list(complement))
                new_tl[node.t] = slot
                adjusted.append(new_tl)
        return witness_tls + adjusted

    raw = recurse(root)
    # Drop rejected branches -- the paper's Lemma 4 "Rejected" case, which
    # Algorithm 1 leaves out because it assumes the tableau contains only
    # accepted branches. stlsat's DOT does NOT: process_job() writes a node's
    # children to the graph when it decomposes, before each child is itself
    # Z3-checked, so a child that later fails the check is already in the
    # file (as a childless leaf with contradictory bounds). Whole-formula
    # satisfiability doesn't prevent this -- "(y<-1) && ((y>0) || (y<=0))" is
    # satisfiable via y<=0, yet its y>0 disjunct is dead on arrival. Since
    # every constraint is a per-variable interval, a branch admits no signal
    # exactly when some variable's piece list is empty -- which needs the
    # endpoints' openness to be right, or "y<0 && y>0" reads as the point
    # [0,0] instead of nothing and the dead branch survives.
    raw = [tl for tl in raw
           if not any(not merge_pieces(pieces)
                      for slot in tl.values() for pieces in slot.values())]
    final_paths = []
    for tl in raw:
        full = {}
        for t in sorted(all_times):
            slot = dict(tl.get(t, {}))
            for var in all_vars:
                slot.setdefault(var, [Interval(float('-inf'), float('inf'))])
            full[t] = slot
        final_paths.append(Path(full))
    return final_paths
        

def discover_all_variables(dot_content):
    # Must accept exactly the operators and constants _ATOM does, or a variable
    # constrained only by an omitted form goes missing from the ambient space
    # entirely -- "x != 5" used to yield no variables at all.
    ineq_pattern = re.compile(
        rf'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:>=|<=|!=|==|>|<)\s*{_CONST}')


    vars_found = set()
    # Use findall on the content
    for match in ineq_pattern.finditer(dot_content):
        # Access the variable specifically (the first group)
        var = match.group(1)
        if var not in ('F', 'OF', 'G', 'OG', 'U', 'OU'):
            vars_found.add(var)
    return sorted(list(vars_found))

DEFAULT_STLSAT_ARGS = [
    "--no-jump-rule",
    "--no-formula-simplifications",
    "--no-formula-optimizations",
]

def resolve_tabex_root(tabex_root=None):
    root = tabex_root or os.environ.get("TABEX_ROOT", "~/tabex")
    return pathlib.Path(root).expanduser()

def run_stlsat(formula, tabex_root=None, extra_args=None):
    # Runs the real stlsat binary (via `cargo run --release`) on `formula`
    # and returns the DOT tableau it writes to --graph-output.
    #
    # stlsat's own "Tableau result:" verdict is deliberately NOT read.
    # prune_incomplete() derives emptiness from the graph instead, which keeps
    # the extraction independent of a one-line summary of a search whose shape
    # we are already reading in full. It also means a truncated or
    # mis-summarised tableau cannot silently empty a real signal space -- the
    # failure mode that "(x<1) && ((F[2,3](y<2)) || (x>=1))" used to trigger,
    # reporting UNSAT while the disjunct-swapped twin reported SAT.
    root = resolve_tabex_root(tabex_root)
    args = DEFAULT_STLSAT_ARGS if extra_args is None else extra_args

    with tempfile.TemporaryDirectory() as tmp_dir:
        stl_path = pathlib.Path(tmp_dir) / "formula.stl"
        dot_path = pathlib.Path(tmp_dir) / "tableau.dot"
        stl_path.write_text(formula, encoding="utf-8")

        result = subprocess.run(
            ["cargo", "run", "--release", str(stl_path), "--graph-output", str(dot_path), *args],
            cwd=str(root / "m_stlsat"),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"stlsat failed for formula {formula!r}:\n{result.stderr}")
        if not dot_path.is_file():
            raise RuntimeError(f"stlsat did not produce a graph output for formula {formula!r}")

        return dot_path.read_text(encoding="utf-8")

def generate_signal_space_from_formula(formula, tabex_root=None, extra_args=None, all_vars=None, all_times=None):
    # Full pipeline: formula string -> stlsat tableau -> tree -> standardized paths.
    # `all_vars`/`all_times` default to this formula's own variables/instants,
    # but a comparison between two formulas must pass the *joint* sets
    # (Definition 5/6: an axis is active for the comparison if either side
    # constrains it) -- see similarity/stl_similarity.py's calc_similarity_from_formulas.
    # An unsatisfiable formula falls out of standardize() as an empty list.
    dot_content = run_stlsat(formula, tabex_root, extra_args)
    root = build_tree_from_dot(dot_content)
    if all_vars is None:
        all_vars = discover_all_variables(dot_content)
    return standardize(root, all_vars, all_times)

def print_paths(source_label, final_path_list):
    print(f"--- Standardized Feasible Paths for {source_label} ---")
    for i, path in enumerate(final_path_list, 1):
        print(f"\nPath #{i}:")
        for t in sorted(path.timeline.keys()):
            constraints = path.timeline[t]
            print(f"  t={t}: {constraints}")

def main(dot_file_path):
    # 1. Load and parse the DOT content
    with open(dot_file_path, 'r', encoding='utf-8') as f:
        dot_content = f.read()

    # 2. Build the hierarchical tree structure
    root = build_tree_from_dot(dot_content)

    if dbg:
        pretty_print_tree(root)
        sys.exit(0)  # Exit after printing the tree for debugging

    # 3. Discover system variables for padding
    # This assumes we have collected all variables from the parser earlier
    all_vars = discover_all_variables(dot_content)

    # 5. Execute Iterative Signal Space Standardization (Algorithm 1)
    # We pass the root and the globally discovered variables
    final_path_list = standardize(root, all_vars)

    # 6. Output the results
    print_paths(dot_file_path, final_path_list)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the standardized signal space from a stlsat tableau.")
    parser.add_argument("dot_file", nargs="?", help="Path to an existing stlsat .dot tableau file.")
    parser.add_argument("--formula", help="STL formula string; runs stlsat automatically instead of using dot_file.")
    parser.add_argument("--tabex-root", help="Override TABEX_ROOT (default: $TABEX_ROOT or ~/tabex).")
    parser.add_argument("--save-dot", help="If set with --formula, also save the intermediate tableau .dot here.")
    cli_args = parser.parse_args()

    if cli_args.formula:
        dot_content = run_stlsat(cli_args.formula, cli_args.tabex_root)
        if cli_args.save_dot:
            pathlib.Path(cli_args.save_dot).write_text(dot_content, encoding="utf-8")
        root = build_tree_from_dot(dot_content)
        all_vars = discover_all_variables(dot_content)
        print_paths(cli_args.formula, standardize(root, all_vars))
    elif cli_args.dot_file:
        main(cli_args.dot_file)
    else:
        parser.error("Provide either a dot_file or --formula.")


