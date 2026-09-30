"""RQ4 baseline: Slam's own redundancy pruning (`--remove-impl`), via STLSat.

    python experiments/rq4/stlsat_baseline.py [--stlsat PATH] [--workers 30] [--timeout 60]

Re-implements `Qualifier::filterAssertionsWithImplications` (Slam, develop):
walk the candidates in rank order keeping a set `kept`; a candidate a is
checked only against kept b with the SAME propositions; if b implies a, a is
dropped; else if a implies b, b is dropped; a is then kept. "b implies a" is
decided as Slam does it: `G(` replaced by `G[0,100](`, and stlsat run on
`(b) && !(a)` -- unsat means implied.

Two deviations, both about cost and not about the result: every same-
proposition ordered pair is decided up front, in parallel (the greedy walk is
then replayed on the stored answers, so it takes the same decisions Slam's
serial loop would); and each stlsat call has a timeout, counted as "not
implied" (it keeps the candidate -- the conservative answer) and reported.
Slam's own loop has no timeout: a single sat instance ran past 120 s here.

Formulas go to stlsat in TABEX's translation (`@(v,k)` -> `v_dk`), since
stlsat does not parse Slam's derivative operator.

Output: experiments/rq4/results/implications.csv, stlsat_kept.csv.
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent.parent
RESULTS = FilePath(__file__).resolve().parent / "results"
ATOM = re.compile(r"(@\(\w+,\d+\)|\w+)\s*(<=|>=|==|!=|<|>)\s*(-?[\d.]+)")


def props(slam_text):
    """Slam's `getPropsAsString` equality test, on the atoms of the assertion."""
    return frozenset(ATOM.findall(slam_text))


def implies(job):
    stlsat, timeout, key, b, a = job     # does b imply a?
    wrap = lambda f: f"G[0,100]({f})"    # noqa: E731  -- as Slam's replaceAll("G(", "G[0,100](")
    with tempfile.NamedTemporaryFile("w", suffix=".stl", delete=False) as fh:
        fh.write(f"({wrap(b)}) && !({wrap(a)})\n")
        path = fh.name
    start = time.perf_counter()
    try:
        out = subprocess.run([stlsat, path], capture_output=True, text=True, timeout=timeout).stdout
        status = "implied" if "Some(false)" in out else ("not_implied" if "Some(true)" in out
                                                          else "unknown")
    except subprocess.TimeoutExpired:
        status = "timeout"
    finally:
        os.unlink(path)
    return key + (status, time.perf_counter() - start)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # Slam calls `stlsat` from the PATH (Qualifier.cc). Build it from
    # https://github.com/ZamponiMarco/stlsat (master, 16e5ea6 used here), e.g.
    #   Z3_SYS_Z3_HEADER=<z3>/include/z3.h RUSTFLAGS="-L <z3>/lib" cargo build --release
    # with the z3 that Slam's third_party/install_z3.sh builds.
    parser.add_argument("--stlsat", default="stlsat")
    parser.add_argument("--workers", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    contexts = defaultdict(list)
    with open(RESULTS / "candidates.csv") as fh:
        for row in csv.DictReader(fh):
            contexts[(row["case"], row["context"])].append(row)

    jobs = []
    for (case, context), rows in contexts.items():
        for x in rows:
            for y in rows:
                if x is not y and props(x["slam"]) == props(y["slam"]):
                    key = (case, context, int(y["rank"]), int(x["rank"]))  # y implies x?
                    jobs.append((args.stlsat, args.timeout, key, y["tabex"], x["tabex"]))
    # Resumable: answers already in implications.csv are reused, not recomputed.
    answers, path = {}, RESULTS / "implications.csv"
    if path.exists():
        with open(path) as fh:
            for r in csv.DictReader(fh):
                answers[(r["case"], r["context"], int(r["b"]), int(r["a"]))] = r["b_implies_a"] == "implied"
    todo = [j for j in jobs if j[2] not in answers]
    print(f"{len(jobs)} stlsat calls, {len(jobs) - len(todo)} already decided", flush=True)
    start = time.perf_counter()
    with Pool(args.workers) as pool, open(path, "a", newline="") as fh:
        writer = csv.writer(fh)
        if fh.tell() == 0:
            writer.writerow(["case", "context", "b", "a", "b_implies_a", "seconds"])
        for n, row in enumerate(pool.imap_unordered(implies, todo), 1):
            writer.writerow(row[:5] + (f"{row[5]:.3f}",))
            fh.flush()
            answers[row[:4]] = row[4] == "implied"
            if n % 200 == 0:
                print(f"  {n}/{len(todo)}  {time.perf_counter() - start:.0f}s", flush=True)

    with open(RESULTS / "stlsat_kept.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["case", "context", "candidates", "kept"])
        for (case, context), rows in contexts.items():
            by_rank, kept = {int(r["rank"]): r for r in rows}, []
            for x in rows:
                a, keep = int(x["rank"]), True
                for b in list(kept):
                    if props(x["slam"]) != props(by_rank[b]["slam"]):
                        continue
                    if answers.get((case, context, b, a)):
                        keep = False
                        break
                    if answers.get((case, context, a, b)):
                        kept.remove(b)
                if keep:
                    kept.append(a)
            writer.writerow((case, context, len(rows), len(kept)))
            print(f"{case:13} {context:25} {len(rows):4} -> {len(kept):4}")
    print(f"done in {time.perf_counter() - start:.0f}s wall")


if __name__ == "__main__":
    main()
