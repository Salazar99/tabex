import argparse
import os
from pathlib import Path
import sys
from similarity.stl_similarity import calc_similarity
from dotparser.input_creator import generate_volumes

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare the similarity of two formulas."
    )
    parser.add_argument("formula1", help="First formula")
    parser.add_argument("formula2", help="Second formula")
    parser.add_argument(
        "--save-volumes",
        action="store_true",
        help="Keep the temporary STL files after running.",
    )
    args = parser.parse_args()
    filepath1 = Path("tmp1.stl")
    filepath2 = Path("tmp2.stl")
    #0.1 Create the tmp.stl files for both formulas
    if not filepath1.is_file():
        with open("tmp1.stl", "w") as f:
            f.write(args.formula1)
    if not filepath2.is_file():
        with open("tmp2.stl", "w") as f:
            f.write(args.formula2)

    try:
        #1 call input_creator to get the two formulas volumes
        volume1 = generate_volumes(os.path.abspath("tmp1.stl"), f"{args.formula1}_volume.json" if args.save_volumes else None)
        volume2 = generate_volumes(os.path.abspath("tmp2.stl"), f"{args.formula2}_volume.json" if args.save_volumes else None)

        #2 call stl_similarity to get the similarity between the two volumes
        calc_similarity(volume1, volume2)
    finally:
        sys.stdout.flush()
    #    #Cleanup tmp files
    #    if not args.save_volumes:
    #        os.remove("tmp1.stl")
    #        os.remove("tmp2.stl")