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

from fastapi import Cookie, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from src import __version__
from src.api import auth
from src.pipeline.build_dataset import ART
from src.recsys import responsible as rp
from src.recsys.serve import LobbyService

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DASHBOARD = os.path.join(REPO, "src", "dashboard", "index.html")
BACKEND = os.path.join(REPO, "src", "dashboard", "backend.html")
LOGIN = os.path.join(REPO, "src", "dashboard", "login.html")

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


@app.get("/explain/{player_id}/{code:path}")
def explain(player_id: str, code: str) -> Dict[str, Any]:
    """
    Why the trained ranker scored this game for this player.

    Returns the feature vector and each feature's contribution. For logistic
    regression the contributions are exact (coefficient x standardised value,
    summing to the logit); the response says so via `exact`.
    """
    out = service().explain(player_id, code)
    if out is None:
        raise HTTPException(
            404, "no explanation available - unknown player/game, or the "
                 "ranker has not been trained (run: python -m src.cli train)")
    g = service().catalog.get(code) or {}
    out["game"] = {"code": code, "title": g.get("title"), "provider": g.get("provider")}
    return out


@app.get("/model")
def model_report() -> Dict[str, Any]:
    """What was fitted, and what the ranker learned. Feeds /backend."""
    out = {"model": _read("model_report.json"), "dataset": _read("dataset_report.json")}
    path = os.path.join(ART, "ranker_report.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            out["ranker"] = json.load(fh)
    path = os.path.join(ART, "eval_full.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            out["evaluation"] = json.load(fh)
    return out


@app.get("/profile/{player_id}")
def profile(player_id: str, top: int = Query(12, ge=1, le=50)) -> Dict[str, Any]:
    """What the model actually knows about one player. Feeds /backend."""
    import numpy as np
    svc = service()
    if player_id not in svc.row_of:
        raise HTTPException(404, "unknown player")
    u = svc.row_of[player_id]
    rec = svc.R[u].toarray().ravel()
    hist = svc.X[u].toarray().ravel()
    order = np.argsort(-rec)[:top]
    games, providers = [], {}
    for i in order:
        if rec[i] <= 0:
            continue
        code = svc.items[int(i)]
        g = svc.catalog.get(code) or {}
        games.append({"code": code, "title": g.get("title"),
                      "provider": g.get("provider"), "named": bool(g.get("displayable")),
                      "recency_weight": round(float(rec[i]), 4),
                      "confidence": round(float(hist[i]), 4)})
        p = g.get("provider") or "?"
        providers[p] = providers.get(p, 0.0) + float(hist[i])
    total = sum(providers.values()) or 1.0
    return {
        "player_id": player_id,
        "n_games": int(svc.X[u].nnz),
        "also_bets_sport": svc.sb.get(player_id),
        "top_games": games,
        "providers": sorted(({"provider": k, "share": round(v / total, 4)}
                             for k, v in providers.items()),
                            key=lambda d: -d["share"])[:8],
    }


# ------------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/login")
def login(req: LoginRequest, response: Response) -> Dict[str, Any]:
    """
    Sign in to the demo.

    The age/ID gate lives HERE, not in the lobby. Croatia's Act on Measures for
    Socially Responsible Organisation of Games of Chance requires the check
    before play is allowed, so an unverified account is refused a session
    entirely rather than issued one and filtered afterwards.

    Self-exclusion is deliberately NOT checked here: a self-excluded person must
    still reach their account and support. Their lobby returns zero
    recommendations instead - see src/recsys/responsible.py.
    """
    user = auth.authenticate(req.username, req.password)
    if user is None:
        # Identical message either way: never reveal whether a username exists.
        raise HTTPException(401, "Neispravno korisnicko ime ili lozinka.")

    flags = auth.player_flags(user)
    state = rp.assess({"player": flags})
    if state.hard_gate and not flags.get("self_excluded"):
        raise HTTPException(403, {
            "message": "Prijava odbijena: provjera dobi/identiteta nije prosla.",
            "state": state.state,
            "reasons": state.reasons,
            "required_surfaces": state.required_surfaces,
        })

    response.set_cookie(
        auth.COOKIE_NAME, auth.issue_session(user["username"]),
        max_age=auth.SESSION_TTL_SECONDS, httponly=True, samesite="lax")
    return {"ok": True, "user": auth.public_user(user)}


@app.post("/logout")
def logout(response: Response) -> Dict[str, Any]:
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


@app.get("/me")
def me(psk_demo_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    """Who is signed in, if anyone. Drives both pages."""
    user = auth.read_session(psk_demo_session)
    if user is None:
        return {"authenticated": False}
    return {"authenticated": True, "user": auth.public_user(user)}


@app.get("/demo-accounts")
def demo_accounts() -> Dict[str, Any]:
    """
    The demo credentials, for the login page to display.

    Safe to expose: invented personas over anonymous ids on a prototype, and a
    judge cannot guess them. Never includes a salt or a hash.
    """
    store = auth.users()
    return {
        "password": auth.DEMO_PASSWORD,
        "note": store.get("_readme"),
        "accounts": [auth.public_user(u) for u in store.get("users", [])],
    }


@app.get("/lobby")
def lobby(psk_demo_session: Optional[str] = Cookie(default=None),
          row_size: int = Query(10, ge=1, le=20)) -> Dict[str, Any]:
    """
    The signed-in player's lobby.

    Responsible-play flags come from the account record server-side, never from
    query parameters, so a browser cannot talk itself out of a gate.
    """
    user = auth.read_session(psk_demo_session)
    if user is None:
        raise HTTPException(401, "Not signed in.")
    out = service().lobby(user["player_id"],
                          player=auth.player_flags(user), row_size=row_size)
    out["user"] = auth.public_user(user)
    return out


@app.get("/anonymous-lobby")
def anonymous_lobby(row_size: int = Query(10, ge=1, le=20)) -> Dict[str, Any]:
    """What a visitor who has not signed in sees. Identical for everyone."""
    return service().lobby("__anonymous__", row_size=row_size)


@app.get("/backend", include_in_schema=False)
def backend_view():
    """The visualisations: pipeline, learned weights, per-tile attribution."""
    if os.path.exists(BACKEND):
        return FileResponse(BACKEND, media_type="text/html")
    return JSONResponse({"detail": "backend view not built", "try": "/model"},
                        status_code=404)


@app.get("/", include_in_schema=False)
def root(psk_demo_session: Optional[str] = Cookie(default=None),
         fresh: Optional[str] = None):
    """
    Landing page when signed out; the personalised lobby when signed in.

    `?fresh=1` forces the signed-out landing page and clears the cookie. The
    demo opens with it because the session lasts 8 hours: without it, giving
    the demo twice in one afternoon lands the second audience straight on the
    lobby, and the "this is what everyone sees today" opening is lost.
    """
    if fresh:
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(auth.COOKIE_NAME)
        return response
    signed_in = auth.read_session(psk_demo_session) is not None
    page = DASHBOARD if signed_in else LOGIN
    if os.path.exists(page):
        return FileResponse(page, media_type="text/html")
    return JSONResponse({"detail": "page not built", "try": "/docs"}, status_code=404)
