import argparse
import json
from fractions import Fraction

from similarity.stl_similarity import (
    calc_similarity_from_formulas,
    signal_spaces_from_definition,
    signal_spaces_from_tableau,
)


def _serialize_paths(paths):
    # [l, r, left_open, right_open] -- the openness has to be dumped too, or
    # "x>0" and "x>=0" serialize identically.
    # Endpoints are exact rationals internally; JSON has no rational, so this
    # dump is a lossy *snapshot* and not the semantics. Nothing reads it back.
    def row(iv):
        l, r, lo, ro = iv.to_tuple()
        return [float(l), float(r), lo, ro]

    return [
        {
            str(t): {var: sorted(row(iv) for iv in ivs)
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
    parser.add_argument("--tabex-root", help="Override $TABEX_ROOT / ~/tabex (--via tableau only).")
    parser.add_argument("--D", type=Fraction, default=None,
                        help="Domain D of Definition 2: the truncation window, read "
                             "exactly (10, 10.5 and 21/2 all accepted). Must exceed "
                             "every constant occurring in either formula. Derived as "
                             "max|constant| + 1 if omitted.")
    parser.add_argument("--via", choices=("definition", "tableau"), default="definition",
                        help="Compute the signal space denotationally (default) or via stlsat's tableau.")
    args = parser.parse_args()

    if args.save_volumes:
        # Built by the SAME route as the score below -- dumping a tableau region
        # beside a denotational score would put two different computations of
        # the signal space in one output.
        if args.via == "definition":
            paths1, paths2, _ = signal_spaces_from_definition(args.formula1, args.formula2)
        else:
            paths1, paths2, _ = signal_spaces_from_tableau(
                args.formula1, args.formula2, tabex_root=args.tabex_root)
        with open(f"{args.formula1}_volume.json", "w") as f:
            json.dump(_serialize_paths(paths1), f, indent=2)
        with open(f"{args.formula2}_volume.json", "w") as f:
            json.dump(_serialize_paths(paths2), f, indent=2)

    score = calc_similarity_from_formulas(args.formula1, args.formula2,
                                          tabex_root=args.tabex_root, D=args.D,
                                          via=args.via)
    print(f"Similarity score between formula {args.formula1!r} and formula {args.formula2!r} is: {score}")
