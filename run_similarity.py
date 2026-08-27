import argparse
import json

from parse_graph import generate_signal_space_from_formula
from similarity.stl_similarity import calc_similarity_from_formulas


def _serialize_paths(paths):
    # [l, r, left_open, right_open] -- the openness has to be dumped too, or
    # "x>0" and "x>=0" serialize identically.
    return [
        {
            str(t): {var: sorted(list(iv.to_tuple()) for iv in ivs)
                     for var, ivs in sorted(path.timeline[t].items())}
            for t in sorted(path.timeline.keys())
        }
        for path in paths
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare the similarity of two formulas.")
    parser.add_argument("formula1", help="First formula")
    parser.add_argument("formula2", help="Second formula")
    parser.add_argument(
        "--save-volumes",
        action="store_true",
        help="Save each formula's standardized signal space to a .json file.",
    )
    parser.add_argument("--tabex-root", help="Override $TABEX_ROOT / ~/tabex.")
    args = parser.parse_args()

    paths1 = generate_signal_space_from_formula(args.formula1, tabex_root=args.tabex_root)
    paths2 = generate_signal_space_from_formula(args.formula2, tabex_root=args.tabex_root)

    if args.save_volumes:
        with open(f"{args.formula1}_volume.json", "w") as f:
            json.dump(_serialize_paths(paths1), f, indent=2)
        with open(f"{args.formula2}_volume.json", "w") as f:
            json.dump(_serialize_paths(paths2), f, indent=2)

    score = calc_similarity_from_formulas(args.formula1, args.formula2, tabex_root=args.tabex_root)
    print(f"Similarity score between formula {args.formula1!r} and formula {args.formula2!r} is: {score}")
