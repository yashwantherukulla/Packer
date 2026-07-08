import numpy as np

from packer.engine.detect.signals.numerics import (
    count_outlier_singular_values,
    effective_rank,
    mp_upper_edge,
    singular_values,
    stable_rank,
)


def test_mp_edge_matches_bai_yin():
    assert mp_upper_edge(64, 36, 1.0) == 8.0 + 6.0


def test_random_matrix_has_no_outliers():
    rng = np.random.default_rng(0)
    m = rng.standard_normal((64, 48))
    assert count_outlier_singular_values(m) == 0


def test_rank1_perturbation_is_flagged():
    rng = np.random.default_rng(1)
    m = rng.standard_normal((64, 48))
    u = rng.standard_normal(64)
    u /= np.linalg.norm(u)
    v = rng.standard_normal(48)
    v /= np.linalg.norm(v)
    spiked = m + 50.0 * np.outer(u, v)
    assert count_outlier_singular_values(spiked) >= 1


def test_effective_rank_low_for_lowrank():
    rng = np.random.default_rng(2)
    full = rng.standard_normal((40, 40))
    low = np.outer(rng.standard_normal(40), rng.standard_normal(40))
    assert effective_rank(singular_values(low)) < effective_rank(singular_values(full))


def test_stable_rank_of_identity():
    assert abs(stable_rank(np.eye(10)) - 10.0) < 1e-9
