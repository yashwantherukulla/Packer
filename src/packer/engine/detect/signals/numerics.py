from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


def singular_values(mat: NDArray[Any]) -> NDArray[Any]:
    """Descending singular values of a 2-D matrix (float64, no singular vectors)."""
    m = np.asarray(mat, dtype=np.float64)
    if m.ndim != 2:
        raise ValueError(f"expected 2-D matrix, got shape {m.shape}")
    return np.linalg.svd(m, compute_uv=False)


def frobenius_norm(mat: NDArray[Any]) -> float:
    return float(np.linalg.norm(np.asarray(mat, dtype=np.float64), ord="fro"))


def spectral_norm(mat: NDArray[Any]) -> float:
    sv = singular_values(mat)
    return float(sv[0]) if sv.size else 0.0


def stable_rank(mat: NDArray[Any]) -> float:
    """||W||_F^2 / ||W||_2^2 — a soft, scale-free rank measure."""
    spec = spectral_norm(mat)
    if spec == 0.0:
        return 0.0
    return float(frobenius_norm(mat) ** 2 / spec**2)


def effective_rank(sv: NDArray[Any]) -> float:
    """exp(Shannon entropy of the normalized singular-value spectrum) — Roy & Vetterli."""
    s = np.asarray(sv, dtype=np.float64)
    s = s[s > 0]
    if s.size == 0:
        return 0.0
    p = s / s.sum()
    entropy = float(-(p * np.log(p)).sum())
    return float(np.exp(entropy))


def mp_upper_edge(n_rows: int, n_cols: int, sigma: float) -> float:
    """Largest-singular-value soft edge of an nxm Gaussian matrix with entry std ``sigma``:
    sigma * (sqrt(n) + sqrt(m)) (Bai-Yin, the Marchenko-Pastur bulk edge)."""
    return float(sigma) * (float(np.sqrt(n_rows)) + float(np.sqrt(n_cols)))


def estimate_sigma(sv: NDArray[Any], n_rows: int, n_cols: int) -> float:
    """Per-entry std from the spectrum via the Frobenius identity ``sum(sv^2) = ||W||_F^2``:
    ``sigma = ||W||_F / sqrt(n*m)`` — the RMS of the entries. A handful of spikes barely
    move it (the bulk dominates ``sum(sv^2)``), while it stays correct for a clean
    Gaussian, unlike a median-of-singular-values estimate which under-reads sigma."""
    s = np.asarray(sv, dtype=np.float64)
    denom = float(n_rows) * float(n_cols)
    if s.size == 0 or denom <= 0:
        return 0.0
    return float(np.sqrt(float((s**2).sum()) / denom))


def count_outlier_singular_values(mat: NDArray[Any], *, margin: float = 1.05) -> int:
    """Count singular values exceeding ``margin`` x the estimated MP/Bai-Yin bulk edge."""
    sv = singular_values(mat)
    if sv.size == 0:
        return 0
    n, m = np.asarray(mat).shape
    sigma = estimate_sigma(sv, n, m)
    edge = mp_upper_edge(n, m, sigma) * margin
    return int(np.count_nonzero(sv > edge))


def hill_alpha(sv: NDArray[Any], *, tail_frac: float = 0.2) -> float:
    """Hill power-law tail exponent of the singular spectrum. Heavier tail → smaller alpha.
    Returns +inf when the tail is too small to estimate."""
    s = np.sort(np.asarray(sv, dtype=np.float64))[::-1]
    s = s[s > 0]
    if s.size < 3:
        return float("inf")
    k = min(max(2, int(s.size * tail_frac)), s.size - 1)
    tail = s[: k + 1]
    smin = tail[-1]
    if smin <= 0:
        return float("inf")
    logs = np.log(tail[:-1] / smin)
    denom = float(logs.mean())
    return 1.0 + 1.0 / denom if denom > 0 else float("inf")
