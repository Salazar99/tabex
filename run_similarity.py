import argparse
import json

from parse_graph import generate_signal_space_from_formula
from similarity.stl_similarity import build_volume_from_paths, compute_similarity


def _serialize_paths(paths):
    return [
        {
            str(t): {var: sorted([iv.l, iv.r] for iv in ivs) for var, ivs in sorted(path.timeline[t].items())}
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

    volume1 = build_volume_from_paths(args.formula1, paths1)
    volume2 = build_volume_from_paths(args.formula2, paths2)
    score = compute_similarity(volume1, volume2)
    print(f"Similarity score between formula {args.formula1!r} and formula {args.formula2!r} is: {score}")
