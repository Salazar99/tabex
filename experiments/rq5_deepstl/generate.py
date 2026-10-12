"""RQ5: sample requirements from DeepSTL and collect LLM formalisations.

    python experiments/rq5_deepstl/generate.py select
    GOOGLE_API_KEY=... python experiments/rq5_deepstl/generate.py gemini [--budget-usd 3.5]
    python experiments/rq5_deepstl/generate.py ollama [--url http://127.0.0.1:11434]

`select` draws the requirement set: DeepSTL pairs whose STL is in TABEX's
fragment and tractable (deepstl.classify), deduplicated on the STL, stratified
by DeepSTL's requirement type, N_PER_TYPE each (fewer if the type has fewer),
seed 0 -> results/requirements.csv.

`gemini` / `ollama` send PROMPT (below) for every requirement to every model in
MODELS and append each raw answer to results/samples.jsonl: one line per
(requirement, model, sample index), with the model id, temperature, seed and
token usage. Re-running skips what is already there, so a run can be resumed.

Sampling: temperature 0.8 for every model, K samples per requirement, each an
independent call with seed 1..K. Gemini 3.8 Flash neither offers several
candidates per call nor lets thinking be switched off (thinking_budget=0 still
spends ~200-350 thought tokens), so thinking is left at the model default. Gemini spend is estimated from the API's own token
counts at the list prices in PRICE_USD_PER_M (conservative) and the run stops
before `--budget-usd` is exceeded.
"""
import argparse
import csv
import json
import os
import random
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path as FilePath

HERE = FilePath(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from deepstl import CORPUS, classify  # noqa: E402

RESULTS = HERE / "results"
N_PER_TYPE, K, TEMPERATURE = 60, 3, 0.8
MODELS = {
    "gemini": ["gemini-3.8-flash"],
    "ollama": ["qwen2.5:7b-instruct"],
}
# USD per 1M tokens (input, output incl. thinking). Gemini 3.8 Flash lists $0.75 / $3.75
# until 2026-12-31 and $1.50 / $7.50 from 2027; the later (higher) prices are used.
PRICE_USD_PER_M = {"gemini-3.8-flash": (1.50, 7.50)}

PROMPT = """You translate natural-language requirements of cyber-physical systems into Signal Temporal Logic (STL).

Time is discrete: instants 0, 1, 2, ... ("time units"). Every signal is real-valued. Use the signal names exactly as they are written in the requirement. Temporal intervals [a,b] are closed, with non-negative integer bounds, relative to the instant at which the operator is evaluated.

Write the formula in exactly this grammar:

  formula  ::= atom | true | false
             | !formula | formula && formula | formula || formula | formula -> formula
             | F[a,b] formula | G[a,b] formula | formula U[a,b] formula
             | G formula                      (unbounded "always", only as the outermost operator)
             | ( formula )
  atom     ::= signal op constant        op is one of  <  <=  >  >=  ==  !=
  constant ::= a decimal number, e.g. 5, -2, 15.4

An atom compares ONE signal with ONE constant (no "x > y", no arithmetic, no chained comparisons like 0 < x < 2 -- write x > 0 && x < 2 instead).

Requirement: {english}

Answer with ONLY the formula on a single line: no explanation, no markdown, no quotes."""


def select():
    by_type, seen = defaultdict(list), set()
    with open(CORPUS) as fh:
        for n, row in enumerate(csv.DictReader(fh)):
            formula, _ = classify(row["STL"])
            if formula and row["STL"] not in seen:
                seen.add(row["STL"])
                by_type[row["Type"]].append((n, row))
    rng = random.Random(0)
    out = []
    for typ in sorted(by_type):
        for n, row in rng.sample(by_type[typ], min(N_PER_TYPE, len(by_type[typ]))):
            out.append({"id": f"D{n}", "type": typ, "english": row["English"],
                        "stl": row["STL"], "reference": classify(row["STL"])[0]})
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / "requirements.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print({t: min(N_PER_TYPE, len(v)) for t, v in by_type.items()}, "of", {t: len(v) for t, v in by_type.items()})


def load_requirements():
    """Round-robin over requirement types, so a budget stop keeps the set balanced."""
    with open(RESULTS / "requirements.csv") as fh:
        rows = list(csv.DictReader(fh))
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)
    queues = [by_type[t] for t in sorted(by_type)]
    return [q[i] for i in range(max(map(len, queues))) for q in queues if i < len(q)]


