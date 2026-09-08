"""
Recommendation API — a thin HTTP shell over src.recsys.serve.

    uvicorn src.api.app:app --reload --port 8000

    GET /                     the personalised lobby (dashboard)
    GET /docs                 interactive API docs
    GET /health               model provenance and size
    GET /players              a few sample player ids to try
    GET /recommendations/{id} the widget rows for one player
    GET /evaluation           the measured results behind the widget design

No model is fitted here. `src.recsys.train` writes artifacts/model.npz offline
and this process loads it once at import, so a request is a handful of sparse
lookups.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from src import __version__
from src.pipeline.build_dataset import ART
from src.recsys.serve import LobbyService

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DASHBOARD = os.path.join(REPO, "src", "dashboard", "index.html")

app = FastAPI(
    title="PSK Game Recommender",
    version=__version__,
    description=(
        "Personalised casino lobby for psk.hr. Rows are driven by a blend of "
        "day-to-day play sequence and item-item collaborative filtering; the "
        "popularity row PSK already ships is kept because it wins the head. "
        "Responsible-play gates run before anything is generated. "
        "Team Q'Makers, FEG Innovation Challenge 2026."
    ),
)

_service: Optional[LobbyService] = None


def service() -> LobbyService:
    global _service
    if _service is None:
        _service = LobbyService()
    return _service


def _read(name: str) -> Dict[str, Any]:
    path = os.path.join(ART, name)
    if not os.path.exists(path):
        raise HTTPException(404, "%s not found - run the pipeline first" % name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@app.get("/health")
def health() -> Dict[str, Any]:
    svc = service()
    model = _read("model_report.json")
    data = _read("dataset_report.json")
    return {
        "status": "ok",
        "version": __version__,
        "model": model,
        "dataset": {
            "sources": data.get("sources"),
            "date_range": data.get("date_range"),
            "split_date": data.get("split_date"),
            "months_of_history": data.get("months_of_history"),
            "players": data.get("players"),
            "games_trainable": data.get("games_trainable"),
            "games_displayable": data.get("games_displayable"),
            "games_named_by_bridge": data.get("games_named_by_bridge"),
            "new_games": data.get("new_games"),
            "jackpot_games": data.get("jackpot_games"),
            "sequence_transitions": data.get("sequence_transitions"),
            "sb_crossover_players": data.get("sb_crossover_players"),
            "dropped_rows": data.get("dropped"),
        },
        "catalogue_displayable": int(svc.displayable.sum()),
    }


@app.get("/players")
def players(limit: int = Query(12, ge=1, le=100)) -> Dict[str, Any]:
    """
    Sample player ids with enough named history to make a good demo.

    Ids are the pre-hashed identifiers from the FEG export; no personal data.
    """
    svc = service()
    out = []
    for i in range(min(len(svc.players), 4000)):
        named = int(sum(svc.displayable[j] for j in svc.X[i].indices))
        if named >= 5:
            out.append({"player_id": svc.players[i],
                        "games_played": int(svc.X[i].nnz),
                        "named_games": named})
        if len(out) >= limit:
            break
    return {"players": out}


@app.get("/recommendations/{player_id}")
def recommendations(
    player_id: str,
    row_size: int = Query(8, ge=1, le=20),
    self_excluded: bool = False,
    age_verified: bool = True,
    deposits_this_session: int = 0,
    stake_above_own_history: bool = False,
    chasing_losses: bool = False,
) -> Dict[str, Any]:
    """
    The personalised lobby for one player.

    The responsible-play flags are query parameters so a reviewer can watch the
    suppression behaviour without needing an account in a particular state. In
    production they come from the player record, never from the recommender.
    """
    player = {
        "self_excluded": self_excluded or None,
        "age_verified": age_verified,
        "deposits_this_session": deposits_this_session or None,
        "stake_above_own_history": stake_above_own_history or None,
        "chasing_losses": chasing_losses or None,
    }
    player = {k: v for k, v in player.items() if v is not None}
    return service().lobby(player_id, player=player, row_size=row_size)


@app.get("/evaluation")
def evaluation() -> Dict[str, Any]:
    """The measured results the widget design is based on."""
    return _read("eval_full.json")


@app.get("/", include_in_schema=False)
def dashboard():
    if os.path.exists(DASHBOARD):
        return FileResponse(DASHBOARD, media_type="text/html")
    return JSONResponse({"detail": "dashboard not built", "try": "/docs"}, status_code=404)
