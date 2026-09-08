"""
Game catalogue: turn PSK's `reporting_bet_type` codes into displayable games.

The stake export identifies games by a code, and those codes come in several
families. Only one of them carries a real name:

    POP 100 Burning Hot Buy Bonus v1 (EGT via FEG)   -> named
    (GPAS) Big Bad Wolf: Cash Collect & Link™ POP    -> named
    pop_9f571b7a_egtfeg                              -> opaque hash
    gpas_3chken_pop                                  -> slug, NOT a name
    3cb                                              -> short code, NOT a name
    NA - Deposit / Withdrawal / Corrections          -> not a game at all

Two rules this module exists to enforce:

1. **A slug is not a name.** `gpas_3chken_pop` might be "3 Chickens" or might
   not. Decoding it would be guesswork, so those games are trainable but never
   displayable.
2. **Non-game rows must leave the matrix.** The deposit/withdrawal correction
   row would otherwise look like the most co-played "game" on the site and
   poison every similarity score.

Games that cannot be named are still used for training - their co-occurrence
carries real signal - they are simply never shown to a player.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

# --- code families ---------------------------------------------------------
RE_OPAQUE = re.compile(r"^pop_[0-9a-f]{6,}_[a-z0-9]+$", re.I)
RE_GPAS_SLUG = re.compile(r"^gpas_[a-z0-9_]+$", re.I)
RE_SHORT_CODE = re.compile(r"^[a-z0-9]{1,6}$", re.I)

# Accounting rows that are not gameplay. Matched loosely on purpose.
NON_GAME_MARKERS = ("deposit", "withdrawal", "correction")

NAMED = "named"
OPAQUE = "opaque_hash"
SLUG = "gpas_slug"
SHORT = "short_code"
NON_GAME = "non_game"

DISPLAYABLE = {NAMED}
TRAINABLE = {NAMED, OPAQUE, SLUG, SHORT}

# --- title cleanup ---------------------------------------------------------
RE_GPAS_PREFIX = re.compile(r"^\(GPAS\)\s*", re.I)
RE_POP_PREFIX = re.compile(r"^POP\s+", re.I)
RE_STUDIO = re.compile(r"\s*\(([^)]+?)\s+via\s+FEG\)\s*$", re.I)
RE_TRAILING_POP = re.compile(r"(?:\s+A\d)?\s+POP\s*$", re.I)


def classify(code: str) -> str:
    """Which family a raw code belongs to."""
    c = (code or "").strip()
    if not c:
        return NON_GAME
    low = c.lower()
    if low.startswith("na -") or sum(m in low for m in NON_GAME_MARKERS) >= 2:
        return NON_GAME
    if RE_OPAQUE.match(c):
        return OPAQUE
    if RE_GPAS_SLUG.match(c):
        return SLUG
    if RE_SHORT_CODE.match(c) and " " not in c:
        return SHORT
    return NAMED


@dataclass
class Game:
    code: str
    family: str
    title: Optional[str] = None      # display name; None unless family == named
    studio: Optional[str] = None     # from the name, e.g. "EGT", "Promatic"
    provider: Optional[str] = None   # platform provider column
    game_type: Optional[str] = None  # src_game_type, e.g. "POP Slots"
    players: int = 0
    stake: float = 0.0

    @property
    def displayable(self) -> bool:
        return self.family in DISPLAYABLE and bool(self.title)

    def as_dict(self) -> Dict:
        return {
            "code": self.code, "family": self.family, "title": self.title,
            "studio": self.studio, "provider": self.provider,
            "game_type": self.game_type, "players": self.players,
            "stake": round(self.stake, 2), "displayable": self.displayable,
        }


def parse_title(code: str):
    """Extract (title, studio) from a named code. Returns (None, None) if unnamed."""
    if classify(code) != NAMED:
        return None, None

    s = code.strip()
    studio = None

    m = RE_STUDIO.search(s)
    if m:
        studio = m.group(1).strip()
        s = RE_STUDIO.sub("", s)

    had_gpas = bool(RE_GPAS_PREFIX.match(s))
    s = RE_GPAS_PREFIX.sub("", s)
    s = RE_POP_PREFIX.sub("", s)
    if had_gpas:
        # "(GPAS) Big Bad Wolf™ POP" -> the trailing POP is platform noise.
        s = RE_TRAILING_POP.sub("", s)
        studio = studio or "Playtech"

    s = s.replace("™", "").replace("®", "")
    s = re.sub(r"\s{2,}", " ", s).strip(" -–—")

    if not s or len(s) < 2:
        return None, None
    return s, studio


def build(rows: Iterable[Dict]) -> Dict[str, Game]:
    """
    Build the catalogue from CA_Player rows.

    `rows` yields dicts with reporting_bet_type / reporting_provider_info /
    src_game_type / PlayerID / total_stake_amt.
    """
    games: Dict[str, Game] = {}
    seen_players: Dict[str, set] = {}

    for r in rows:
        code = (r.get("reporting_bet_type") or "").strip()
        if not code:
            continue
        g = games.get(code)
        if g is None:
            fam = classify(code)
            title, studio = parse_title(code)
            g = games[code] = Game(
                code=code, family=fam, title=title, studio=studio,
                provider=(r.get("reporting_provider_info") or None),
                game_type=(r.get("src_game_type") or None),
            )
            seen_players[code] = set()
        seen_players[code].add(r.get("PlayerID"))
        try:
            g.stake += float(r.get("total_stake_amt") or 0.0)
        except (TypeError, ValueError):
            pass

    for code, g in games.items():
        g.players = len(seen_players[code])
    return games


def summarise(games: Dict[str, Game]) -> Dict[str, Dict]:
    """Counts per family - used by the pipeline to report what it kept."""
    out: Dict[str, Dict] = {}
    for g in games.values():
        b = out.setdefault(g.family, {"games": 0, "stake": 0.0})
        b["games"] += 1
        b["stake"] += g.stake
    total = sum(b["stake"] for b in out.values()) or 1.0
    for b in out.values():
        b["stake_share_pct"] = round(100 * b["stake"] / total, 1)
        b["stake"] = round(b["stake"], 2)
    return out


def displayable_codes(games: Dict[str, Game]) -> List[str]:
    return sorted(c for c, g in games.items() if g.displayable)
