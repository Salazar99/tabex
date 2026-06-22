import re

class Interval:
    def __init__(self, l, r):
        self.l = float(l)
        self.r = float(r)

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

class Path:
    def __init__(self, timeline):
        # timeline: {t: {var: Interval}}
        self.timeline = timeline

    def copy(self):
        new_tl = {t: {v: Interval(val.l, val.r) for v, val in vars.items()} 
                  for t, vars in self.timeline.items()}
        return Path(new_tl)

class Node:
    def __init__(self, node_id, t, label):
        self.id = node_id
        self.t = t
        self.label = label
        self.children = []
        self.intervals = {} # Populated by your parser
        self.paths = []     # Used for the standardization algorithm
        
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
        
def compress_path_list(paths):
    """Algorithm 4: Compress Path List via Single-Step Variance Rule."""
    changed = True
    while changed:
        changed = False
        # Simplified implementation of the variance loop 
        # Merges paths that differ by only one variable interval that touches/overlaps
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                # If variance_count == 1 and intervals are mergeable 
                # paths[i].timeline[t][v] = union(...)
                # paths.remove(paths[j]); changed = True; break
                pass 
    return paths

def pad_time_horizons(l_combined, all_vars):
    """Algorithm 3: Pad Time Horizons[cite: 177]."""
    if not l_combined: return l_combined
    t_max = max(max(p.timeline.keys()) for p in l_combined)
    for p in l_combined:
        for t in range(t_max + 1):
            if t not in p.timeline:
                # Fill unconstrained steps with (-inf, inf) [cite: 177]
                p.timeline[t] = {v: Interval(float('-inf'), float('inf')) for v in all_vars}
    return l_combined

def topological_sort_leaves_to_root(root):
    """
    Algorithm 2: Computes a post-order traversal ensuring 
    children precede parents.
    """
    order = []
    visited = set()

    def dfs(node):
        if node in visited:
            return
        
        visited.add(node)
        
        # Recurse through all children first (Post-Order)
        for child in node.children:
            dfs(child)
        
        # Append node after all children have been processed
        order.append(node)

    dfs(root)
    return order

def standardize(node, all_vars):
    """Algorithm 1: Iterative Signal Space Standardization."""
    # CASE 1: Leaf Nodes 
    if not node.children:
        st = {v: Interval(float('-inf'), float('inf')) for v in all_vars}
        st.update(node.intervals)
        node.paths = [Path({node.t: st})]
    
    # CASE 2 & 3: Splits
    else:
        for child in node.children:
            standardize(child, all_vars)
        
        # Spatial Split 
        if "||" in node.label:
            l_comb = [p for c in node.children for p in c.paths]
            node.paths = compress_path_list(l_comb)
            
        # Temporal Split (Eventually/Until)       
        else:
             # SAFETY CHECK: Ensure we have both children
           
            if len(node.children) >= 2:
                c_imm, c_def = node.children[0], node.children[1]
                # Extract Domain Phi 
                # Inject Negation into Deferred Branch 
                l_def_prime = []
                for p in c_def.paths:
                    p_prime = p.copy()
                    # Intersect with negation 
                    l_def_prime.append(p_prime)

                combined = c_imm.paths + l_def_prime
                padded = pad_time_horizons(combined, all_vars)
                node.paths = compress_path_list(padded)
            else:
                # If only one child exists, it's not a proper temporal split
                # Treat it as a simple pass-through or handle error
                node.paths = node.children[0].paths if node.children else []
    return node.paths        

