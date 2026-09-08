"""
Generate the 12 demo accounts.

    python -m src.api.make_demo_users

Accounts are chosen from the real model so that switching between them visibly
changes the lobby: heavy players, mid, narrow, some with sportsbook crossover,
and some whose history is mostly unnameable game codes so the placeholder
behaviour is on show rather than hidden.

Four accounts additionally carry responsible-play states, so the gates can be
demonstrated rather than described.

ON THE NAMES
`ana.k`, `marko.p` and the rest are **invented labels**. They are attached to
pre-hashed anonymous player identifiers and are derived from nothing: the
export contains no name, age, gender, location or any other personal attribute,
so none could be revealed even by accident. The play history behind each
account is real; the person is not.

Passwords are written as PBKDF2 hashes with per-user salts. The plaintext is
printed once here and lives on the login page for the demo - it is never
persisted to disk.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

import numpy as np

from src.api.auth import USERS_PATH, hash_password

# Invented labels. Not derived from any datum in the export.
PERSONAS = [
    ("ana.k", "Ana K."), ("marko.p", "Marko P."), ("ivana.s", "Ivana S."),
    ("luka.b", "Luka B."), ("petra.m", "Petra M."), ("nikola.t", "Nikola T."),
    ("maja.r", "Maja R."), ("filip.d", "Filip D."), ("sara.v", "Sara V."),
    ("tomislav.j", "Tomislav J."), ("lucija.h", "Lucija H."), ("davor.z", "Davor Z."),
]
PASSWORD = "psk2026"          # same for every demo account, shown on screen

# The four accounts that carry a responsible-play state, by index into PERSONAS.
RG_ACCOUNTS = {
    9: {"label": "MODERATE",
        "flags": {"deposits_this_session": 3, "stake_above_own_history": True},
        "note": "Rizik otkriven — svi redovi koji potiču igru su povučeni."},
    10: {"label": "BLOCKED",
         "flags": {"self_excluded": True},
         "note": "Samoisključen — prijava radi, ali nema nijedne preporuke."},
    11: {"label": "AGE_UNVERIFIED",
         "flags": {"age_verified": False},
         "note": "Dob nije potvrđena — prijava se odbija prije pristupa igrama."},
}


def pick_players(svc, n_each=(3, 3, 3)) -> List[int]:
    """Rows spread across heavy / mid / narrow history, favouring variety."""
    heavy, mid, narrow = [], [], []
    for i in range(min(len(svc.players), 3000)):
        idx = svc.X[i].indices
        named = int(sum(svc.displayable[j] for j in idx))
        if named < 4:
            continue
        n = len(idx)
        bucket = heavy if n >= 100 else (mid if n >= 20 else narrow)
        bucket.append((named, i))
    for b in (heavy, mid, narrow):
        b.sort(reverse=True)

    picks: List[int] = []
    for bucket, want in zip((heavy, mid, narrow), n_each):
        step = max(len(bucket) // max(want, 1), 1)
        picks += [bucket[k * step][1] for k in range(want) if k * step < len(bucket)]
    return picks


def describe(svc, row: int) -> Dict:
    idx = svc.X[row].indices
    named = int(sum(svc.displayable[j] for j in idx))
    rec = svc.R[row].toarray().ravel()
    top_code = svc.items[int(np.argmax(rec))] if rec.max() > 0 else None
    top_title = (svc.catalog.get(top_code) or {}).get("title") if top_code else None
    sb = svc.sb.get(svc.players[row])
    return {
        "games_played": int(len(idx)),
        "named_games": named,
        "top_game": top_title or "(naziv nije u katalogu)",
        "also_bets_sport": sb["top_sport"] if sb else None,
    }


def main():
    from src.recsys.serve import LobbyService
    svc = LobbyService()

    rows = pick_players(svc)
    # Top up to 12 with further named-history players, preferring crossover.
    seen = set(rows)
    extra = []
    for i in range(min(len(svc.players), 3000)):
        if i in seen:
            continue
        named = int(sum(svc.displayable[j] for j in svc.X[i].indices))
        if named >= 6:
            extra.append((0 if svc.sb.get(svc.players[i]) else 1, -named, i))
    extra.sort()
    rows += [i for _, _, i in extra[: max(0, len(PERSONAS) - len(rows))]]
    rows = rows[: len(PERSONAS)]

    out = []
    for n, (row, (username, display)) in enumerate(zip(rows, PERSONAS)):
        rec = hash_password(PASSWORD)
        profile = describe(svc, row)
        entry = {
            "username": username,
            "display_name": display,
            "player_id": svc.players[row],
            "salt": rec["salt"], "hash": rec["hash"], "rounds": rec["rounds"],
            "profile": profile,
            "flags": {},
            "rg_label": "NORMAL",
            "note": None,
        }
        if n in RG_ACCOUNTS:
            spec = RG_ACCOUNTS[n]
            entry["flags"] = spec["flags"]
            entry["rg_label"] = spec["label"]
            entry["note"] = spec["note"]
        out.append(entry)

    doc = {
        "_readme": (
            "Demo accounts for the PSK recommender prototype. Usernames and "
            "display names are INVENTED LABELS attached to pre-hashed anonymous "
            "player identifiers; the export contains no personal attribute of "
            "any kind, so none is revealed here. The play history behind each "
            "account is real. Passwords are PBKDF2-SHA256 hashes with per-user "
            "salts - no plaintext is stored. This is prototype auth, not "
            "production auth: no rate limiting, lockout, rotation or MFA."
        ),
        "password_hint": "All demo accounts share one password, shown on the login page.",
        "users": out,
    }
    with open(USERS_PATH, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)

    print("wrote %s (%d accounts)" % (USERS_PATH, len(out)))
    print("password for every account: %s\n" % PASSWORD)
    print("  %-12s %-14s %6s %6s %-12s %s" %
          ("username", "display", "games", "named", "rg", "top game"))
    for u in out:
        p = u["profile"]
        print("  %-12s %-14s %6d %6d %-12s %s" %
              (u["username"], u["display_name"], p["games_played"],
               p["named_games"], u["rg_label"], p["top_game"][:34]))


if __name__ == "__main__":
    main()
