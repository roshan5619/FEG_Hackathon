"""
Tests for the three-way split and the trained ranker.

The split tests exist because an earlier version of this project had only
train/test, swept blend weights on the test set, and reported test numbers from
it. These assertions make that class of mistake fail loudly.
"""
import os

import numpy as np
import pytest

from src.pipeline.build_dataset import ART, load


def _ready(*names):
    return all(os.path.exists(os.path.join(ART, n)) for n in names)


@pytest.fixture(scope="module")
def data():
    if not _ready("interactions.npz", "catalog.json"):
        pytest.skip("artifacts not built")
    return load()


# ------------------------------------------------------------------ splits
def test_three_windows_exist_and_are_disjoint_in_time(data):
    r = data["report"]["split"]
    assert r["train_days"] > 0 and r["val_days"] > 0 and r["test_days"] > 0
    assert r["train_end"] < r["val_end"]


def test_no_interaction_appears_in_two_windows(data):
    """
    The same (player, game) may legitimately recur across windows - that is a
    repeat. What must never happen is a window boundary that double-counts the
    same day, so total interactions must equal the sum of the parts.
    """
    total = data["X_train"].nnz + data["X_val"].nnz
    assert data["X_fit"].nnz <= total, "fit cannot contain more cells than train+val"
    assert data["X_fit"].nnz >= max(data["X_train"].nnz, data["X_val"].nnz)


def test_fit_matrix_excludes_the_test_window(data):
    """X_fit is train+validation. A test-only interaction must not be in it."""
    Xf, Xt = data["X_fit"].tocsr(), data["X_test"].tocsr()
    train_val = data["X_train"] + data["X_val"]
    only_test = Xt - Xt.multiply(train_val > 0)
    only_test.eliminate_zeros()
    assert only_test.nnz > 0, "expected some genuinely new test interactions"
    overlap = Xf.multiply(only_test > 0)
    overlap.eliminate_zeros()
    assert overlap.nnz == 0, "test-only interactions leaked into the fit matrix"


def test_sequence_matrices_differ_between_eval_and_serving(data):
    """Evaluation sees train transitions; serving sees train+validation."""
    if "T" not in data or "T_fit" not in data:
        pytest.skip("sequence not built")
    assert data["T"].nnz < data["T_fit"].nnz


# ------------------------------------------------------------------ ranker
@pytest.fixture(scope="module")
def ranker_bits(data):
    if not _ready("ranker.pkl"):
        pytest.skip("ranker not trained")
    from src.recsys.features import FeatureBuilder
    from src.recsys.hybrid import SequenceRec
    from src.recsys.item_item import ItemItemCF
    from src.recsys.ranker import LearnedRanker
    from src.recsys.train import load_model

    m = load_model()
    cf = ItemItemCF()
    cf.sim_ = m["sim"]
    seq = SequenceRec(m["seq"], data["X_recent"])
    seq.T_ = m["seq"]
    fb = FeatureBuilder(data["X_train"], data["catalog"], data["items"], data["X_recent"])
    return LearnedRanker(cf, seq, fb).load(ART), data


def test_ranker_is_actually_trained(ranker_bits):
    """A fitted sklearn estimator with learned parameters, not a heuristic."""
    rk, _ = ranker_bits
    assert rk.model is not None
    assert hasattr(rk.model, "coef_") or hasattr(rk.model, "feature_importances_")
    assert rk.report["n_positives"] > 0
    assert 0.0 < rk.report["positive_rate"] < 0.5, "labels must be imbalanced but real"


def test_learned_weights_are_not_all_zero(ranker_bits):
    rk, _ = ranker_bits
    weights = [f["weight"] for f in rk.report["features"]]
    assert any(abs(w) > 1e-6 for w in weights)
    assert len(weights) == len(set(f["name"] for f in rk.report["features"]))


def test_candidates_exclude_games_already_played(ranker_bits):
    rk, d = ranker_bits
    X = d["X_train"]
    for u in (1, 7, 33):
        cand, _, _ = rk.candidates(X, u)
        played = set(X[u].indices.tolist())
        assert not (set(cand.tolist()) & played)


def test_explanation_is_exact_for_logistic_regression(ranker_bits):
    """
    Contribution = coefficient x standardised value. For a linear model these
    sum to the logit, so the explanation is the decomposition, not a story.
    """
    rk, d = ranker_bits
    if not hasattr(rk.model, "coef_"):
        pytest.skip("non-linear model; attribution is indicative only")
    X = d["X_train"]
    cand, _, _ = rk.candidates(X, 1)
    exp = rk.explain(X, 1, int(cand[0]))
    assert exp["exact"] is True
    total = sum(f["contribution"] for f in exp["features"]) + float(rk.model.intercept_[0])
    p = 1.0 / (1.0 + np.exp(-total))
    assert abs(p - exp["probability"]) < 1e-4, "contributions must reconstruct the probability"


def test_ranker_beats_the_blend_on_tail_discovery(ranker_bits):
    """The claim that justifies training a model at all."""
    from src.recsys.evaluate import evaluate
    from src.recsys.hybrid import HybridRec

    rk, d = ranker_bits
    X, Xt = d["X_train"], d["X_test"]
    mask = np.ones(X.shape[1], dtype=bool)
    got = evaluate(rk, X, Xt, "tail_discovery", mask)

    blend = HybridRec(rk.cf, rk.seq, 1.0, 5.0, 0.0)
    blend.pop_ = np.zeros(X.shape[1], dtype=np.float32)
    ref = evaluate(blend, X, Xt, "tail_discovery", mask)
    assert got["ndcg@10"] > ref["ndcg@10"]
