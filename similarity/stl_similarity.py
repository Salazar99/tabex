from ast import Set
import math
from re import findall
import sys
import json
import re 
from enum import Enum

class NumOperator(Enum):
    LT = "<" 
    GT = ">" 
    LEQ = "<=" 
    GEQ = ">=" 
    EQ = "==" 
    NEQ = "!="

#class that contains a constraint at a specific time
#variable: the variable that is constrained
#time: the time at which the constraint is applied
#left: the left bound of the constraint
#right: the right bound of the constraint
class instant_contraint:
    def __init__(self, variable, time, left, right):
        self.variable = variable
        self.time = time
        self.left = left
        self.right = right

    #return true if the constraint is bounded (both bounds are finite), false otherwise
    def is_bounded(self):
        if math.isinf(self.left) and math.isinf(self.right):
            return True
        
        return False 
    
    #return true if the constraint is undefined, false otherwise
    def is_undefined(self):
        return math.isinf(self.left) and math.isinf(self.right)
    
#class that contains the volume of an STL formula
#Volume is a collection of paths
class FormulaVolume:
    def __init__(self,horizon, formula_name, vars):
        self.horizon = horizon
        self.formula_name = formula_name
        self.vars = vars
        self.volume = []

    def add_path(self, path):
        self.volume.append(path)


#Parse the input files to instantiate the volume of the STL formula
def extract_volume_from_bounds(bounds):
    simple_expression_regex = r"(\w+)\s*(<=|>=|<|>|=)\s*(\d+)"
    # 1. initilize the volume to return 
    volume = FormulaVolume(len(bounds["paths"][0]["trace"]),bounds["formula"], bounds["vars"])
    
    # 2. Start manipulating the paths
    for path in bounds["paths"]:
        path_instance = {}
        for contraint in path["trace"]:
            time = contraint["t"]
            path_instance[time] = {}
            #constraint is a list of expressions of the form "var op value" or "Undefined:var"
            #Multiple expression could be present for the same variable at the same time, in this case we can treat them as a conjunction of constraints
            
            #Support var to create the instant_constraint instances
            #variable
            #operator
            #leftvalue
            #rightvalue
            variable_constraints = {}
            
            for expr in contraint["constraints"]:
                expr = expr.strip("()") 
                if expr.startswith("Undefined:"):
                    variable = expr.split(":")[1]
                    variable_constraints[variable] = (None, None, None)
                else:
                    negated = False
                    if expr.startswith("!"):
                        negated = True
                        expr = expr[1:] #remove the negation for parsing
                        expr = expr.strip("()")
                    # Parse the expression to extract variable, operator, and value
                    match = re.match(simple_expression_regex, str(expr))
                    if match:
                        variable = match.group(1)
                        operator = match.group(2)
                        value = int(match.group(3))
                        
                        if negated:
                            #Negate the operator
                            match operator:
                                case NumOperator.LT.value:
                                    operator = NumOperator.GEQ.value
                                case NumOperator.GT.value:
                                    operator = NumOperator.LEQ.value
                                case NumOperator.LEQ.value:
                                    operator = NumOperator.GT.value
                                case NumOperator.GEQ.value:
                                    operator = NumOperator.LT.value
                                case NumOperator.EQ.value:
                                    operator = NumOperator.NEQ.value
                                case NumOperator.NEQ.value:
                                    operator = NumOperator.EQ.value
                                case _:
                                    raise ValueError(f"Unsupported operator: {operator}")
                                    sys.exit(1)
                        
                        lvalue, rvalue = None, None
                        
                        match operator:
                            case NumOperator.LT.value:
                                #expr is var < value, so bounds is (-inf, rvalue)
                                #x < 5 and new one is x < 3 --> update rvalue to 3
                                rvalue = value
                                if variable in variable_constraints:
                                    #if it already exists and rvalue is less than the current lvalue, update it
                                    if variable_constraints[variable][1] is not None and variable_constraints[variable][1] > rvalue:
                                        variable_constraints[variable][3] = rvalue
                                    #if it already exists and lvalue is None, update it
                                    elif variable_constraints[variable][1] is None:
                                        variable_constraints[variable][3] = rvalue
                                    #Otherwise do nothing, 
                                else:
                                    variable_constraints[variable] = (operator, None, rvalue)
                            
                            case NumOperator.GT.value:
                                #expr is var > value, so bounds is (lvalue, +inf)
                                # x > 5 and new one is x > 7 --> update lvalue to 7
                                lvalue = value
                                if variable in variable_constraints:
                                    #if it already exists and lvalue is greater than the current lvalue, update it
                                    if variable_constraints[variable][1] is not None and variable_constraints[variable][1] < lvalue:
                                        variable_constraints[variable][2] = lvalue
                                    #if it already exists and lvalue is None, update it
                                    elif variable_constraints[variable][1] is None:
                                        variable_constraints[variable][2] = lvalue
                                    #Otherwise do nothing, 
                                else:
                                    variable_constraints[variable] = [operator, lvalue, None]
                            case NumOperator.LEQ.value:
                                #expr is var < value, so bounds is (-inf, rvalue)
                                #x < 5 and new one is x < 3 --> update rvalue to 3
                                rvalue = value
                                if variable in variable_constraints:
                                    #if it already exists and rvalue is less than the current lvalue, update it
                                    if variable_constraints[variable][1] is not None and variable_constraints[variable][1] > rvalue:
                                        variable_constraints[variable][3] = rvalue
                                    #if it already exists and lvalue is None, update it
                                    elif variable_constraints[variable][1] is None:
                                        variable_constraints[variable][3] = rvalue
                                    #Otherwise do nothing, 
                                else:
                                    variable_constraints[variable] = [operator, None, rvalue]
                            case NumOperator.GEQ.value:
                                #expr is var > value, so bounds is (lvalue, +inf)
                                # x > 5 and new one is x > 7 --> update lvalue to 7
                                lvalue = value
                                if variable in variable_constraints:
                                    #if it already exists and lvalue is greater than the current lvalue, update it
                                    if variable_constraints[variable][1] is not None and variable_constraints[variable][1] < lvalue:
                                        variable_constraints[variable][2] = lvalue
                                    #if it already exists and lvalue is None, update it
                                    elif variable_constraints[variable][1] is None:
                                        variable_constraints[variable][2] = lvalue
                                    #Otherwise do nothing, 
                                else:
                                    variable_constraints[variable] = [operator, lvalue, None]
                            case NumOperator.EQ.value:
                                lvalue = value
                                rvalue = value
                                variable_constraints[variable] = [operator, lvalue, rvalue]
                            case _: 
                                raise ValueError(f"Unsupported operator: {operator}")
                                sys.exit(1)
                    else:
                        raise ValueError(f"Unsupported expression format: {expr}")
                        sys.exit(1)
                    #end of expression parsing for this time instat       
            #end of expressions parsign for this time instant
            #Create the instant constraint instances for each variable
            for variable, [operator, lvalue, rvalue] in variable_constraints.items():
                if lvalue is None:
                    lvalue = float("-inf")
                if rvalue is None:
                    rvalue = float("inf") 
                path_instance[time][variable] = instant_contraint(variable, time, lvalue, rvalue)

        #end of path instance creation for this path, add it to the volume
        volume.add_path(path_instance)    
                
    return volume


