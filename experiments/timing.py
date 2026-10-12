"""RQ2: execution time vs formula complexity (horizon T, number of variables |V|).

    python experiments/timing.py [--workers 8] [--timeout 60] [--mem-gb 3]
    python experiments/timing.py --plot-only

Each pair is one formula family instantiated twice, with the two predicates of
Madsen et al.'s Example 1 (theta1 = [0.2, 0.4], theta2 = [0.2, 0.44]) on every
variable -- a partially overlapping pair, so no method can shortcut on
identity. Four families: G-box, F-box, G o F, until. Four methods: TABEX's
reference pipeline, tabex_fast, Madsen's PH (both directed MILPs) and SD.

Every (family, |V|, method) series runs in its own worker process, sweeping T
upwards; a run that exceeds the timeout or the memory cap ends its series
(larger T is only harder), and the remaining points are recorded as skipped.
Each run is timed inside a fresh child process, so a blow-up cannot take the
worker down and memory from one run never leaks into the next. Times are
wall-clock of the scoring call alone (parse included, process start excluded),
the minimum of up to 3 repetitions while the total stays under a second.

Output: experiments/results/timing.csv and timing.png.
"""
import argparse
import csv
import multiprocessing as mp
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "experiments" / "results"
VARS = ["x", "y", "z", "w", "v"]
HORIZONS = [2, 4, 6, 8, 10, 12, 16, 20, 24, 28, 32, 36, 40]
N_VARS = [1, 2, 3, 4, 5]
METHODS = ["reference", "tabex_fast", "PH", "SD"]


def box(variables, upper):
    return "(" + " && ".join(f"{v}>=0.2 && {v}<={upper}" for v in variables) + ")"


def lower(variables):
    return "(" + " && ".join(f"{v}>=0.2" for v in variables) + ")"


def upper(variables, value):
    return "(" + " && ".join(f"{v}<={value}" for v in variables) + ")"


FAMILIES = {
    "G": lambda vs, T, u: f"G[0,{T}]{box(vs, u)}",
    "F": lambda vs, T, u: f"F[0,{T}]{box(vs, u)}",
    # G o F with a fixed inner window, so T is the overall horizon.
    "GF": lambda vs, T, u: f"G[0,{T - 2}] F[0,2]{box(vs, u)}",
    "U": lambda vs, T, u: f"{lower(vs)} U[0,{T}] {upper(vs, u)}",
}


def pair(family, n_vars, T):
    vs = VARS[:n_vars]
    return FAMILIES[family](vs, T, 0.4), FAMILIES[family](vs, T, 0.44)


def score(method, f1, f2):
    if method == "tabex_fast":
        from tabex_fast.engine import similarity
        return similarity(f1, f2)
    if method == "reference":
        from similarity.stl_similarity import calc_similarity_from_formulas
        return calc_similarity_from_formulas(f1, f2)
    from similarity.reference_semantics import parse
    from similarity.stl_similarity import resolve_D
    D = float(resolve_D(None, parse(f1), parse(f2)))
    if method == "PH":
        from madsen.metrics import d_ph
        return d_ph(f1, f2, -D, D)[0]
    from madsen.metrics import d_sd
    return d_sd(f1, f2, -D, D)


def _child(method, f1, f2, mem_bytes, queue):
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    try:
        best, value, spent = float("inf"), None, 0.0
        for _ in range(3):
            start = time.perf_counter()
            value = score(method, f1, f2)
            elapsed = time.perf_counter() - start
            best, spent = min(best, elapsed), spent + elapsed
            if spent > 1.0:
                break
        queue.put(("ok", best, value))
    except MemoryError:
        queue.put(("memout", None, None))
    except RecursionError:
        queue.put(("memout", None, None))
    except Exception as exc:  # noqa: BLE001  -- recorded, not hidden
        queue.put(("error", None, f"{type(exc).__name__}: {exc}"[:200]))


def timed(method, f1, f2, timeout, mem_bytes):
    ctx = mp.get_context("fork")
    queue = ctx.Queue()
    proc = ctx.Process(target=_child, args=(method, f1, f2, mem_bytes, queue))
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.kill()
        proc.join()
        return "timeout", None, None
    if queue.empty():   # killed by the OS (e.g. allocation failure in C)
        return "memout", None, None
    return queue.get()


