import sys

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

#class that contains the volume of an STL formula
#Volume is a collection of paths
class FormulaVolume:
    def __init__(self, formula_name):
        self.formula_name = formula_name
        self.volume = []

    def add_path(self, path):
        self.volume.append(path)

#Parse the input files to instantiate the volume of the STL formula
def extract_volume_from_bounds(bounds):
    
    return None


def compute_similarity(volume1, volume2):
    return None

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python stl_similarity.py <bounds_file_formula1> <bounds_file_formula2>")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        bounds1 = f.read().strip()
    with open(sys.argv[2], 'r') as f:
        bounds2 = f.read().strip()

    formula_volume1 = extract_volume_from_bounds(bounds1)
    formula_volume2 = extract_volume_from_bounds(bounds2)

    print(f"Volume of formula 1: {formula_volume1}")
    print(f"Volume of formula 2: {formula_volume2}")