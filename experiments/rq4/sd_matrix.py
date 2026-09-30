"""RQ4 baseline: Madsen et al.'s SD distance on every pair of pairs.csv.

    python experiments/rq4/sd_matrix.py [--workers 16]

Same pairs, same per-context D (signal domain S = [-D, D]) as
similarity_matrix.py. SD needs rectangular predicates, so `v == c` is written
as the closed range `v >= c && v <= c` (the same set of values); nothing else
changes. Output: results/sd_pairs.csv.gz (case, context, i, j, SD).
"""
import argparse
import csv
import gzip
import re
import sys
from multiprocessing import Pool
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from experiments.rq4.similarity_matrix import context_D, load_contexts  # noqa: E402
from madsen.metrics import d_sd  # noqa: E402

RESULTS = FilePath(__file__).resolve().parent / "results"


def rectangular(formula):
    return re.sub(r"\(\s*(\w+)\s*==\s*(-?[\d.]+)\s*\)", r"(\1 >= \2 && \1 <= \2)", formula)


def score(job):
    case, context, i, fi, j, fj, D = job
    return case, context, i, j, d_sd(rectangular(fi), rectangular(fj), -float(D), float(D))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    jobs = []
    for (case, context), cands in load_contexts().items():
        D = context_D([f for _, f in cands])
        jobs += [(case, context, i, fi, j, fj, D)
                 for a, (i, fi) in enumerate(cands) for j, fj in cands[a + 1:]]
    with Pool(args.workers) as pool, gzip.open(RESULTS / "sd_pairs.csv.gz", "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "context", "i", "j", "SD"])
        for row in pool.imap_unordered(score, jobs, chunksize=256):
            w.writerow(row[:4] + (f"{row[4]:.6f}",))
    print(f"{len(jobs)} pairs")


if __name__ == "__main__":
    main()
