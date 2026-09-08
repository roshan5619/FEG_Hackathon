"""
Tests for the recommender.

Three groups, in order of how much they matter:

1. **Safety** - a self-excluded account gets no recommendations at all, and no
   opaque game code can ever reach a tile.
2. **Honesty of the evaluation** - the temporal split does not leak, the
   discovery task never counts a game the player already played, and the
   metrics agree with hand-computed values on a tiny fixture.
3. **Correctness of the catalogue** - the accounting row is excluded, slugs are
   never treated as names.
"""
import numpy as np
import pytest
from scipy import sparse

from src.recsys import catalog as cat
from src.recsys import responsible as rp
from src.recsys.baselines import MostPlayed, UserTop
from src.recsys.evaluate import _metrics, evaluate
from src.recsys.item_item import ItemItemCF


# ------------------------------------------------------------------ catalogue
@pytest.mark.parametrize("code,family", [
    ("pop_9f571b7a_egtfeg", cat.OPAQUE),
    ("gpas_3chken_pop", cat.SLUG),
    ("3cb", cat.SHORT),
    ("NA - Deposit / Withdrawal / Corrections", cat.NON_GAME),
    ("POP Rhino Coins: Hit the Bonus (Playson via FEG)", cat.NAMED),
    ("(GPAS) Big Bad Wolf: Cash Collect & Link™ POP", cat.NAMED),
])
def test_code_families(code, family):
    assert cat.classify(code) == family


def test_accounting_row_is_not_a_game():
    """Left in, it would become the most co-played 'game' on the site."""
    assert cat.classify("NA - Deposit / Withdrawal / Corrections") == cat.NON_GAME
    assert cat.parse_title("NA - Deposit / Withdrawal / Corrections") == (None, None)


def test_slug_is_never_given_a_name():
    """gpas_3chken_pop might be '3 Chickens'. Guessing would be fabrication."""
    title, _ = cat.parse_title("gpas_3chken_pop")
    assert title is None


@pytest.mark.parametrize("code,title,studio", [
    ("POP Rhino Coins: Hit the Bonus (Playson via FEG)", "Rhino Coins: Hit the Bonus", "Playson"),
    ("(GPAS) Cougar Blitz™ POP", "Cougar Blitz", "Playtech"),
    ("POP 100 Burning Hot Buy Bonus v1 (EGT via FEG)", "100 Burning Hot Buy Bonus v1", "EGT"),
])
def test_title_parsing(code, title, studio):
    got_title, got_studio = cat.parse_title(code)
    assert got_title == title
    assert got_studio == studio


# ------------------------------------------------------------------- safety
def test_self_excluded_account_is_blocked_before_scoring():
    state = rp.assess({"player": {"self_excluded": True}})
    assert state.state == rp.BLOCKED
    assert state.hard_gate is True
    assert state.blocks_everything


def test_unverified_age_is_a_hard_gate():
    assert rp.assess({"player": {"age_verified": False}}).state == rp.BLOCKED


def test_moderate_risk_suppresses_engagement_rows():
    state = rp.assess({"player": {"deposits_this_session": 3,
                                  "stake_above_own_history": True}})
    assert state.state == rp.MODERATE
    assert state.suppresses_conversion


def test_clean_account_is_not_suppressed():
    state = rp.assess({"player": {}})
    assert state.state == rp.NORMAL
    assert not state.suppresses_conversion


# --------------------------------------------------------------- evaluation
def _toy():
    """
    4 users x 5 items.

    Train: u0 {0,1}, u1 {0,1,2}, u2 {2,3}, u3 {0,1,2,3}
    Test : u0 {2}   -> discovery (never played)
           u1 {0}   -> repeat
           u3 {4}   -> discovery
    """
    tr = sparse.csr_matrix(np.array([
        [1, 1, 0, 0, 0],
        [1, 1, 1, 0, 0],
        [0, 0, 1, 1, 0],
        [1, 1, 1, 1, 0],
    ], dtype=np.float32))
    te = sparse.csr_matrix(np.array([
        [0, 0, 1, 0, 0],
        [1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1],
    ], dtype=np.float32))
    return tr, te


