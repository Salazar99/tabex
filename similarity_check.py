"""Interactive interface: type two STL formulas, get their similarity score."""
from similarity.stl_similarity import calc_similarity_from_formulas

QUIT_WORDS = {"quit", "exit"}


def run_comparison(formula1, formula2, tabex_root=None):
    return calc_similarity_from_formulas(formula1, formula2, tabex_root=tabex_root)


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