def done_keys():
    path = RESULTS / "samples.jsonl"
    if not path.exists():
        return set(), 0.0
    keys, spent = set(), 0.0
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        keys.add((rec["id"], rec["model"], rec["sample"]))
        spent += rec.get("cost_usd", 0.0)
    return keys, spent


def append(records):
    with open(RESULTS / "samples.jsonl", "a") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def run_gemini(budget):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    keys, spent = done_keys()
    reqs = load_requirements()
    for model in MODELS["gemini"]:
        p_in, p_out = PRICE_USD_PER_M[model]
        for req in reqs:
            for k in range(K):
                if (req["id"], model, k) in keys:
                    continue
                # Worst case of this call, so the budget is never crossed.
                if spent + (2000 * p_in + 4000 * p_out) / 1e6 > budget:
                    print(f"budget reached (${spent:.4f}); stopping")
                    return
                config = types.GenerateContentConfig(
                    temperature=TEMPERATURE, seed=k + 1, max_output_tokens=4000)
                for attempt in range(6):
                    try:
                        resp = client.models.generate_content(
                            model=model, contents=PROMPT.format(english=req["english"]),
                            config=config)
                        break
                    except Exception as exc:  # noqa: BLE001  -- rate limits: back off, retry
                        print(f"  {model} {req['id']}: {type(exc).__name__} {str(exc)[:120]}; retry")
                        time.sleep(10 * (attempt + 1))
                else:
                    raise RuntimeError("giving up after 6 attempts")
                u = resp.usage_metadata
                n_in = u.prompt_token_count or 0
                n_out = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
                cost = (n_in * p_in + n_out * p_out) / 1e6
                spent += cost
                parts = (resp.candidates[0].content.parts or []) if resp.candidates and \
                    resp.candidates[0].content else []
                text = "".join(p.text for p in parts if getattr(p, "text", None))
                append([{"id": req["id"], "model": model, "sample": k, "answer": text,
                         "temperature": TEMPERATURE, "seed": k + 1, "tokens_in": n_in,
                         "tokens_out": n_out, "cost_usd": cost}])
            print(f"{model} {req['id']}  ${spent:.4f}", flush=True)


def run_ollama(url):
    keys, _ = done_keys()
    reqs = load_requirements()
    for model in MODELS["ollama"]:
        for req in reqs:
            for k in range(K):
                if (req["id"], model, k) in keys:
                    continue
                body = json.dumps({"model": model, "prompt": PROMPT.format(english=req["english"]),
                                   "stream": False, "options": {"temperature": TEMPERATURE,
                                                                "seed": k + 1, "num_predict": 200}})
                r = urllib.request.urlopen(urllib.request.Request(
                    f"{url}/api/generate", data=body.encode(),
                    headers={"Content-Type": "application/json"}), timeout=600)
                out = json.loads(r.read())
                append([{"id": req["id"], "model": model, "sample": k, "answer": out["response"],
                         "temperature": TEMPERATURE, "seed": k + 1,
                         "tokens_in": out.get("prompt_eval_count"),
                         "tokens_out": out.get("eval_count"), "cost_usd": 0.0}])
            print(f"{model} {req['id']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("what", choices=["select", "gemini", "ollama"])
    parser.add_argument("--budget-usd", type=float, default=3.5)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    {"select": select, "gemini": lambda: run_gemini(args.budget_usd),
     "ollama": lambda: run_ollama(args.url)}[args.what]()