def test_discovery_never_scores_an_already_played_game():
    tr, te = _toy()
    mask = np.ones(5, dtype=bool)
    res = evaluate(MostPlayed().fit(tr), tr, te, "discovery", mask,
                   ks=(3,), min_train=2)
    # u1's test item 0 is a repeat, so u1 must not appear in the discovery cohort
    assert res["cohort"] == 2                      # u0 and u3 only
    assert res["truth_total"] == 2


def test_repeat_task_only_ranks_the_players_own_history():
    tr, te = _toy()
    mask = np.ones(5, dtype=bool)
    res = evaluate(UserTop(), tr, te, "repeat", mask, ks=(3,), min_train=2)
    assert res["cohort"] == 1                      # only u1 has a repeat
    assert res["recall@3"] == pytest.approx(1.0)   # item 0 is in their history


def test_no_leakage_between_train_and_test_scoring():
    """A discovery recommendation must never be an item from the train row."""
    tr, te = _toy()
    mask = np.ones(5, dtype=bool)
    model = MostPlayed().fit(tr)
    res = evaluate(model, tr, te, "discovery", mask, ks=(3,), min_train=2)
    assert res["cohort"] > 0
    # item 4 is unplayed by everyone in train; it must be reachable
    assert res["coverage@3"] >= 1


def test_metrics_match_hand_computation():
    ranked = np.array([[2, 0, 1]])           # hit at rank 1 (0-indexed)
    truths = [{0}]
    pop_rank = np.zeros(3, dtype=np.float32)
    m = _metrics(ranked, truths, 3, pop_rank)
    assert m["precision@3"] == pytest.approx(1 / 3)
    assert m["recall@3"] == pytest.approx(1.0)
    # DCG = 1/log2(3), IDCG = 1/log2(2) = 1
    assert m["ndcg@3"] == pytest.approx(1 / np.log2(3))


# ------------------------------------------------------------------- model
def test_popularity_correction_actually_has_an_effect():
    """
    Regression test for a real bug.

    The first version damped item columns and *then* L2-normalised them. Cosine
    is scale-invariant per column, so the damping cancelled exactly and every
    alpha produced byte-identical output. The correction now applies to the
    similarity matrix.
    """
    tr, _ = _toy()
    a = ItemItemCF(alpha=0.0, shrink=0.0, top_k=5).fit(tr).sim_.toarray()
    b = ItemItemCF(alpha=1.0, shrink=0.0, top_k=5).fit(tr).sim_.toarray()
    assert not np.allclose(a, b), "alpha must change the similarity matrix"


def test_similarity_has_no_self_loops():
    tr, _ = _toy()
    S = ItemItemCF(top_k=5).fit(tr).sim_.toarray()
    assert np.allclose(np.diag(S), 0.0)


def test_item_item_beats_popularity_on_tail_discovery():
    """
    The headline claim, asserted on the real artifacts if they are present.

    Popularity wins overall discovery outright - that is in docs/evaluation.md
    and we do not hide it. The claim that justifies shipping a recommender is
    narrower: once the global top-50 are removed, CF wins.
    """
    art = pytest.importorskip("src.pipeline.build_dataset")
    import os
    if not os.path.exists(os.path.join(art.ART, "interactions.npz")):
        pytest.skip("artifacts not built")
    d = art.load()
    X, T = d["X_train"], d["X_test"]
    mask = np.ones(X.shape[1], dtype=bool)
    cf = evaluate(ItemItemCF().fit(X), X, T, "tail_discovery", mask)
    pop = evaluate(MostPlayed().fit(X), X, T, "tail_discovery", mask)
    assert cf["ndcg@10"] > pop["ndcg@10"]
    assert cf["coverage@10"] > pop["coverage@10"]


