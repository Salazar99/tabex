"""Interactive interface: type two STL formulas, get their similarity score."""
from fractions import Fraction

from similarity.stl_similarity import calc_similarity_from_formulas

QUIT_WORDS = {"quit", "exit"}


def run_comparison(formula1, formula2, tabex_root=None, D=None):
    return calc_similarity_from_formulas(formula1, formula2, tabex_root=tabex_root, D=D)


def main():
    print("STL Formula Similarity Checker -- type 'quit' at any prompt to exit.\n")
    while True:
        formula1 = input("First formula:  ").strip()
        if formula1.lower() in QUIT_WORDS:
            break
        formula2 = input("Second formula: ").strip()
        if formula2.lower() in QUIT_WORDS:
            break
        domain = input("Domain D (blank = auto): ").strip()
        if domain.lower() in QUIT_WORDS:
            break
        try:
            score = run_comparison(formula1, formula2, D=Fraction(domain) if domain else None)
            print(f"Similarity score: {score:.4f}\n")
        except RuntimeError as e:
            print(f"stlsat error: {e}\n")
        except ValueError as e:
            # An ill-formed D, or a formula outside the fragment
            # (UnsupportedFormula subclasses ValueError). Report and keep the
            # loop alive -- the message says what D would be acceptable.
            print(f"{e}\n")


if __name__ == "__main__":
    main()
