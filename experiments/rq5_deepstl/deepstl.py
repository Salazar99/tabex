"""DeepSTL (He et al., ICSE 2022) -> TABEX's fragment: conversion and filter.

The corpus (Archive/material/artifact/complete_track/data_set/corpus_no_split.csv,
120 000 English/STL pairs, https://github.com/JieHE-2020/DeepSTL) writes

    always [a:b] ( ... ), eventually [a:b], until [a:b], and, or, not, ->, rise, fall

A formula is kept iff, after conversion, `reference_semantics.parse` accepts it
and it satisfies the tractability bounds below. Each reason for rejection is
counted separately (`classify`):

* rise / fall        -- edge operators: need the previous instant, not in the fragment;
* string constant    -- `sig == RYoU_1`: an enumerated value, not a real constant;
* fractional bound   -- `[0:11.91]`: the fragment has discrete, integer time;
* unbounded inner    -- `always`/`eventually` without an interval below the top level;
* horizon / vars     -- horizon > MAX_H or more than MAX_V signals (scoring cost, RQ2);
* parse              -- anything else the parser refuses.

A top-level unbounded `always ( body )` -- the invariance form, as in Slam's
G(...) (RQ4) -- is kept as its body: the outer G is shared by both formulas of a
comparison, and the body is what the formalisations disagree about. Both the
reference and every LLM output are normalised by the same rule.
"""
import re
import sys
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from similarity.reference_semantics import parse, variables  # noqa: E402

MAX_H, MAX_V = 12, 3
CORPUS = (FilePath.home() / "DeepSTL" / "Archive" / "material" / "artifact" / "complete_track"
          / "data_set" / "corpus_no_split.csv")


def _strip_outer_always(text):
    """`always ( X )` with the parenthesis spanning the whole formula -> `X`."""
    m = re.match(r"^\s*(always|G)\s*\(", text)
    if not m:
        return text
    depth = 0
    for k in range(m.end() - 1, len(text)):
        depth += text[k] == "("
        depth -= text[k] == ")"
        if depth == 0:
            return text[m.end():k] if text[k + 1:].strip() == "" else text
    return text


def convert(text):
    """DeepSTL / free-form STL syntax -> TABEX syntax (no semantic change)."""
    t = text.strip().strip("`").strip()
    t = re.sub(r"\[\s*([^\]:,]+?)\s*[:,]\s*([^\]]+?)\s*\]", r"[\1,\2]", t)   # [a:b] -> [a,b]
    t = _strip_outer_always(t)
    for word, sym in (("always", "G"), ("eventually", "F"), ("until", "U"),
                      ("and", "&&"), ("or", "||"), ("not", "!")):
        t = re.sub(rf"\b{word}\b", sym, t)
    t = re.sub(r"\bG\s*(\[)", r"G\1", t)
    t = re.sub(r"\bF\s*(\[)", r"F\1", t)
    t = re.sub(r"\bU\s*(\[)", r"U\1", t)
    t = t.replace("∧", "&&").replace("∨", "||").replace("¬", "!").replace("→", "->")
    t = re.sub(r"(?<![<>=!])=(?!=)", "==", t)          # a lone '=' means equality
    return t


def classify(text):
    """(formula, None) if in the fragment and tractable, else (None, reason)."""
    raw = text
    if re.search(r"\b(rise|fall)\b", raw):
        return None, "rise/fall"
    if re.search(r"==\s*[A-Za-z_][A-Za-z0-9_]*", raw) and not re.search(r"==\s*-?\d", raw.split("==", 1)[1][:3] or "0"):
        pass
    t = convert(raw)
    if re.search(r"(==|!=|<=|>=|<|>)\s*(?!-?\d)[A-Za-z_]", t):
        return None, "string constant"
    if re.search(r"\[\s*[^\],]*\.\d*[1-9]|,\s*[^\]]*\.\d*[1-9][^\]]*\]", t):
        return None, "fractional bound"
    if re.search(r"\b[GF](?!\[)\s*\(|\bU(?!\[)", t):
        return None, "unbounded inner"
    try:
        tree = parse(t)
    except Exception as exc:  # noqa: BLE001
        return None, f"parse: {type(exc).__name__}"
    if tree.horizon() > MAX_H:
        return None, f"horizon > {MAX_H}"
    if len(variables(tree)) > MAX_V:
        return None, f"vars > {MAX_V}"
    return t, None