def series(args):
    family, n_vars, method, timeout, mem_bytes = args
    rows, dead = [], None
    for T in HORIZONS:
        f1, f2 = pair(family, n_vars, T)
        if dead:
            rows.append((family, n_vars, T, method, "skipped", "", "", f1, f2))
            continue
        status, seconds, value = timed(method, f1, f2, timeout, mem_bytes)
        if status != "ok":
            dead = status
        rows.append((family, n_vars, T, method, status,
                     "" if seconds is None else f"{seconds:.6f}",
                     "" if value is None else value, f1, f2))
        print(f"{family:2} |V|={n_vars} T={T:2} {method:10} {status:8} "
              f"{'' if seconds is None else f'{seconds:.4f}s'}", flush=True)
    return rows


def run(workers, timeout, mem_gb):
    jobs = [(f, n, m, timeout, int(mem_gb * 2**30))
            for f in FAMILIES for n in N_VARS for m in METHODS]
    # Longest series first, so the pool is not left waiting on one straggler.
    jobs.sort(key=lambda j: (j[2] != "reference", j[2] != "PH"))
    rows = []
    with ProcessPoolExecutor(workers, mp_context=mp.get_context("spawn")) as pool:
        for result in pool.map(series, jobs):
            rows.extend(result)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "timing.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["family", "n_vars", "T", "method", "status", "seconds", "value",
                         "formula1", "formula2"])
        writer.writerows(sorted(rows, key=lambda r: (r[0], r[1], METHODS.index(r[3]), r[2])))


# Reference categorical palette (dataviz skill), fixed slot order per method.
COLORS = {"reference": "#2a78d6", "tabex_fast": "#eb6834", "PH": "#1baf7a", "SD": "#eda100"}
MARKERS = {"reference": "o", "tabex_fast": "s", "PH": "^", "SD": "D"}
TITLES = {"G": "G[0,T] θ", "F": "F[0,T] θ", "GF": "G[0,T-2] F[0,2] θ", "U": "θ_lo U[0,T] θ_hi"}


def plot(timeout):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with open(OUT / "timing.csv") as fh:
        rows = list(csv.DictReader(fh))
    fams, nvs = list(FAMILIES), [1, 3, 5]
    fig, axes = plt.subplots(len(nvs), len(fams), figsize=(14, 9), sharex=True, sharey=True)
    for i, n in enumerate(nvs):
        for j, fam in enumerate(fams):
            ax = axes[i][j]
            for m in METHODS:
                pts = [(int(r["T"]), float(r["seconds"])) for r in rows
                       if r["family"] == fam and int(r["n_vars"]) == n and r["method"] == m
                       and r["status"] == "ok"]
                fail = [(int(r["T"]), r["status"]) for r in rows
                        if r["family"] == fam and int(r["n_vars"]) == n and r["method"] == m
                        and r["status"] in ("timeout", "memout", "error")]
                if pts:
                    ax.plot(*zip(*pts), color=COLORS[m], marker=MARKERS[m], markersize=4,
                            linewidth=1.5, label=m)
                for T, _ in fail:   # the first failing T, drawn at the timeout line
                    ax.plot([T], [timeout], color=COLORS[m], marker="x", markersize=8,
                            linestyle="none")
            ax.axhline(timeout, color="#8a8986", linewidth=0.8, linestyle=":")
            ax.set_yscale("log")
            ax.grid(True, color="#e6e5e1", linewidth=0.6)
            ax.set_axisbelow(True)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            if i == 0:
                ax.set_title(TITLES[fam], fontsize=10)
            if j == 0:
                ax.set_ylabel(f"|V| = {n}\nseconds (log)")
            if i == len(nvs) - 1:
                ax.set_xlabel("horizon T")
    handles, labels = axes[0][0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color="#52514e", marker="x", linestyle="none"))
    labels.append(f"timeout / memout ({timeout:g}s)")
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT / "timing.png", dpi=150)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--mem-gb", type=float, default=3.0)
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args()
    if not args.plot_only:
        run(args.workers, args.timeout, args.mem_gb)
    plot(args.timeout)
