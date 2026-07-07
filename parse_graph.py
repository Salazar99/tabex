import re

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

def parse_tableau(dot_content):
    nodes = {}
    
    node_pattern = re.compile(r'^\s*"([^"]+)"\s*\[\s*label\s*=\s*"(.*?)"\s*\]', re.MULTILINE | re.DOTALL)
    # Optimized to ignore (N) or (N) -> (Y) and capture the actual formula
    formula_strip_pattern = re.compile(r'\(.*?\)(?:\s*→\s*\(.*?\))?\s*\|\s*(.*)')
    ineq_pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|>|<|==)\s*([+-]?\d+(?:\.\d+)?)')

    for match in node_pattern.finditer(dot_content):
        node_id = match.group(1)
        label_text = match.group(2)
        
        t_match = re.search(r'\bt\s*=\s*(\d+)', label_text, re.IGNORECASE)
        t = int(t_match.group(1)) if t_match else 0
        
        node_properties = {}
        node_formulas = []
        
        normalized_label = label_text.replace('\\n', '\n')
        for line in normalized_label.split('\n'):
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
    # 1. Reuse existing tableau parsing logic to get raw node data
    tableau_data = parse_tableau(dot_content)
    raw_nodes = tableau_data['nodes']
    
    # 2. Create Node objects
    tree_nodes = {}
    for nid, data in raw_nodes.items():
        # Correctly passing the real label from the parsed data
        tree_nodes[nid] = Node(data['id'], data['t'], label=data.get('label', ''), properties=data['properties'], formulas=data['formulas'])
        
        
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
    #If the root has no children, I am in a leaf node, so I will return the single constraint
    if not root.children:
        #Get intervals from properties of the node
        timeline = {}
        for var in all_vars:
            if var in root.properties:
                #Assuming properties[var] is a list of constraints, we will take the first one for simplicity
                constraint = root.properties[var][0]
                op = re.search(r'(>=|<=|>|<|==)', constraint).group(1)
                val = re.search(r'([+-]?\d+(?:\.\d+)?)', constraint).group(1)
                interval = parse_inequality_to_interval(op, val)
                timeline[root.t] = {var: interval}
            else:
                #If the variable is not present, set it to unconstrained
                timeline[root.t] = {var: Interval(float('-inf'), float('inf'))}
        #return the path 
        return [Path(timeline)]
    
    else:
        if len(root.children) > 2:
            print(f"Error: Node {root.id} has more than 2 children. This may not be a binary tree.")
            sys.exit(1)
        else:
            current_constraints = get_immediate_constraints(root)
            
            if len(root.children) == 1:  # Assuming 'G' is the only formula in this node
                #Single child, propagate constraints
                child_paths = standardize(root.children[0], all_vars)

                #Now we need to add the current node's constraints to each of the child paths
                #Need to keep consider the time and the possible merging of paths
                if(root.t != root.children[0].t):
                    ret_paths = advance_paths(child_paths, root.t, current_constraints)
                else:
                    ret_paths = child_paths
                
            else:
                #Two children, handle disjunctions
                left_paths = standardize(root.children[0], all_vars)
                right_paths = standardize(root.children[1], all_vars)    
                
                merged_paths = merge_paths(left_paths, right_paths)
                if (root.t != root.children[0].t):  # Assuming both children have the same time
                    ret_paths = advance_paths(merged_paths, root.t, current_constraints)
                else:
                    ret_paths = merged_paths
            
            return ret_paths
        

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
    print(f"--- Standardized Feasible Paths for {dot_file_path} ---")
    for i, path in enumerate(final_path_list, 1):
        print(f"\nPath #{i}:")
        for t in sorted(path.timeline.keys()):
            constraints = path.timeline[t]
            print(f"  t={t}: {constraints}")

if __name__ == "__main__":
    import sys
    # Example usage: python script.py graph_G.dot
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Please provide a .dot file path.")        
                            

