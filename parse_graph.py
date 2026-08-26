import os
import re
import subprocess
import sys
import tempfile
import pathlib

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
        
class Interval:
    def __init__(self, l, r):
        self.l = float(l)
        self.r = float(r)

    def is_empty(self):
        return self.l > self.r

    def intersect(self, other):
        nl = max(self.l, other.l)
        nr = min(self.r, other.r)
        if nl > nr: return None
        return Interval(nl, nr)

    def union(self, other):
        # Takes the spanning union of two intervals for disjunctions (||)
        return Interval(min(self.l, other.l), max(self.r, other.r))

    def __repr__(self):
        l_str = "-inf" if self.l == float('-inf') else str(self.l)
        r_str = "inf" if self.r == float('inf') else str(self.r)
        return f"[{l_str}, {r_str}]"

    def to_tuple(self):
        return (self.l, self.r)


def merge_pieces(pieces):
    # Collapse overlapping/touching Interval pieces into a minimal disjoint
    # set, so duplicate/overlapping pieces (e.g. [[0,inf],[0,inf]]) don't
    # double-count length or get treated as distinct alternatives.
    merged = []
    for iv in sorted(pieces, key=lambda iv: iv.l):
        if merged and iv.l <= merged[-1].r:
            merged[-1] = Interval(merged[-1].l, max(merged[-1].r, iv.r))
        else:
            merged.append(Interval(iv.l, iv.r))
    return merged

#A path is a sequence of time-interval mappings for each variable
class Path:
    def __init__(self, timeline):
        # timeline: {t: {var: Interval}}
        self.timeline = timeline

    def add_interval(self, t, var, interval):
        if t not in self.timeline:
            self.timeline[t] = {}
            self.timeline[t][var] = interval
        else:
            #If t already exists, either we pass or we are instantiating an empty variable
            if var not in self.timeline[t]:
                self.timeline[t][var] = interval
            else:
               print(f"Warning: Possible overwriting of existing interval for variable '{var}' at time {t}.")
               
    def copy(self):
        new_tl = {t: {v: Interval(val.l, val.r) for v, val in vars.items()} 
                  for t, vars in self.timeline.items()}
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

def parse_inequality_to_interval(op, val_str):
    val = float(val_str)
    if op in ('>', '>='): return Interval(val, float('inf'))
    elif op in ('<', '<='): return Interval(float('-inf'), val)
    elif op == '==': return Interval(val, val)
    return Interval(float('-inf'), float('inf'))

def invert_operator(op):
    """
    Returns the logically negated (complement) operator 
    for a given mathematical inequality.
    """
    mapping = {
        '>': '<=',
        '>=': '<',
        '<': '>=',
        '<=': '>',
        '==': '!='
    }
    return mapping.get(op, '==')

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


def get_immediate_constraints(node):
    #identify atomic constraints in the node formulas and store them in a temporry structure
    immediate_constraints = {}
    for formula in node.formulas:
        #Extract atomic constraints using regex
        ineq_pattern = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|>|<|==)\s*([+-]?\d+(?:\.\d+)?)$')
        matches = ineq_pattern.findall(formula)
        for var, op, val in matches:
            if op in ('>', '>='):
                immediate_constraints[var] = Interval(float(val), float('inf'))
            elif op in ('<', '<='):
                immediate_constraints[var] = Interval(float('-inf'), float(val))
            elif op == '==':
                immediate_constraints[var] = Interval(float(val), float(val))
            else:
                # Calculate the complement interval for op 
                pass
    
    return immediate_constraints

def advance_paths(paths, t, constraints):
    if constraints is None or not constraints:
        return paths  # No constraints to apply, return original paths
    new_paths = []
    for path in paths:
        new_path = path.copy()
        for var, interval in constraints.items():
            new_path.add_interval(t, var, interval)
        new_paths.append(new_path)
    return new_paths

def merge_paths(left_paths, right_paths):
    merged_paths = []
    for left in left_paths:
        for right in right_paths:
            merged_timeline = {}
            all_times = set(left.timeline.keys()).union(right.timeline.keys())
            for t in all_times:
                merged_timeline[t] = {}
                if t in left.timeline:
                    merged_timeline[t].update(left.timeline[t])
                if t in right.timeline:
                    for var, interval in right.timeline[t].items():
                        if var in merged_timeline[t]:
                            # Merge intervals for the same variable
                            merged_interval = merged_timeline[t][var].union(interval)
                            merged_timeline[t][var] = merged_interval
                        else:
                            merged_timeline[t][var] = interval
            merged_paths.append(Path(merged_timeline))
    return merged_paths

