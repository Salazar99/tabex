"""RQ4, step 2: pairwise one-way similarity and G between Slam's candidates.

    python experiments/rq4/similarity_matrix.py [--workers 30]

Candidates are compared within a (case, context): a context is one Slam hint
(one template, one consequent), which is where a miner's redundancy lives --
candidates of different contexts assert different things by construction.

Scored by tabex_fast (same number as the reference pipeline). Each pair is
scored on its own joint grid (Definition 1), and with ONE D per context:
max|constant| over all of that context's candidates, + 1 (Definition 2's
bound, for the whole set). A per-pair D would make the scores of one matrix
incomparable, and clustering needs a single metric.

Output: experiments/rq4/results/pairs.csv.gz (gzipped CSV) -- one row per unordered pair i < j
(ranks within the context), with OWSim(i->j), OWSim(j->i), G and the time.
"""
import argparse
import csv
import gzip
import sys
import time
from collections import defaultdict
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from similarity.reference_semantics import constants, parse  # noqa: E402
from tabex_fast.engine import one_way, regions  # noqa: E402

RESULTS = FilePath(__file__).resolve().parent / "results"


def load_contexts():
    contexts = defaultdict(list)
    with open(RESULTS / "candidates.csv") as fh:
        for row in csv.DictReader(fh):
            if not row["unsupported"]:
                contexts[(row["case"], row["context"])].append((int(row["rank"]), row["tabex"]))
    return contexts


def context_D(formulas):
    return max((abs(c) for f in formulas for c in constants(parse(f))), default=Fraction(0)) + 1


def score(job):
    case, context, i, fi, j, fj, D = job
    start = time.perf_counter()
    r1, r2, _, _ = regions(fi, fj)
    forward, backward = one_way(r1, r2, D), one_way(r2, r1, D)
    return (case, context, i, j, forward, backward, (forward + backward) / 2,
            time.perf_counter() - start)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=30)
    args = parser.parse_args()

    jobs = []
    for (case, context), cands in load_contexts().items():
        D = context_D([f for _, f in cands])
        jobs += [(case, context, i, fi, j, fj, D)
                 for a, (i, fi) in enumerate(cands) for j, fj in cands[a + 1:]]
    print(f"{len(jobs)} pairs", flush=True)
    start = time.perf_counter()
    with Pool(args.workers) as pool, gzip.open(RESULTS / "pairs.csv.gz", "wt", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["case", "context", "i", "j", "ow_ij", "ow_ji", "G", "seconds"])
        for n, row in enumerate(pool.imap_unordered(score, jobs, chunksize=16), 1):
            writer.writerow(row[:4] + tuple(f"{v:.6f}" for v in row[4:]))
            if n % 5000 == 0:
                print(f"  {n}/{len(jobs)}  {time.perf_counter() - start:.0f}s", flush=True)
    print(f"done in {time.perf_counter() - start:.0f}s wall")


if __name__ == "__main__":
    main()
