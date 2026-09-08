"""
Freeze the live lobby into a static JSON bundle.

    python -m src.dashboard.export_static

The API needs Python, the artifacts and a running server. A judge should not
need any of that to see the product. This precomputes real lobbies for a
spread of players - including the responsible-play states - so the same page
can be opened from a plain file or a static host with no backend at all.

Nothing here is mocked: every row, tile, badge and explanation is the actual
output of `LobbyService.lobby()`.
"""
from __future__ import annotations

import json
import os

from src.pipeline.build_dataset import ART
from src.recsys.serve import LobbyService

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data.json")
N_PLAYERS = 12
ROW_SIZE = 10

# The states a reviewer should be able to see without holding an account in one.
STATES = {
    "normal": {},
    "moderate": {"deposits_this_session": 3, "stake_above_own_history": True},
    "blocked": {"self_excluded": True},
}


def pick_players(svc, n):
    """A spread of history sizes, so the demo is not all power users."""
    scored = []
    for i, pid in enumerate(svc.players):
        row = svc.X[i]
        named = int(sum(svc.displayable[j] for j in row.indices))
        if named >= 3:
            scored.append((named, int(row.nnz), pid))
    scored.sort(reverse=True)
    if len(scored) <= n:
        return [p for _, _, p in scored]
    step = max(len(scored) // n, 1)
    return [scored[i * step][2] for i in range(n)]


def main():
    svc = LobbyService()
    players = pick_players(svc, N_PLAYERS)
    print("exporting %d players" % len(players))

    bundle = {"players": [], "lobbies": {}, "static_lobby": None, "meta": {}}

    for n, pid in enumerate(players, 1):
        i = svc.row_of[pid]
        named = int(sum(svc.displayable[j] for j in svc.X[i].indices))
        bundle["players"].append({
            "id": pid, "label": "Igrac %02d" % n,
            "games_played": int(svc.X[i].nnz), "named_games": named,
            "also_bets_sport": svc.sb.get(pid),
        })
        for state, flags in STATES.items():
            bundle["lobbies"]["%s|%s" % (pid, state)] = svc.lobby(
                pid, player=flags, row_size=ROW_SIZE)

    # The counterfactual: what every player sees today. Same code path, but no
    # personalised rows - which is exactly what an unknown player receives.
    bundle["static_lobby"] = svc.lobby("__anonymous__", row_size=ROW_SIZE)

    for name in ("dataset_report.json", "model_report.json"):
        path = os.path.join(ART, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                bundle["meta"][name.split(".")[0]] = json.load(fh)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(OUT) / 1024
    print("wrote %s (%.0f KB, %d lobbies)" % (OUT, size, len(bundle["lobbies"])))


if __name__ == "__main__":
    main()
