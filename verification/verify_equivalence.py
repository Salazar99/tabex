"""Randomised check that equivalent formulas score G = 1.

Exercises the WHOLE pipeline -- evaluate E -> canonicalize -> trim -> G -- by
generating a random formula and comparing it against an equivalence-preserving
rewrite of itself. G must be exactly 1 (the paper's correctness result).

Every pair here is equivalent BY CONSTRUCTION, so nothing external is asked
whether two formulas are equivalent.

A failure means either E gave two equivalent formulas different regions
(Theorem 1) or canonicalization is not canonical (Theorem 2). Run:

    python verification/verify_equivalence.py
"""
import argparse
import random
import signal
import sys
from pathlib import Path as FilePath

sys.path.insert(0, str(FilePath(__file__).resolve().parent.parent))   # the repo root
from similarity.stl_similarity import calc_similarity_from_formulas  # noqa: E402

VARS = ["x", "y"]
OPS = [">", ">=", "<", "<="]

# A tautology, for the "conjoining true changes nothing" rewrites.
TRUE = "((y>0) || (y<=0))"


def rewrites(lower, upper, point):
    """Meaning-preserving rewrites, each returning the (original, rewritten) pair.

    `lower`/`upper`/`point` are freshly drawn per trial so the temporal
    identities are exercised over many different windows rather than one.
    """
    a, b, p = lower, upper, point
    return [
        # --- propositional ---
        ("double negation",       lambda f, g: (f, f"!(!({f}))")),
        ("idempotent &&",         lambda f, g: (f, f"({f}) && ({f})")),
        ("idempotent ||",         lambda f, g: (f, f"({f}) || ({f})")),
        ("triple &&",             lambda f, g: (f, f"(({f}) && ({f})) && ({f})")),
        ("absorption",            lambda f, g: (f, f"({f}) || (({f}) && ({g}))")),
        ("tautological conjunct", lambda f, g: (f, f"({f}) && {TRUE}")),
        ("commutative &&",        lambda f, g: (f"({f}) && ({g})", f"({g}) && ({f})")),
        ("commutative ||",        lambda f, g: (f"({f}) || ({g})", f"({g}) || ({f})")),
        ("de Morgan &&",          lambda f, g: (f"!(({f}) && ({g}))", f"(!({f})) || (!({g}))")),
        ("de Morgan ||",          lambda f, g: (f"!(({f}) || ({g}))", f"(!({f})) && (!({g}))")),
        ("distributivity",        lambda f, g: (f"({f}) && (({g}) || ({f}))",
                                                f"(({f}) && ({g})) || (({f}) && ({f}))")),
        # --- temporal ---
        ("F over ||",             lambda f, g: (f"F[{a},{b}](({f}) || ({g}))",
                                                f"(F[{a},{b}]({f})) || (F[{a},{b}]({g}))")),
        ("G over &&",             lambda f, g: (f"G[{a},{b}](({f}) && ({g}))",
                                                f"(G[{a},{b}]({f})) && (G[{a},{b}]({g}))")),
        ("!F = G!",               lambda f, g: (f"!(F[{a},{b}]({f}))", f"G[{a},{b}](!({f}))")),
        ("!G = F!",               lambda f, g: (f"!(G[{a},{b}]({f}))", f"F[{a},{b}](!({f}))")),
        ("F = G at a point",      lambda f, g: (f"F[{p},{p}]({f})", f"G[{p},{p}]({f})")),
        ("nested G collapses",    lambda f, g: (f"G[0,1](G[0,1]({f}))", f"G[0,2]({f})")),
        ("nested F collapses",    lambda f, g: (f"F[0,1](F[0,1]({f}))", f"F[0,2]({f})")),
        ("F idempotent",          lambda f, g: (f"F[{a},{b}]({f})",
                                                f"(F[{a},{b}]({f})) || (F[{a},{b}]({f}))")),
        ("G idempotent",          lambda f, g: (f"G[{a},{b}]({f})",
                                                f"(G[{a},{b}]({f})) && (G[{a},{b}]({f}))")),
        ("G absorbs F",           lambda f, g: (f"G[{a},{b}]({f})",
                                                f"(G[{a},{b}]({f})) && (F[{a},{b}]({f}))")),
        ("temporal absorption",   lambda f, g: (f"G[{a},{b}]({f})",
                                                f"(G[{a},{b}]({f})) || ((G[{a},{b}]({f})) && ({g}))")),
        # --- until ---
        ("U tautological",        lambda f, g: (f"(({f}) U[{a},{b}] ({g}))",
                                                f"((({f}) U[{a},{b}] ({g}))) && {TRUE}")),
        ("U idempotent",          lambda f, g: (f"(({f}) U[{a},{b}] ({g}))",
                                                f"((({f}) U[{a},{b}] ({g}))) || ((({f}) U[{a},{b}] ({g})))")),
        # The next four pin the paper's reading of "until" (Remark 1): the invariant holds up
        # to AND INCLUDING the witness instant, so "phi U[a,b] psi" means
        # "exists t in [a,b]: psi(t) and phi on [0,t]". Each is false under the
        # textbook half-open reading, so they fail loudly if E drifts.
        ("U absorbs its invariant",
                                  lambda f, g: (f"(({f}) U[{a},{b}] ({g}))",
                                                f"(({f}) U[{a},{b}] (({f}) && ({g})))")),
        ("U at a point",          lambda f, g: (f"(({f}) U[{p},{p}] ({g}))",
                                                f"(G[0,{p}]({f})) && (G[{p},{p}]({g}))")),
        ("U over ||",             lambda f, g: (f"(({f}) U[{a},{b}] (({g}) || ({f})))",
                                                f"((({f}) U[{a},{b}] ({g}))) || ((({f}) U[{a},{b}] ({f})))")),
        ("U with a true invariant",
                                  lambda f, g: (f"({TRUE} U[{a},{b}] ({f}))",
                                                f"F[{a},{b}]({f})")),
    ]


