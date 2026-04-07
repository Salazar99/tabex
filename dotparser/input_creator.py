import pydot
import sys
import subprocess
import os
import re
import json

TABEX_ROOT = os.environ.get("TABEX_ROOT", "~/tabex")  # Default to current working directory if not set
class NodeObj:
    def __init__(self, time_instant, formulas, original_string):
        self.time_instant = time_instant
        self.formulas = formulas
        self.original_string = original_string

class FormulaBounds:
    def __init__(self,formula_name=None, variables=None):
        self.variables = variables # set of variables appearing in the formulas,
        self.formula_name = formula_name
        self.bounds = {} # time_instant: list of constraints
        
    def add_constraints(self, path_id, constraints):
        #if it is a new path
        if path_id not in self.bounds:
            self.bounds[path_id] = {}
            self.bounds[path_id][constraints[0]] = constraints[1] #constraints is a tuple (time_instant, list of constraints)
        else:    
            #if it is a new time instant for the path, add the constraints, otherwise extend the existing constraints for that time instant
            if not self.bounds[path_id].get(constraints[0]):
                self.bounds[path_id][constraints[0]] = constraints[1] #constraints is a tuple (time_instant, list of constraints)
            else:
                self.bounds[path_id][constraints[0]].extend(constraints[1])
            
    def __str__(self):
        ret_str = ""
        ret_str += f"Formula: {self.formula_name}\n"
       # Sort the bounds by time instant and format them for output
        for path_id, constraints in sorted(self.bounds.items()):
            ret_str += f"Path ID: {path_id}\n"
            for time,constraint in sorted(constraints.items()):
                ret_str += f"t: {time} "
                ret_str += f"{constraint} \n"
        return ret_str
    
    def to_json_str(self):
        # Reconstruct into a list-based format for better portability
        formatted_data = {
            "formula": self.formula_name,
            "vars": list(self.variables),
            "paths": []
        }

        for path_id, time_steps in sorted(self.bounds.items()):
            path_entry = {
                "path_id": path_id,
                "trace": []
            }
            for t, constraints in sorted(time_steps.items()):
                path_entry["trace"].append({
                    "t": t,
                    "constraints": constraints
                })
            formatted_data["paths"].append(path_entry)

        return json.dumps(formatted_data, indent=4)


# Function to call stlsat with the specified arguments and generate the .dot file
def call_stlsat(input_file):
    argumetns = ["--graph-output", "tmp.dot", "--no-jump-rule", "--no-formula-simplifications", "--no-formula-optimizations"]
    
    result = subprocess.run(["cargo", "run", "--release", input_file] + list(argumetns), capture_output=True, text=True, cwd=f"{TABEX_ROOT}/m_stlsat")
    if result.returncode != 0:
        print("Error running stlsat:", result.stderr)
        sys.exit(1)
    else:
        if False: #debug print
            print("stlsat run successfully")

#regex to get time from a label node
time_regex = r"t\s*=\s*(\d+)"
#node_formula_regex = r"Formula:\s*(.*)"
node_formula_regex = r"\(\d+\)\s*\|\s*(.*)"

simple_expression_regex = r"(\w+)\s*(<=|>=|<|>|=)\s*(\d+)"

# Parse label string to extract time instant, formulas and original string
def sanitize_label(label):
    # Extract time instant using regex
    time_instant = None
    match = re.search(time_regex, label)
    if match:
        time_instant = int(match.group(1))
    else: 
        print(f"Error: Time instant not found in label '{label}'")
        sys.exit(1)
    
    # Extract formulas.    
    formulas = []        
    matches = re.finditer(node_formula_regex, label)
    for match in matches:
        formula = match.group(1).strip()
        formulas.append(formula)
        
    return NodeObj(time_instant, formulas.copy(), original_string=label)

