"""Interactive interface: type two STL formulas, get their similarity score."""
from parse_graph import generate_signal_space_from_formula
from similarity.stl_similarity import build_aligned_volumes, compute_similarity

QUIT_WORDS = {"quit", "exit"}


def run_comparison(formula1, formula2, tabex_root=None):
    paths1 = generate_signal_space_from_formula(formula1, tabex_root)
    paths2 = generate_signal_space_from_formula(formula2, tabex_root)
    volume1, volume2 = build_aligned_volumes(formula1, paths1, formula2, paths2)
    return compute_similarity(volume1, volume2)


def main():
    print("STL Formula Similarity Checker -- type 'quit' at any prompt to exit.\n")
    while True:
        formula1 = input("First formula:  ").strip()
        if formula1.lower() in QUIT_WORDS:
            break
        formula2 = input("Second formula: ").strip()
        if formula2.lower() in QUIT_WORDS:
            break
        try:
            print(f"Similarity score: {run_comparison(formula1, formula2):.4f}\n")
        except RuntimeError as e:
            print(f"stlsat error: {e}\n")


if __name__ == "__main__":
    main()