#Traverse the tree and standardize paths based on the discovered nodes
def standardize(root, all_vars):
    all_times = set()
    def collect_times(n):
        all_times.add(n.t)
        for c in n.children:
            collect_times(c)
    collect_times(root)

    def node_own_constraints(node):
        # Extract atomic var/op/val constraints directly owned by this node, tolerating
        # a leading temporal-operator prefix (e.g. "G[0,2] x > 0"). Disjunctions ("||")
        # are already decomposed into separate child nodes elsewhere in the tree, so a
        # formula line containing "||" is skipped here rather than misread as a
        # conjunction. Conjunctions ("&&") are NOT decomposed into children, so each
        # conjunct is extracted independently (all hold simultaneously).
        prefix_pattern = re.compile(r'^\(?O?[FGU]\[\d+,\d+\]\)?\s*')
        atom_pattern = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|>|<|==)\s*([+-]?\d+(?:\.\d+)?)$')
        result = {}
        for formula in node.formulas:
            stripped = prefix_pattern.sub('', formula).strip()
            if '||' in stripped:
                continue
            inner = stripped
            if inner.startswith('(') and inner.endswith(')'):
                inner = inner[1:-1]
            clauses = [c.strip() for c in inner.split('&&')] if '&&' in inner else [inner]
            for clause in clauses:
                m = atom_pattern.match(clause)
                if m:
                    var, op, val = m.groups()
                    iv = parse_inequality_to_interval(op, val)
                    if var in result:
                        prev = result[var]
                        iv = Interval(max(prev.l, iv.l), min(prev.r, iv.r))
                    result[var] = iv
        return result

    def is_leaf(node):
        return not node.children

    def explicit_vars_at(timelines, t):
        # Union of explicitly-constrained variables at time t, across alternative timelines
        combined = {}
        for tl in timelines:
            for var, intervals in tl.get(t, {}).items():
                combined.setdefault(var, []).extend(intervals)
        return combined

    def complement_pieces(intervals):
        # Complement of the union of `intervals` (a witness constraint, possibly a merged
        # multi-piece signal set), computed exactly via De Morgan: complement(A u B u ...)
        # = complement(A) n complement(B) n ..., reusing Interval.intersect. This avoids
        # over-approximating by merging unrelated ranges (e.g. complementing (0,inf) yields
        # (-inf,0], not the whole real line).
        per_interval_complements = []
        for iv in intervals:
            pieces = []
            if iv.l != float('-inf'):
                pieces.append(Interval(float('-inf'), iv.l))
            if iv.r != float('inf'):
                pieces.append(Interval(iv.r, float('inf')))
            per_interval_complements.append(pieces)
        result = per_interval_complements[0] if per_interval_complements else []
        for pieces in per_interval_complements[1:]:
            result = [inter for a in result for b in pieces if (inter := a.intersect(b)) is not None]
        return result or [Interval(float('-inf'), float('inf'))]

    def recurse(node):
        # Returns a list of sparse timelines: [{t: {var: [Interval, ...]}}, ...]
        if is_leaf(node):
            slot = {var: [iv] for var, iv in node_own_constraints(node).items()}
            return [{node.t: slot}]

        if len(node.children) > 2:
            print(f"Error: Node {node.id} has more than 2 children. This may not be a binary tree.")
            sys.exit(1)

        if len(node.children) == 1:
            child_tls = recurse(node.children[0])
            own = node_own_constraints(node)
            if not own:
                return child_tls
            result = []
            for tl in child_tls:
                new_tl = {t: dict(v) for t, v in tl.items()}
                slot = dict(new_tl.get(node.t, {}))
                for var, iv in own.items():
                    slot.setdefault(var, []).append(iv)
                new_tl[node.t] = slot
                result.append(new_tl)
            return result

        # Two children
        left, right = node.children
        left_tls, right_tls = recurse(left), recurse(right)
        left_adv = any(t > node.t for tl in left_tls for t in tl)
        right_adv = any(t > node.t for tl in right_tls for t in tl)

        if not left_adv and not right_adv:
            left_vars = explicit_vars_at(left_tls, node.t)
            right_vars = explicit_vars_at(right_tls, node.t)
            same_single_var = (set(left_vars) == set(right_vars) and len(left_vars) <= 1
                                and len(left_tls) == 1 and len(right_tls) == 1)
            if same_single_var:
                # Same variable, same instant -> merge into one path with a list of intervals
                merged = {t: dict(v) for t, v in left_tls[0].items()}
                slot = dict(merged.get(node.t, {}))
                for var, ivs in right_tls[0].get(node.t, {}).items():
                    slot[var] = slot.get(var, []) + ivs
                merged[node.t] = slot
                return [merged]
            return left_tls + right_tls  # Different variables -> keep as separate paths

        if left_adv and right_adv:
            return left_tls + right_tls  # No clear witness/continuation relation -> keep separate

        # One side stays at this instant (witness), the other advances in time (continuation):
        # the continuation implies the witness constraint does NOT hold yet at this instant.
        witness_tls, continue_tls = (right_tls, left_tls) if left_adv else (left_tls, right_tls)
        witness = explicit_vars_at(witness_tls, node.t)
        adjusted = []
        for tl in continue_tls:
            new_tl = {t: dict(v) for t, v in tl.items()}
            slot = dict(new_tl.get(node.t, {}))
            for var, ivs in witness.items():
                slot[var] = complement_pieces(ivs)
            new_tl[node.t] = slot
            adjusted.append(new_tl)
        return witness_tls + adjusted

    raw = recurse(root)
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
    # Regex with 3 groups: variable, operator, value
    ineq_pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:>=|<=|>|<|==)\s*[+-]?\d+(?:\.\d+)?')
    
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

def generate_signal_space_from_formula(formula, tabex_root=None, extra_args=None, all_vars=None):
    # Full pipeline: formula string -> stlsat tableau -> tree -> standardized paths.
    # `all_vars` defaults to this formula's own variables, but a comparison
    # between two formulas must pass the *joint* variable set (Definition
    # 5/6: an axis is active for the comparison if either side constrains
    # it) -- see similarity/stl_similarity.py's calc_similarity_from_formulas.
    dot_content = run_stlsat(formula, tabex_root, extra_args)
    root = build_tree_from_dot(dot_content)
    if all_vars is None:
        all_vars = discover_all_variables(dot_content)
    return standardize(root, all_vars)

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