def jaccard_similarity(constraint1, constraint2):
    """
    Calculates the Jaccard Index for two finite intervals.
    I and J are tuples or lists: (start, end)
    """
    # Find the intersection coordinates
    inter_start = max(constraint1.left, constraint2.left)
    inter_end = min(constraint1.right, constraint2.right)
    
    # Calculate intersection length
    intersection = max(0, inter_end - inter_start)

    # Calculate union length: Area(I) + Area(J) - Intersection
    len_i = constraint1.right - constraint1.left
    len_j = constraint2.right - constraint2.left
    union = len_i + len_j - intersection
    
    return intersection / union if union > 0 else 0.0

def distance_decay_similarity(constraint1, constraint2):
    """
    Calculates proximity similarity for intersecting, unbounded constraints.
    Used when at least one constraint is semi-infinite (e.g., x > 0).
    
    Formula: 1 / (1 + dist(I, J))
    """
    if constraint1.is_bounded() and not constraint2.is_bounded():
        # If constraint1 is bounded and constraint2 is unbounded, we can consider the distance as the distance between the finite endpoint of constraint1 and the infinite endpoint of constraint2
        threshold_c1 = (constraint1.left + constraint1.right) / 2 # we can consider the midpoint of the interval as the representative point for distance calculation
        threshold_c2 = constraint2.left if constraint2.left != float("-inf") else constraint2.right
    elif not constraint1.is_bounded() and constraint2.is_bounded():
        # If constraint1 is unbounded and constraint2 is bounded, we can consider the distance as the distance between the finite endpoint of constraint2 and the infinite endpoint of constraint1
        threshold_c1 = constraint1.left if constraint1.left != float("-inf") else constraint1.right
        threshold_c2 = (constraint2.left + constraint2.right) / 2 # we can consider the midpoint of the interval as the representative point for distance calculation
    else:
        # If both constraints are unbounded, we can consider the distance as the distance between the finite endpoints of the two constraints
        threshold_c1 = constraint1.left if constraint1.left != float("-inf") else constraint1.right
        threshold_c2 = constraint2.left if constraint2.left != float("-inf") else constraint2.right
        
    # 2. Calculate the distance-based decay
    # dist(I, J) is the Euclidean distance between finite endpoints.
    dist = abs(threshold_c1 - threshold_c2)
    
    return 1 / (1 + dist)


