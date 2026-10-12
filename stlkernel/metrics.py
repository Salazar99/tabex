"""The STL kernel of Bortolussi et al. (TACAS 2022), as embedded by stl2vec (Saveri et al. 2024).

A baseline to compare G against. Formulas are compared through their robustness
on random signals:

    k(phi, psi) = E_{xi ~ mu0} [ rho(phi, xi, 0) * rho(psi, xi, 0) ]
    k0          = k(phi, psi) / sqrt(k(phi, phi) * k(psi, psi))

with atoms normalised by tanh (stl2vec App. A) and mu0 the piecewise-linear
base measure of stl2vec App. A at its default parameters. `kernel_distance`
returns 1 - k0. The papers apply a Gaussian on top of k0; it is monotone in
k0, so it changes neither which pairs score identical nor any rank statistic,
and is left out. stl2vec's embedding is a kernel-PCA projection of this same
kernel, so this is the similarity it approximates.

Choices of ours, not fixed by the papers: `true`/`false` get robustness +1/-1
(the ends of tanh's range); each variable is drawn from mu0 independently; the
two formulas of a pair are evaluated on the SAME sampled signals, so formulas
with identical robustness score exactly 0. `==` / `!=` are refused.

Walks `reference_semantics`' NNF AST, so all tools read formulas with one parser.
"""
import sys
from pathlib import Path as FilePath

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(FilePath(__file__).resolve().parent.parent))

from similarity.intervals import UnsupportedFormula  # noqa: E402
from similarity.reference_semantics import (  # noqa: E402
    Always, And, Atom, Constant, Eventually, Or, Until, constant_value, parse, variables,
)

LENGTH = 101   # mu0 on [0, 100] with step 1


def sample_mu0(m, n_vars, rng, length=LENGTH, q=0.1):
    """`m` signals of `n_vars` variables from mu0 (stl2vec App. A), shape [m, n_vars, length].

    Start ~ N(0,1); total variation K ~ N(0,1)^2, split at length-2 sorted
    uniform cuts; the slope's sign flips with probability q at each step.
    """
    shape = (m, n_vars)
    start = rng.standard_normal(shape)
    total = rng.standard_normal(shape) ** 2
    cuts = np.sort(rng.random(shape + (length - 2,)), axis=-1) * total[..., None]
    steps = np.diff(cuts, axis=-1, prepend=0, append=total[..., None])
    signs = rng.choice([-1, 1], shape)[..., None] * \
        np.cumprod(np.where(rng.random(shape + (length - 1,)) < q, -1, 1), axis=-1)
    return np.concatenate([start[..., None], start[..., None] + np.cumsum(signs * steps, axis=-1)],
                          axis=-1)


def robustness(node, X, index):
    """Normalised robustness at every instant where `node` is defined: shape [m, length - horizon]."""
    if isinstance(node, Constant):
        return np.full(X.shape[::2], 1.0 if node.value else -1.0)
    if isinstance(node, Atom):
        if node.op in ("==", "!="):
            raise UnsupportedFormula(f"the kernel baseline does not support {node.op!r}")
        x, c = X[:, index[node.variable]], float(constant_value(node.constant))
        return np.tanh(x - c if node.op in (">", ">=") else c - x)
    if isinstance(node, (And, Or)):
        left, right = robustness(node.left, X, index), robustness(node.right, X, index)
        n = min(left.shape[1], right.shape[1])
        return (np.minimum if isinstance(node, And) else np.maximum)(left[:, :n], right[:, :n])
    if isinstance(node, (Eventually, Always)):
        body = robustness(node.body, X, index)
        windows = sliding_window_view(body, node.upper - node.lower + 1, axis=1)[:, node.lower:]
        return windows.max(-1) if isinstance(node, Eventually) else windows.min(-1)
    if isinstance(node, Until):
        # Closed invariant range [t, t+u], as in reference_semantics.Until (Remark 1).
        phi, psi = robustness(node.invariant, X, index), robustness(node.witness, X, index)
        n = min(phi.shape[1], psi.shape[1]) - node.upper
        return np.max([np.minimum(psi[:, u:u + n], sliding_window_view(phi, u + 1, axis=1)[:, :n].min(-1))
                       for u in range(node.lower, node.upper + 1)], axis=0)
    raise TypeError(f"not a formula node: {node!r}")


def kernel_distance(f1, f2, m=10_000, seed=0, q=0.1):
    """1 - k0(f1, f2), estimated on `m` signals from mu0 shared by both formulas."""
    a, b = parse(f1), parse(f2)
    if max(a.horizon(), b.horizon()) >= LENGTH:
        raise UnsupportedFormula(f"horizon exceeds mu0's {LENGTH} instants")
    names = sorted(variables(a) | variables(b))
    X = sample_mu0(m, max(len(names), 1), np.random.default_rng(seed), q=q)
    index = {name: i for i, name in enumerate(names)}
    r1, r2 = robustness(a, X, index)[:, 0], robustness(b, X, index)[:, 0]
    return 1 - np.mean(r1 * r2) / np.sqrt(np.mean(r1 * r1) * np.mean(r2 * r2))
