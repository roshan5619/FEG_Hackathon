"""
Serving: turn a player id into the rows of a personalised PSK lobby.

Row names and structure mirror the live casino.psk.hr lobby (Popularno, Nove
igre, Jackpoti) so this reads as a feature of that product rather than a
separate dashboard. Two rows are new and are the point of the work:
*Nastavi igrati* and *Preporuceno za tebe*.

The personalised rows are ordered by a TRAINED ranker. Two stages: item-item
collaborative filtering and a day-to-day sequence model generate ~200
candidates, then a scikit-learn logistic regression - fitted with a loss
function on labelled examples - reorders them. Measured on the held-out test
week, tail discovery NDCG@10:

    ranker 0.0708 | blend 0.0655 | sequence 0.0649 | CF 0.0490 | popularity 0.0165

The ranker is 4.28x popularity. If it has not been trained, serving falls back
to the blend rather than failing.

Popularity is deliberately *not* in the blend but *is* still a row. It wins
head prediction outright and cannot be improved on there; it simply cannot
reach the 3,000 games outside the top 50, which is what the personalised rows
are for.

Every row passes through `responsible.assess` before it is returned. A blocked
account gets no recommendations at all - not a filtered list, none.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from src.pipeline.build_dataset import load
from src.recsys import responsible as rp
from src.recsys.strings import DEFAULT_LANG, t as strings_for
from src.recsys.train import HEAD_N, load_model

DEFAULT_ROW_SIZE = 10
MAX_PER_PROVIDER = 3          # diversity cap inside a recommendation row

_KINDS = [
    ("jackpot", "jackpot slot"), ("slot", "slot"), ("roulette", "roulette"),
    ("blackjack", "blackjack"), ("crash", "crash game"), ("arcade", "arcade game"),
    ("card", "card game"), ("table", "table game"),
]


def _kind_of(game_type: Optional[str]) -> str:
    low = (game_type or "").lower()
    for needle, label in _KINDS:
        if needle in low:
            return label
    return "game"


@dataclass
class Tile:
    code: str
    title: str
    provider: Optional[str]
    game_type: Optional[str]
    score: float
    why: str
    named: bool = True
    badges: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "title": self.title, "provider": self.provider,
                "game_type": self.game_type, "score": round(float(self.score), 5),
                "why": self.why, "named": self.named, "badges": self.badges}


@dataclass
class Row:
    key: str
    title: str
    subtitle: str
    source: str
    personalised: bool = False
    tiles: List[Tile] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "title": self.title, "subtitle": self.subtitle,
                "source": self.source, "personalised": self.personalised,
                "tiles": [t.as_dict() for t in self.tiles]}


class LobbyService:
    """Loads artifacts once; answers per-player lobby requests."""

    def __init__(self):
        d = load()
        m = load_model()
        self.X = d["X_train"]
        self.R = d["X_recent"]
        self.items: List[str] = list(d["items"])
        self.players: List[str] = list(d["players"])
        self.catalog: Dict[str, Dict] = d["catalog"]
        self.sb: Dict[str, Dict] = d.get("sb", {})
        self.sim, self.seq = m["sim"], m["seq"]
        self.pop = m["pop"]
        self.w_cf, self.w_seq, self.w_pop = m["w_cf"], m["w_seq"], m["w_pop"]

        self.index_of = {c: i for i, c in enumerate(self.items)}
        self.row_of = {p: i for i, p in enumerate(self.players)}
        n = len(self.items)
        self.displayable = np.zeros(n, dtype=bool)
        self.displayable[np.asarray(d["displayable"], dtype=np.int64)] = True
        self.new_items = list(d.get("new_items", []))
        self.jackpot_items = list(d.get("jackpot_items", []))
        self.head = set(int(i) for i in np.argsort(-self.pop)[:HEAD_N])
        self.provider_of = [(self.catalog.get(c) or {}).get("provider") for c in self.items]
        self.pop_norm = self.pop / max(self.pop.max(), 1e-9)

        # The trained ranker is optional: the lobby still works without it, and
        # says so rather than silently degrading.
        self.ranker = self._load_ranker()

    def _load_ranker(self):
        import os
        from src.pipeline.build_dataset import ART
        if not os.path.exists(os.path.join(ART, "ranker.pkl")):
            return None
        try:
            from src.recsys.features import FeatureBuilder
            from src.recsys.hybrid import SequenceRec
            from src.recsys.item_item import ItemItemCF
            from src.recsys.ranker import LearnedRanker

            cf = ItemItemCF()
            cf.sim_ = self.sim
            seq = SequenceRec(self.seq, self.R)
            seq.T_ = self.seq
            fb = FeatureBuilder(self.X, self.catalog, self.items, self.R)
            return LearnedRanker(cf, seq, fb).load(ART)
        except Exception as exc:                       # pragma: no cover
            print("ranker unavailable (%s); serving candidate models only" % exc)
            return None

    def explain(self, player_id: str, code: str):
        """
        Per-feature contribution behind one recommendation.

        Returns None when the ranker is not built or the inputs are unknown -
        the caller should say so rather than invent an explanation.
        """
        if self.ranker is None or player_id not in self.row_of:
            return None
        item = self.index_of.get(code)
        if item is None:
            return None
        return self.ranker.explain(self.X, self.row_of[player_id], item)

    # -- scoring -----------------------------------------------------------
    def _blend(self, urow: int) -> np.ndarray:
        """The candidate-generation score: components max-normalised, then weighted."""
        def unit(v):
            mx = v.max()
            return v / mx if mx > 0 else v

        cf = unit(np.asarray((self.X[urow] @ self.sim).todense(), dtype=np.float32).ravel())
        sq = unit(np.asarray((self.R[urow] @ self.seq).todense(), dtype=np.float32).ravel())
        out = self.w_cf * cf + self.w_seq * sq
        if self.w_pop:
            out = out + self.w_pop * self.pop_norm
        return out

    def _score(self, urow: int) -> np.ndarray:
        """
        What actually orders the personalised rows.

        The trained ranker when it is available - it measures best on tail
        discovery (0.0708 NDCG@10 against 0.0655 for the blend and 0.0165 for
        popularity). The blend is the fallback, so the lobby still works if the
        ranker has not been trained.
        """
        if self.ranker is None:
            return self._blend(urow)
        try:
            scores = self.ranker.scores(self.X, np.asarray([urow]))[0]
        except Exception:                                   # pragma: no cover
            return self._blend(urow)
        # Candidates the ranker did not score keep a small blend-based score so
        # a row can always be filled; ranked candidates always outrank them.
        floor = self._blend(urow)
        unscored = scores <= -1e29
        scores = np.where(unscored, floor * 1e-6, scores + 1.0)
        return scores.astype(np.float32)

    def _why(self, urow: int, item: int, T) -> str:
        """
        The literal largest contributor to this score - a decomposition, not a
        generated rationale. Sequence and CF are checked separately so the copy
        names the signal that actually fired.
        """
        played = self.X[urow].indices
        if len(played) == 0:
            return T["why_popular"]

        seq_c = (np.asarray(self.R[urow, played].todense()).ravel()
                 * np.asarray(self.seq[played, item].todense()).ravel())
        cf_c = (np.asarray(self.X[urow, played].todense()).ravel()
                * np.asarray(self.sim[played, item].todense()).ravel())
        best_seq = float(seq_c.max()) if seq_c.size else 0.0
        best_cf = float(cf_c.max()) if cf_c.size else 0.0
        if max(best_seq, best_cf) <= 0:
            return T["why_similar"]

        use_seq = best_seq * self.w_seq >= best_cf * self.w_cf
        src = int(played[int(np.argmax(seq_c if use_seq else cf_c))])
        title = (self.catalog.get(self.items[src]) or {}).get("title")
        if not title:
            return T["why_similar"]
        return (T["why_seq"] % title) if use_seq \
            else (T["why_cf"] % title)

    # -- tiles -------------------------------------------------------------
    def _badges(self, g: Dict, T) -> List[str]:
        out = []
        if g.get("is_new"):
            out.append(T["badge_new"])
        if g.get("has_jackpot"):
            out.append(T["badge_jackpot"])
        if (g.get("momentum") or 0) >= 2.0:
            out.append(T["badge_rising"])
        return out

    def _tile(self, idx: int, score: float, why: str, T,
              allow_unnamed: bool = False):
        code = self.items[idx]
        g = self.catalog.get(code) or {}
        if g.get("displayable") and g.get("title"):
            return Tile(code=code, title=g["title"], provider=g.get("provider"),
                        game_type=g.get("game_type"), score=score, why=why,
                        badges=self._badges(g, T))
        if not allow_unnamed:
            return None
        prov = g.get("provider")
        kind = _kind_of(g.get("game_type"))
        return Tile(code=code, title=("%s %s" % (prov, kind)) if prov else kind.capitalize(),
                    provider=prov, game_type=g.get("game_type"), score=score,
                    why=T["why_unnamed"], named=False)

    def _take(self, order, scores, why_fn, n, exclude, T,
              allow_unnamed=False):
        out: List[Tile] = []
        per_provider: Dict[Optional[str], int] = {}
        for idx in order:
            i = int(idx)
            if i in exclude:
                continue
            if not allow_unnamed and not self.displayable[i]:
                continue
            prov = self.provider_of[i]
            # The diversity cap stops one studio owning a row. It must not apply
            # to a player's own history - if they only play Amusnet, so be it.
            if not allow_unnamed and per_provider.get(prov, 0) >= MAX_PER_PROVIDER:
                continue
            t = self._tile(i, float(scores[i]), why_fn(i), T, allow_unnamed)
            if t is None:
                continue
            out.append(t)
            per_provider[prov] = per_provider.get(prov, 0) + 1
            exclude.add(i)
            if len(out) >= n:
                break
        return out

    # -- the lobby ---------------------------------------------------------
    def lobby(self, player_id: str, player: Optional[Dict[str, Any]] = None,
              row_size: int = DEFAULT_ROW_SIZE,
              lang: str = DEFAULT_LANG) -> Dict[str, Any]:
        T = strings_for(lang)
        state = rp.assess({"player": player or {}})
        known = player_id in self.row_of

        envelope: Dict[str, Any] = {
            "player_id": player_id,
            "known_player": known,
            "responsible_play": state.as_dict(),
            "rows": [], "suppressed_rows": [],
        }
        if known and player_id in self.sb:
            envelope["also_bets_sport"] = self.sb[player_id]

        if state.blocks_everything:
            envelope["suppressed_rows"] = ["all"]
            envelope["required_surfaces"] = state.required_surfaces
            return envelope

        rows: List[Row] = []

        if known:
            urow = self.row_of[player_id]
            played = set(int(i) for i in self.X[urow].indices)
            score = self._score(urow)
            order = np.argsort(-score)

            recent = self.R[urow].toarray().ravel()
            n_recent = int((recent > 0).sum())
            tiles = self._take(np.argsort(-recent)[:n_recent], recent,
                               lambda i: T["why_recent"], row_size, set(), T,
                               allow_unnamed=True)
            if tiles:
                rows.append(Row("continue", T["row_continue"][0],
                                T["row_continue"][1],
                                "recency_profile", True, tiles))

            excl = set(played)
            tiles = self._take(order, score, lambda i: self._why(urow, i, T),
                               row_size, excl, T)
            if tiles:
                rows.append(Row("for_you", T["row_for_you"][0],
                                T["row_for_you"][1],
                                "sequence+cf", True, tiles))

            shown = {self.index_of[t.code] for r in rows for t in r.tiles}
            excl2 = set(played) | self.head | shown
            tiles = self._take(order, score, lambda i: self._why(urow, i, T),
                               row_size, excl2, T)
            if tiles:
                rows.append(Row("discover", T["row_discover"][0],
                                T["row_discover"][1],
                                "sequence+cf_tail", True, tiles))

            jp = sorted((i for i in self.jackpot_items if i not in played),
                        key=lambda i: -score[i])
            tiles = self._take(np.asarray(jp, dtype=np.int64), score,
                               lambda i: T["why_jackpot"], row_size, set(), T)
            if tiles:
                rows.append(Row("jackpot", T["row_jackpot"][0],
                                T["row_jackpot"][1],
                                "jackpot+personalised", True, tiles))
        else:
            envelope["cold_start"] = (
                "Player not in the training window; serving popularity and new "
                "releases only. A collaborative model cannot personalise without "
                "history, and pretending otherwise would be dishonest.")

        tiles = self._take(np.argsort(-self.pop), self.pop,
                           lambda i: T["why_popular"], row_size, set(), T)
        if tiles:
            rows.append(Row("popular", T["row_popular"][0],
                            T["row_popular"][1],
                            "most_played", False, tiles))

        new = sorted(self.new_items, key=lambda i: -self.pop[i])
        tiles = self._take(np.asarray(new, dtype=np.int64), self.pop,
                           lambda i: T["why_new"], row_size, set(), T)
        if tiles:
            rows.append(Row("new", T["row_new"][0],
                            T["row_new"][1],
                            "game_age", False, tiles))

        if state.suppresses_conversion:
            keep = [r for r in rows if r.key == "continue"]
            envelope["suppressed_rows"] = [r.key for r in rows if r not in keep]
            rows = keep

        envelope["rows"] = [r.as_dict() for r in rows]
        if state.required_surfaces:
            envelope["required_surfaces"] = state.required_surfaces
        return envelope