# Parse the .dot file to extract nodes and edges, and store them in a structured format
def parse_dot_tableau(file_path):
    # Load the graph from the .dot file
    graphs = pydot.graph_from_dot_file(file_path)
    graph = graphs[0]

    tableau_data = {
        "nodes": {},      # node_id: label_obj
        "edges": [],      # (source_id, destination_id)
        "parent_map": {}, # child_id: parent_id
        "leaves": [],      # list of node_ids that have no children
        "root": None,      # node_id of the root node (Node0)
        "simple_expressions": [], # node_id: list of simple expressions in the tableau (e.g., x <= 5)
        "max_time_instant": 0, # maximum time instant found in the tableau, useful for adding undefined constraints
        "starting_time": 0, #depends on the formula, we need to parse it from the root node, default is 0  
        "formula_name": ""
    }
    
    # 1. Extract Nodes
    for node in graph.get_nodes():
        node_id = node.get_name().strip('"')
        if node_id in ['node', 'graph', 'edge']:
            continue
            
        label = node.get_attributes().get('label', node_id)
        clean_label = label.strip('"').replace('\\n', '\n')
        
        # Store the sanitized object (time, formulas, etc.)
        tableau_data["nodes"][node_id] = sanitize_label(clean_label)
        # Update max time instant
        if tableau_data["nodes"][node_id].time_instant > tableau_data["max_time_instant"]:
            tableau_data["max_time_instant"] = tableau_data["nodes"][node_id].time_instant

    # 2. Extract Edges and build the Parent Map
    sources = set()
    destinations = set()

    for edge in graph.get_edges():
        src = edge.get_source().strip('"')
        dst = edge.get_destination().strip('"')
        
        tableau_data["edges"].append((src, dst))
        tableau_data["parent_map"][dst] = src 
        sources.add(src)
        destinations.add(dst)

    # 3. Calculate Leaves
    # A leaf is a node that appears as a destination but never as a source
    # We use .keys() to ensure we check all known nodes in the graph
    all_node_ids = set(tableau_data["nodes"].keys())
    tableau_data["leaves"] = list(all_node_ids - sources)

    # 4. Identify the Root Node
    # The root node is the one that is a source but never a destination
    tableau_data["root"] = None
    for node_id in tableau_data["nodes"]:
        if node_id in sources and node_id not in destinations:
            tableau_data["root"] = node_id
            tableau_data["formula_name"] = tableau_data["nodes"][node_id].formulas[0] if tableau_data["nodes"][node_id].formulas else ""
            break
    if tableau_data["root"] is None:
        print("Error: Root node not found.")
        sys.exit(1)
        
    #4.2 get starting time from root node formula
    root_formula = tableau_data["nodes"][tableau_data["root"]].formulas[0]    
    #We need the leftmost value in []     
    match = re.search(r'\[(\d+),\d+\]', root_formula)
    if match:
        tableau_data["starting_time"] = int(match.group(1))
    else:
        print(f"Error: Starting time not found in root formula '{root_formula}'")
        sys.exit(1)

    # 5. Extract simple expressions for the root
    root_node = tableau_data["nodes"][tableau_data["root"]]
    simple_expressions = []
    for formula in root_node.formulas:
        matches = re.findall(simple_expression_regex, formula)
        if matches:
            for match in matches:
                simple_expressions.append(match[0] + " " + match[1] + " " + match[2])
    tableau_data["simple_expressions"]= simple_expressions


    return tableau_data
    

# Function to get the bounds for a given time instant based on the constraints from the formulas in the nodes along the path
def get_bounds(tableau_data, signal_constraints, time_instant, formulas):
    #Check if we are in the leaf node, if so return the formula as it is a constraint 
    if not bool(signal_constraints):
        ret = formulas
        #Check for not defined contraints on other variables
        for expression in tableau_data["simple_expressions"]:
            if expression not in formulas:
                ret.append(f"!({expression})") #if not defined in current node, add it as undefined
        #If the root has y > 0 and node contains for example only x < 5 and nothing is said about y, we add !(y > 0)   
        return ret        
    else:
        #We are not in a leaf node
        #If the contraints are repeated we return the same constraints, otherwise we negate them  
        current_constraints = []
        for constraint in signal_constraints[time_instant+1]:
            if constraint in formulas:
                #if defined in current node, add it
                current_constraints.append(constraint)
            else:
                #if not defined in current node, add its negation
                if constraint.startswith("!"):
                    #if already negated we don't negate it again
                    current_constraints.append(constraint)
                else:
                    current_constraints.append(f"!({constraint})")
        
        return current_constraints
        
