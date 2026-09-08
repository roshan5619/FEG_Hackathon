"""
Serving: turn a player id into the rows of a personalised lobby.

The widget set is the product answer to what the evaluation actually found
(docs/evaluation.md), which is not what we expected going in:

* Global popularity **beats** collaborative filtering outright on next-game
  prediction (NDCG@10 0.305 vs 0.056). Players overwhelmingly try what is
  already popular. So the Trending row stays popularity-driven - the row PSK
  already ships works, and replacing it would make the lobby worse.
* Once the global top-50 are removed, that reverses: item-item CF beats
  popularity **2.25x** on NDCG with **18x** the catalogue coverage (680 games
  against 37). And **76.5%** of all discovery plays live in that tail.

So the lobby is deliberately hybrid: popularity owns the head, CF owns the
tail, and neither pretends to do the other's job.

Every row passes through `responsible.assess` before it is returned. A blocked
account gets no recommendations at all - not a filtered list, none.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from src.pipeline.build_dataset import load
from src.recsys import responsible as rp
from src.recsys.train import HEAD_N, load_model

DEFAULT_ROW_SIZE = 8
MAX_PER_PROVIDER = 3         # diversity cap inside a single row


@dataclass
class Tile:
    code: str
    title: str
    provider: Optional[str]
    game_type: Optional[str]
    score: float
    why: str

    def as_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "title": self.title, "provider": self.provider,
                "game_type": self.game_type, "score": round(float(self.score), 5),
                "why": self.why}


@dataclass
class Row:
    key: str
    title: str
    subtitle: str
    source: str
    tiles: List[Tile] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "title": self.title, "subtitle": self.subtitle,
                "source": self.source, "tiles": [t.as_dict() for t in self.tiles]}


class LobbyService:
    """Loads artifacts once; answers per-player lobby requests."""

    def __init__(self):
        d = load()
        m = load_model()
        self.X = d["X_train"]
        self.items: List[str] = list(d["items"])
        self.players: List[str] = list(d["players"])
        self.catalog: Dict[str, Dict] = d["catalog"]
        self.sim = m["sim"]
        self.pop = m["pop"]
        self.cold = set(int(i) for i in m["cold"])

        self.row_of = {p: i for i, p in enumerate(self.players)}
        n = len(self.items)

        # Only nameable games are ever shown. Opaque codes still train the
        # model; they must never reach a tile.
        self.displayable = np.zeros(n, dtype=bool)
        self.displayable[np.asarray(d["displayable"], dtype=np.int64)] = True

        self.head = set(int(i) for i in np.argsort(-self.pop)[:HEAD_N])
        self.provider_of = [
            (self.catalog.get(c) or {}).get("provider") for c in self.items]

    # -- helpers -----------------------------------------------------------
    def _tile(self, idx: int, score: float, why: str) -> Optional[Tile]:
        code = self.items[idx]
        g = self.catalog.get(code) or {}
        if not g.get("displayable") or not g.get("title"):
            return None
        return Tile(code=code, title=g["title"], provider=g.get("provider"),
                    game_type=g.get("game_type"), score=score, why=why)

    def _take(self, order: np.ndarray, scores: np.ndarray, why_fn, n: int,
              exclude: set) -> List[Tile]:
        """Walk a ranked index list, applying display, diversity and dedup rules."""
        out: List[Tile] = []
        per_provider: Dict[Optional[str], int] = {}
        for idx in order:
            i = int(idx)
            if i in exclude or not self.displayable[i]:
                continue
            prov = self.provider_of[i]
            if per_provider.get(prov, 0) >= MAX_PER_PROVIDER:
                continue
            t = self._tile(i, float(scores[i]), why_fn(i))
            if t is None:
                continue
            out.append(t)
            per_provider[prov] = per_provider.get(prov, 0) + 1
            exclude.add(i)
            if len(out) >= n:
                break
        return out

    def _cf_scores(self, urow: int) -> np.ndarray:
        return np.asarray((self.X[urow] @ self.sim).todense(), dtype=np.float32).ravel()

    def _why_because(self, urow: int, item: int) -> str:
        """The literal top contributor to this score, not a post-hoc story."""
        played = self.X[urow].indices
        if len(played) == 0:
            return "Popular right now"
        contrib = (np.asarray(self.X[urow, played].todense()).ravel()
                   * np.asarray(self.sim[played, item].todense()).ravel())
        if contrib.max() <= 0:
            return "Similar to games you play"
        src = self.items[int(played[int(np.argmax(contrib))])]
        g = self.catalog.get(src) or {}
        title = g.get("title")
        return "Because you played %s" % title if title else "Similar to games you play"

    # -- the lobby ---------------------------------------------------------
    def lobby(self, player_id: str, player: Optional[Dict[str, Any]] = None,
              row_size: int = DEFAULT_ROW_SIZE) -> Dict[str, Any]:
        state = rp.assess({"player": player or {}}, _NullFeatures())

        known = player_id in self.row_of
        envelope: Dict[str, Any] = {
            "player_id": player_id,
            "known_player": known,
            "responsible_play": state.as_dict(),
            "rows": [],
            "suppressed_rows": [],
        }

        if state.blocks_everything:
            # Nothing from the recommender reaches a blocked account.
            envelope["rows"] = []
            envelope["suppressed_rows"] = ["all"]
            envelope["required_surfaces"] = state.required_surfaces
            return envelope

        rows: List[Row] = []
        used: set = set()

        if known:
            urow = self.row_of[player_id]
            played = set(int(i) for i in self.X[urow].indices)
            cf = self._cf_scores(urow)
            cf_order = np.argsort(-cf)

            # 1. Continue playing - their own history, strongest first.
            own = self.X[urow].toarray().ravel()
            own_order = np.argsort(-own)
            tiles = self._take(own_order[own[own_order] > 0], own,
                               lambda i: "You have played this", row_size, set())
            if tiles:
                rows.append(Row("continue", "Continue playing",
                                "Games you already play, most-played first",
                                "user_history", tiles))
                used |= {self.items.index(t.code) for t in tiles} if False else set()

            # 2. Because you played X - item-item, explainable, tail-friendly.
            excl = set(played)
            tiles = self._take(cf_order, cf, lambda i: self._why_because(urow, i),
                               row_size, excl)
            if tiles:
                rows.append(Row("because", "Picked for you",
                                "From players with similar taste",
                                "item_item_cf", tiles))

            # 3. Discover - the same model with the blockbusters removed. This
            #    is the row the evaluation says CF actually wins.
            excl2 = set(played) | self.head | {i for r in rows for i in
                                               [self.items.index(t.code) for t in r.tiles]}
            tiles = self._take(cf_order, cf,
                               lambda i: self._why_because(urow, i), row_size, excl2)
            if tiles:
                rows.append(Row("discover", "Discover something new",
                                "Beyond the top 50 - where personalisation beats popularity",
                                "item_item_cf_tail", tiles))
        else:
            envelope["cold_start"] = (
                "Player not in the training window; serving popularity and new "
                "releases only. A collaborative model cannot personalise without "
                "history, and pretending otherwise would be dishonest.")

        # 4. Trending - popularity. Kept because it measurably wins the head.
        pop_order = np.argsort(-self.pop)
        tiles = self._take(pop_order, self.pop, lambda i: "Popular across PSK",
                           row_size, set())
        if tiles:
            rows.append(Row("trending", "Trending now",
                            "Most played across all players - the row PSK ships today",
                            "most_played", tiles))

        # 5. New releases - games with no training history. No CF can reach
        #    these, and they are 12.1% of all discovery. They need their own row.
        cold_sorted = sorted(self.cold, key=lambda i: -self.pop[i])
        tiles = self._take(np.asarray(cold_sorted, dtype=np.int64),
                           self.pop, lambda i: "New to PSK", row_size, set())
        if tiles:
            rows.append(Row("new", "New releases",
                            "No play history yet - unreachable by any recommender",
                            "cold_items", tiles))

        # Responsible play can suppress engagement-driving rows wholesale.
        if state.suppresses_conversion:
            keep = [r for r in rows if r.key in ("continue",)]
            envelope["suppressed_rows"] = [r.key for r in rows if r not in keep]
            rows = keep

        envelope["rows"] = [r.as_dict() for r in rows]
        if state.required_surfaces:
            envelope["required_surfaces"] = state.required_surfaces
        return envelope


class _NullFeatures:
    """
    responsible.assess was written against session features. The recommender has
    no session, so it passes a null object: only the account-level hard gates
    and the caller-supplied risk flags apply here.
    """
    elapsed_s = 0.0
