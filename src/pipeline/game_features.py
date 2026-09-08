"""
Per-game content features from CA_MOM.csv (12 months, game x month, no player).

This file was unused until now, and it is the only place several important
signals exist:

* **Game age** - the first month a title recorded any stake. This is what makes
  the "Nove igre" row honest: previously it listed games with no history in the
  training window, which conflates "brand new" with "nobody played it".
* **Momentum** - stake in the most recent months against the preceding ones.
  Feeds a "rising" signal that pure popularity cannot express.
* **Payout ratio** - total_win_amt / total_stake_amt per game, a volatility and
  RTP proxy. Used ONLY as a similarity feature. It is deliberately never shown
  to a player and never used to rank: advertising "this game pays out more" on
  a gambling platform is exactly the inducement the EU AI Act prohibits.
* **Jackpot / bonus eligibility** - whether a game records jackpot stake or is
  commonly played with bonus funds.
"""
from __future__ import annotations

import collections
import csv
from typing import Dict

MIN_STAKE_FOR_RATIO = 1000.0     # below this a payout ratio is noise
RECENT_MONTHS = 3


def build(path: str) -> Dict[str, dict]:
    months = set()
    stake = collections.defaultdict(lambda: collections.defaultdict(float))
    win = collections.defaultdict(float)
    jackpot = collections.defaultdict(float)
    bonus = collections.defaultdict(float)
    total = collections.defaultdict(float)
    gtype: Dict[str, str] = {}
    provider: Dict[str, str] = {}

    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            code = r["reporting_bet_type"]
            m = r["month_start_date"]
            months.add(m)

            def num(k):
                try:
                    return float(r.get(k) or 0.0)
                except (TypeError, ValueError):
                    return 0.0

            s = num("total_stake_amt")
            stake[code][m] += s
            total[code] += s
            win[code] += num("total_win_amt")
            jackpot[code] += num("jackpot_stake_amt")
            bonus[code] += num("bonus_stake_amt")
            gtype.setdefault(code, r.get("src_game_type"))
            provider.setdefault(code, r.get("reporting_provider_info"))

    ordered = sorted(months)
    recent = set(ordered[-RECENT_MONTHS:])
    prior = set(ordered[:-RECENT_MONTHS])
    index = {m: i for i, m in enumerate(ordered)}

    out: Dict[str, dict] = {}
    for code, by_month in stake.items():
        active = [m for m, v in by_month.items() if v > 0]
        if not active:
            continue
        first = min(active)
        recent_stake = sum(v for m, v in by_month.items() if m in recent)
        prior_stake = sum(v for m, v in by_month.items() if m in prior)
        tot = total[code]

        # Momentum: share of lifetime stake in the last RECENT_MONTHS, scaled
        # against what an even spread would give. 1.0 = flat, >1 = rising.
        even = RECENT_MONTHS / max(len(ordered), 1)
        momentum = (recent_stake / tot / even) if tot > 0 and even > 0 else 0.0

        out[code] = {
            "first_month": first,
            "months_active": len(active),
            "age_months": len(ordered) - index[first],
            "is_new": index[first] >= len(ordered) - RECENT_MONTHS,
            "lifetime_stake": round(tot, 2),
            "recent_stake": round(recent_stake, 2),
            "momentum": round(momentum, 3),
            "payout_ratio": (round(win[code] / tot, 4) if tot >= MIN_STAKE_FOR_RATIO else None),
            "has_jackpot": jackpot[code] > 0,
            "jackpot_share": round(jackpot[code] / tot, 4) if tot > 0 else 0.0,
            "bonus_share": round(bonus[code] / tot, 4) if tot > 0 else 0.0,
            "game_type": gtype.get(code),
            "provider": provider.get(code),
        }
    return {"months": ordered, "games": out}