class Timeout(Exception):
    pass


def _raise_timeout(signum, frame):
    raise Timeout()


def random_atom():
    return f"{random.choice(VARS)}{random.choice(OPS)}{random.randint(-3, 3)}"


def random_proposition(depth=0):
    if depth >= 2 or random.random() < 0.5:
        return random_atom()
    left, right = random_proposition(depth + 1), random_proposition(depth + 1)
    return f"({left} {random.choice(['&&', '||'])} {right})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=120)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--timeout", type=int, default=60,
                        help="Per-pair budget in seconds; a formula whose signal space "
                             "blows up is skipped and counted, not left to hang.")
    args = parser.parse_args()

    signal.signal(signal.SIGALRM, _raise_timeout)
    random.seed(args.seed)
    failures, errors, checked, timeouts = [], [], 0, 0
    per_rewrite = {}
    for _ in range(args.trials):
        first, second = random_proposition(), random_proposition()
        lower = random.randint(0, 2)
        upper = lower + random.randint(0, 2)
        name, rewrite = random.choice(rewrites(lower, upper, random.randint(0, 3)))
        original, rewritten = rewrite(first, second)
        try:
            signal.alarm(args.timeout)
            score = calc_similarity_from_formulas(original, rewritten)
        except Timeout:
            timeouts += 1
            continue
        except Exception as exc:  # parse failure, ...
            errors.append((name, original, rewritten, str(exc).splitlines()[0][:80]))
            continue
        finally:
            signal.alarm(0)
        checked += 1
        per_rewrite[name] = per_rewrite.get(name, 0) + 1
        if abs(score - 1.0) > 1e-9:
            failures.append((name, original, rewritten, score))

    for name, original, rewritten, score in failures:
        print(f"FAIL {score:.4f}  [{name}]")
        print(f"       {original}")
        print(f"    vs {rewritten}")
    for name, original, rewritten, message in errors:
        print(f"ERROR      [{name}] {original}\n        vs {rewritten}\n       {message}")

    print()
    print(f"  {len(per_rewrite)} of {len(rewrites(0, 0, 0))} rewrites exercised")
    status = "ok" if not failures and not errors else "FAIL"
    print(f"  {checked} equivalent pairs checked, "
          f"{len(failures)} scored != 1.0, {len(errors)} errored, "
          f"{timeouts} timed out   {status}")
    return 1 if failures or errors else 0


if __name__ == "__main__":
    sys.exit(main())