# Process the raw tableau data to extract constraints and create the output format
def process_data(tableau_data):
    
    """"Algorithm idea: Explore all the paths from root to leaf nodes
        #Define the constraints for each variable based on the formulas in the nodes along the path
        #Combine all paths to get the complete set of "signals" that satisfy the original STL formula
        #Constraints in the same path are combined with AND, while constraints from different paths are combined with OR for each time instant.
    """    
    variables = set()
    for simple_expression in tableau_data["simple_expressions"]:
        var = simple_expression[0]
        variables.add(var)
        
    formula_bounds = FormulaBounds(tableau_data["formula_name"], variables)
     
    #Node 0 is always the root node, so we start from there
    #Explore all paths from the leaves to node 0 (root) using the parent map
    
    #Keeps track of which contraints are define of each path, usefull for output formatting
    path_id = 0
    for leaf in tableau_data["leaves"]:
        current_node = leaf
        path_constraints = {}  # time_instant: list of constraints
        instant_constraints = []  # List of constraints for the current time instant
            
        # Traverse up the tree    
        while current_node in tableau_data["parent_map"]:
            node_obj = tableau_data["nodes"][current_node]
           
            #Multiple nodes for the same time instant but not all are usefull
            time_instant = node_obj.time_instant     
           
            if time_instant < tableau_data["starting_time"]:
                #We are before the starting time, we can ignore these constraints as they are not relevant for the formula evaluation
                #current_node = tableau_data["parent_map"][current_node]
                finished = True
                break 
                      
            if time_instant not in path_constraints:
                #get the constraints for this time instant based on the formulas in the node and previous constraints          
                path_constraints[time_instant] = get_bounds(tableau_data,path_constraints,time_instant, node_obj.formulas) 
           
            current_node = tableau_data["parent_map"][current_node]
            
        if tableau_data["root"] == current_node:
            finished = True
            #We reached the root node, we can add the constraints for this path to the formula bounds
        
        if finished:
            for time_instant in path_constraints.keys():
                formula_bounds.add_constraints(path_id, (time_instant,path_constraints[time_instant]))

        path_id += 1

    # Return the bounds formatted in some way to be written in a file.
    return formula_bounds

# Add undefined constraints for variables that are not defined in the current node but are defined in the root node
# Undefined vars are added also for the time instants not covered by the path
# For example, if path is defined until time 2 but the whole horizon is 5, we add undefined constraints for time instants 3,4,5
def add_undefined(bounds, tableau_data):
    #Get max time instant 
    max_time_instant = tableau_data["max_time_instant"]
    starting_time = tableau_data["starting_time"]
    #get simple expressions from the root node
    root_simple_expressions = tableau_data["simple_expressions"]
    for path_id, constraints in bounds.bounds.items():
        defined_time_instants = set()
        for constraint in constraints:
            defined_time_instants.add(constraint)
        
        #Add undefined constraints for time instants not covered by the path
        for time_instant in range(starting_time, max_time_instant + 1):
            if time_instant not in defined_time_instants:
                undefined_constraints = []
                for expression in root_simple_expressions:
                    undefined_constraints.append(f"(Undefined:{expression[0]})")
                bounds.add_constraints(path_id, (time_instant, undefined_constraints))
    
    return bounds
    
    
# Take the raw tableau data and gather the constaints 
def gather_constraints(input_file):
    
    #1 run stlsat to generate the .dot file
    call_stlsat(input_file)

    #2 parse the .dot file to extract tableau data    
    if os.path.exists(f"{TABEX_ROOT}/m_stlsat/tmp.dot"):
        tableau_data = parse_dot_tableau(f"{TABEX_ROOT}/m_stlsat/tmp.dot")
        os.remove(f"{TABEX_ROOT}/m_stlsat/tmp.dot")  # Clean up the temporary .dot file
    else:
        print("Error: Generated .dot file not found.")
        sys.exit(1)
    
    #3 process the tableau_data 
    bounds = process_data(tableau_data) 
    
    #4 add undefined contraints on bounds
    return add_undefined(bounds, tableau_data)
    
#Used to generate formula volume using a .dot file from another script
def generate_volumes(input_file,output_file=None):
    bounds = gather_constraints(input_file)
    
    #debug print 
    #print(bounds)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(bounds.to_json_str())

    # Process and write to output file
    return bounds.to_json_str()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tabex.py <input.stl> <output.json>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    bounds = gather_constraints(input_file)

    #debug print 
    print(bounds)

    # Process and write to output file
    with open(output_file, 'w') as f:
        f.write(bounds.to_json_str())