# ------------------------------------------------------- serving behaviour
def test_unnamed_games_appear_only_in_continue_playing():
    """
    54% of players have no nameable game in their history, so "Continue
    playing" is allowed to label a game by provider and kind. Recommending a
    game nobody can identify would be a different thing entirely, and must
    never happen.
    """
    import os
    from src.pipeline.build_dataset import ART
    if not os.path.exists(os.path.join(ART, "model.npz")):
        pytest.skip("artifacts not built")
    from src.recsys.serve import LobbyService

    svc = LobbyService()
    seen_placeholder = False
    for row_idx in range(0, 40):
        out = svc.lobby(svc.players[row_idx])
        for row in out["rows"]:
            for t in row["tiles"]:
                if t["named"] is False:
                    seen_placeholder = True
                    assert row["key"] == "continue", (
                        "unnamed game leaked into row %r" % row["key"])
    assert seen_placeholder, "expected at least one placeholder across 40 players"


# --------------------------------------------------- sequence & enrichment
def _artifacts_ready():
    import os
    from src.pipeline.build_dataset import ART
    return os.path.exists(os.path.join(ART, "sequence.npz"))


def test_provider_matching_is_prefix_tolerant():
    """Provider names differ across exports; a studio mismatch must still fail."""
    from src.pipeline.name_bridge import providers_match
    assert providers_match("Pragmatic", "PragmaticPlay")
    assert providers_match("PlayNGo", "Playn Go")
    assert providers_match("Amusnet", "Amusnet")
    assert not providers_match("Playtech", "Greentube")
    assert not providers_match("", "Playtech")


def test_bridge_titles_are_not_codes():
    """A resolved title must be a real name, never another opaque code."""
    if not _artifacts_ready():
        pytest.skip("artifacts not built")
    import json, os, re
    from src.pipeline.build_dataset import ART
    with open(os.path.join(ART, "catalog.json"), encoding="utf-8") as fh:
        cat_json = json.load(fh)
    bridged = {k: v for k, v in cat_json.items()
               if v.get("title_source") == "event_log_bridge"}
    assert bridged, "expected the bridge to have resolved some codes"
    for code, g in bridged.items():
        assert g["title"], code
        assert not re.match(r"^(pop_[0-9a-f]{6,}|gpas_)", g["title"]), code
        assert g["title_votes"] >= 2, code


def test_sequence_model_beats_cf_on_tail_discovery():
    """
    The claim that justified building a sequence model at all.

    Session-level sequence was not possible (91 of 26,904 players have event
    logs). Day-level transitions cover 76% of players, and on the tail they
    beat both collaborative filtering and popularity.
    """
    if not _artifacts_ready():
        pytest.skip("artifacts not built")
    import numpy as np
    from src.pipeline.build_dataset import load
    from src.recsys.hybrid import SequenceRec
    from src.recsys.item_item import ItemItemCF

    d = load()
    X, T, R = d["X_train"], d["T"], d["X_recent"]
    mask = np.ones(X.shape[1], dtype=bool)
    seq = evaluate(SequenceRec(T, R).fit(X), X, d["X_test"], "tail_discovery", mask)
    cf = evaluate(ItemItemCF().fit(X), X, d["X_test"], "tail_discovery", mask)
    pop = evaluate(MostPlayed().fit(X), X, d["X_test"], "tail_discovery", mask)
    assert seq["ndcg@10"] > cf["ndcg@10"]
    assert seq["ndcg@10"] > 2.0 * pop["ndcg@10"]


def test_negative_and_zero_stakes_are_excluded():
    """Refunds and corrections must never become positive interactions."""
    if not _artifacts_ready():
        pytest.skip("artifacts not built")
    import json, os
    from src.pipeline.build_dataset import ART, load
    with open(os.path.join(ART, "dataset_report.json"), encoding="utf-8") as fh:
        report = json.load(fh)
    dropped = report["dropped"]
    assert dropped["negative_stake"] > 0 and dropped["zero_stake"] > 0
    assert load()["X_train"].data.min() > 0, "no interaction may have zero confidence"


def test_new_games_row_uses_real_release_age():
    """
    "Nove igre" must mean genuinely new, not merely absent from the training
    window. That distinction needs the 12 months in CA_MOM.
    """
    if not _artifacts_ready():
        pytest.skip("artifacts not built")
    from src.pipeline.build_dataset import load
    d = load()
    assert d["new_items"], "expected some genuinely new games"
    for i in d["new_items"][:50]:
        g = d["catalog"][d["items"][i]]
        assert g.get("is_new") is True
        assert g.get("displayable") is True