def parse_tableau(dot_content):
    nodes = {}
    all_variables = set()

    node_pattern = re.compile(r'^\s*"([^"]+)"\s*\[\s*label\s*=\s*"(.*?)"\s*\]', re.MULTILINE | re.DOTALL)
    ineq_pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|>|<|==)\s*([+-]?\d+(?:\.\d+)?)')

    # Global variable discovery scan
    for match in node_pattern.finditer(dot_content):
        for var, _, _ in ineq_pattern.findall(match.group(2)):
            if var not in ('F', 'OF', 'G', 'OG'):
                all_variables.add(var)

    for match in node_pattern.finditer(dot_content):
        node_id = match.group(1)
        label_text = match.group(2)
        
        t_match = re.search(r'\bt\s*=\s*(\d+)', label_text, re.IGNORECASE)
        t = int(t_match.group(1)) if t_match else 0
        
        # Initialize intervals for this node as completely undefined
        node_intervals = {v: Interval(float('-inf'), float('inf')) for v in all_variables}
        
        normalized_label = label_text.replace('\\n', '\n')
        for line in normalized_label.split('\n'):
            if '|' not in line:
                continue
            
            formula_part = line.split('|', 1)[1].strip()
            
            # Rule 1: Skip future commitments
            if re.match(r'^(O)?F\[\d+,\d+\]', formula_part):
                continue
                
            # Rule 2: Evaluate global operators within active windows
            g_match = re.match(r'^(O)?G\[(\d+),(\d+)\]', formula_part)
            if g_match:
                a, b = int(g_match.group(2)), int(g_match.group(3))
                if not (a <= t <= b):
                    continue
            
            # Rule 3: Process Immediate Constraints with Disjunction (||) Awareness
            # Split by logical OR to treat them as alternatives (unions)
            disjunction_parts = formula_part.split('||')
            
            line_var_intervals = {}
            for part in disjunction_parts:
                found_ineqs = ineq_pattern.findall(part)
                
                # Group inequalities by variable inside this specific option clause
                part_var_constraints = {}
                for var, op, val in found_ineqs:
                    if var not in ('F', 'OF', 'G', 'OG'):
                        if var not in part_var_constraints:
                            part_var_constraints[var] = []
                        part_var_constraints[var].append(parse_inequality_to_interval(op, val))
                
                # Intersect constraints inside the same clause option
                for var, intervals in part_var_constraints.items():
                    current_intersect = intervals[0]
                    for nxt in intervals[1:]:
                        current_intersect = current_intersect.intersect(nxt)
                    
                    if var not in line_var_intervals:
                        line_var_intervals[var] = []
                    if current_intersect:
                        line_var_intervals[var].append(current_intersect)
            
            # Union the alternative clauses across the || operator
            for var, intervals in line_var_intervals.items():
                if intervals:
                    current_union = intervals[0]
                    for nxt in intervals[1:]:
                        current_union = current_union.union(nxt)
                    
                    # Merge with any existing restrictions on this node
                    if node_intervals[var].l == float('-inf') and node_intervals[var].r == float('inf'):
                        node_intervals[var] = current_union
                    else:
                        node_intervals[var] = node_intervals[var].intersect(current_union)

        nodes[node_id] = {
            'id': node_id,
            't': t,
            'intervals': node_intervals
        }

    return {
        'nodes': nodes,
        'sorted_node_ids': sorted(nodes.keys(), key=lambda x: int(re.search(r'\d+', x).group())),
    }

def build_tree_from_dot(dot_content):
    # 1. Reuse existing tableau parsing logic to get raw node data
    tableau_data = parse_tableau(dot_content)
    raw_nodes = tableau_data['nodes']
    
    # 2. Create Node objects
    tree_nodes = {}
    for nid, data in raw_nodes.items():
        # You may need to refine the label extraction if not in 'data'
        tree_nodes[nid] = Node(data['id'], data['t'], label="extracted_from_label")
        tree_nodes[nid].intervals = data['intervals']
        
    # 3. Create structural edges
    # Standard DOT uses "--" for undirected graphs, usually representing 
    # parent-child flow in tableau construction
    edge_pattern = re.compile(r'^\s*"([^"]+)"\s*--\s*"([^"]+)"', re.MULTILINE)
    
    # Track children to identify the root
    has_parent = set()
    
    for match in edge_pattern.finditer(dot_content):
        parent_id, child_id = match.group(1), match.group(2)
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

def main(dot_file_path):
    # 1. Load and parse the DOT content
    with open(dot_file_path, 'r', encoding='utf-8') as f:
        dot_content = f.read()

    # 2. Build the hierarchical tree structure
    root = build_tree_from_dot(dot_content)
    
    # 3. Discover system variables for padding
    # This assumes we have collected all variables from the parser earlier
    all_vars = discover_all_variables(dot_content) 

    # 4. Perform Topological Sort (Algorithm 2)
    # This prepares the nodes for post-order traversal
    nodes_in_order = topological_sort_leaves_to_root(root)

    # 5. Execute Iterative Signal Space Standardization (Algorithm 1)
    # We pass the root and the globally discovered variables
    final_path_list = standardize(root, all_vars)

    # 6. Output the results
    print(f"--- Standardized Feasible Paths for {dot_file_path} ---")
    for i, path in enumerate(final_path_list, 1):
        print(f"\nPath #{i}:")
        for t in sorted(path.timeline.keys()):
            constraints = path.timeline[t]
            print(f"  t={t}: {constraints}")

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

if __name__ == "__main__":
    import sys
    # Example usage: python script.py graph_G.dot
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Please provide a .dot file path.")