#Return true if the two constraints are disjuncted, false otherwise
def disjuncted(constraint1, constraint2):
    if constraint1.left >= constraint2.right or constraint2.left >= constraint1.right:
        return True
    return False

def point_similarity(constraint1, constraint2):
    #if only one of the two constraints is undefined, similarity is 0
    if constraint1.is_undefined() != constraint2.is_undefined():
        return 0.0
    #if both constraints are undefined, similarity is 1
    elif constraint1.is_undefined() == constraint2.is_undefined() == True:
        return 1.0
    #if the two constraints are disjuncted, similarity is 0
    elif disjuncted(constraint1, constraint2):
        return 0.0
    else:
        #Defined constraints similarity can be computed using different methods depending on whether the constraints are bounded or unbounded
        #bounded
        if constraint1.is_bounded() and constraint2.is_bounded():
            #Jaccard
            return jaccard_similarity(constraint1, constraint2)
        #unbounded
        else: 
            #Distance decay
            return distance_decay_similarity(constraint1, constraint2)

#Path to path similarity
def path_similarity(path1, path2, numvars, horizon):
    normalizing_factor = horizon * numvars

    time_sum = 0
    for time in range(horizon):
        var_sim_sum = 0
        for var in path1[time].keys():
            if var in path2[time]:
                #compute the similarity of the two constraints on var at this time
                constraint1 = path1[time][var]
                constraint2 = path2[time][var]
                #if one of the two constraints is undefined, similarity is 0
                var_sim_sum += point_similarity(constraint1, constraint2)
            else:
                #if var is not present in path2 at this time, we can consider it as an implicit undefined constraint, so similarity is 0
                continue
        time_sum += var_sim_sum
    return time_sum/normalizing_factor   
#One way similarity from volume1 to volume2
def one_way_similarity(volume1, volume2):
    normalizing_factor = len(volume1.volume)
    path_sim_sum = 0
    
    #compute number of unique variables in the two volumes to use as part of the normalizing factor
    uniquevars = len(set(volume1.vars).union(set(volume2.vars)))
    
    #For each path in volume1, find the best matching path in volume2 and add its similarity to the sum
    for path1 in volume1.volume:
        max_sim_path = 0
        for path2 in volume2.volume:
            max_sim_path = max(max_sim_path, path_similarity(path1, path2, uniquevars,max(volume1.horizon,volume2.horizon)))    
        
        path_sim_sum += max_sim_path
    
    print(f"One way similarity from formula: {volume1.formula_name} to formula: {volume2.formula_name} is: {path_sim_sum/normalizing_factor}")
    return path_sim_sum/normalizing_factor
#Global similarity 
def compute_similarity(volume1, volume2):
    return (one_way_similarity(volume1, volume2) + one_way_similarity(volume2, volume1))/2

#Used to run the similarity computation from another module, e.g., run_similarity.py
def calc_similarity(bounds1, bounds2):
    formula_volume1 = extract_volume_from_bounds(bounds1)
    formula_volume2 = extract_volume_from_bounds(bounds2)

    print(f"Similarity score between formula: {formula_volume1.formula_name} and formula: {formula_volume2.formula_name} is: {compute_similarity(formula_volume1, formula_volume2)}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python stl_similarity.py <bounds_file_formula1> <bounds_file_formula2>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        bounds1 = json.load(f)
    #print(bounds1)

    with open(sys.argv[2]) as f:
        bounds2 = json.load(f)
    #print(bounds2)

    formula_volume1 = extract_volume_from_bounds(bounds1)
    formula_volume2 = extract_volume_from_bounds(bounds2)

    print(f"Similarity score between formula: {formula_volume1.formula_name} and formula: {formula_volume2.formula_name} is: {compute_similarity(formula_volume1, formula_volume2)}")
