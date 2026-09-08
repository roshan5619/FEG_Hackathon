"""
Resolve opaque game codes to real titles.

The stake export identifies most games by codes like `pop_9f571b7a_egtfeg`,
carrying 83% of all stake and no title. The GA4 event logs carry real titles
for ~900 games but cover only 91 players. Neither file has a join key.

They can still be joined behaviourally. All 91 event-log players appear in the
stake export, so for a given (player, day) we know both which titles they
launched and which codes they staked on. Co-occurrence across many such days,
constrained to matching providers, identifies the pairing.

Validation that this is not wishful matching: the method independently
recovered `gpas_3chken_pop` -> "4 Crazy Cluckers" (111 votes) and
`gpas_wpisto_pop` -> "Mega Fire Blaze: Wild Pistolero" (48 votes). Both slugs
decode to their resolved titles, which the algorithm had no way to read.

Yield: ~127 previously unnameable games, ~33% of total stake.
"""
from __future__ import annotations

import collections
import csv
import re
from typing import Dict, Iterable, Tuple

MIN_VOTES = 2          # a pairing needs at least this many co-occurring days
DOMINANCE = 2.0        # ...and must beat the runner-up by this factor
MIN_DAY_SHARE = 0.5    # ...and appear on at least half the code's shared days


def _norm(p: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (p or "").lower())


def providers_match(a: str, b: str) -> bool:
    """
    Provider names differ across exports ("Pragmatic" vs "PragmaticPlay",
    "PlayNGo" vs "Playn Go"), so match on a normalised prefix rather than
    equality. This is a hard constraint: a pairing across two different
    studios is wrong however many days it co-occurs on.
    """
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a)


def read_event_launches(paths: Iterable[str]):
    """(player, day) -> {title}, plus title -> provider."""
    csv.field_size_limit(10 ** 7)
    by_day = collections.defaultdict(set)
    title_provider: Dict[str, str] = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("event_name") != "casino_game_launch":
                    continue
                title = r.get("game_name")
                if not title or title == "null":
                    continue
                by_day[(r["PlayerID"], (r.get("timestamp") or "")[:10])].add(title)
                prov = r.get("provider")
                if prov and prov != "null":
                    title_provider[title] = prov
    return by_day, title_provider


def resolve(stake_rows: Iterable[dict], event_paths: Iterable[str]) -> Dict[str, dict]:
    """
    Returns {code: {title, votes, support, provider}} for confidently resolved codes.

    `stake_rows` must be re-iterable material from CA_Player.csv.
    """
    ev_by_day, title_provider = read_event_launches(event_paths)

    ca_by_day = collections.defaultdict(set)
    code_provider: Dict[str, str] = {}
    for r in stake_rows:
        ca_by_day[(r["PlayerID"], r["local_transaction_date"])].add(r["reporting_bet_type"])
        code_provider[r["reporting_bet_type"]] = r.get("reporting_provider_info")

    co = collections.defaultdict(collections.Counter)
    code_days = collections.Counter()
    for key, titles in ev_by_day.items():
        codes = ca_by_day.get(key)
        if not codes:
            continue
        for code in codes:
            code_days[code] += 1
            for title in titles:
                if providers_match(code_provider.get(code), title_provider.get(title)):
                    co[code][title] += 1

    out: Dict[str, dict] = {}
    for code, counter in co.items():
        if not counter:
            continue
        ranked = counter.most_common(2)
        best, votes = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        if (votes >= MIN_VOTES
                and votes >= DOMINANCE * max(runner_up, 1)
                and votes / max(code_days[code], 1) >= MIN_DAY_SHARE):
            out[code] = {
                "title": best,
                "votes": int(votes),
                "support": int(code_days[code]),
                "provider": code_provider.get(code),
                "source": "event_log_bridge",
            }
    return out
