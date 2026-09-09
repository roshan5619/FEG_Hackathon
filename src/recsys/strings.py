"""
Lobby copy, in Croatian and English.

The product ships Croatian: PSK is a Croatian brand and the row names
deliberately mirror the live casino.psk.hr lobby (*Popularno*, *Nove igre*,
*Jackpoti*) so the new rows read as part of that product rather than as a
bolted-on demo.

English exists because the people evaluating this prototype do not read
Croatian, and a reviewer who cannot read the row headings cannot judge whether
the rows make sense. `?lang=hr` switches back, which also demonstrates that the
copy is a translation layer rather than something hard-coded.

Nothing here is model output. Every string is fixed UI copy; the one piece of
generated text - the per-tile reason - is assembled from these templates plus a
game title that comes from the catalogue.
"""
from __future__ import annotations

from typing import Any, Dict

DEFAULT_LANG = "en"

STRINGS: Dict[str, Dict[str, Any]] = {
    "hr": {
        # rows: (title, subtitle)
        "row_continue": ("Nastavi igrati", "Igre koje si nedavno igrao"),
        "row_for_you": ("Preporuceno za tebe", "Na temelju onoga sto si igrao"),
        "row_discover": ("Otkrij nesto novo",
                         "Izvan top 50 - gdje personalizacija pobjeduje"),
        "row_jackpot": ("Jackpoti", "Igre s jackpotom, poredane prema tvom ukusu"),
        "row_popular": ("Popularno", "Najigranije na PSK-u - red koji PSK vec ima"),
        "row_new": ("Nove igre", "Prvi put objavljene u zadnja 3 mjeseca"),
        # per-tile reasons
        "why_recent": "Nedavno si igrao",
        "why_popular": "Popularno na PSK-u",
        "why_similar": "Slicno igrama koje igras",
        "why_jackpot": "Jackpot igra",
        "why_new": "Novo na PSK-u",
        "why_unnamed": "U tvojoj povijesti · naziv nije u katalogu",
        "why_cf": "Jer igras %s",
        "why_seq": "Nakon %s igraci cesto igraju ovu",
        # badges
        "badge_new": "NOVO",
        "badge_jackpot": "JACKPOT",
        "badge_rising": "U PORASTU",
        # placeholder titles for games with no name in the data
        "kind_slot": "slot",
        "kind_live": "live igra",
        "kind_game": "igra",
    },
    "en": {
        "row_continue": ("Continue playing", "Games you played recently"),
        "row_for_you": ("Picked for you", "Based on what you have played"),
        "row_discover": ("Discover something new",
                         "Outside the top 50 - where personalisation wins"),
        "row_jackpot": ("Jackpots", "Jackpot games, ordered to your taste"),
        "row_popular": ("Popular", "Most played on PSK - the row PSK already has"),
        "row_new": ("New games", "First released in the last 3 months"),
        "why_recent": "You played this recently",
        "why_popular": "Popular on PSK",
        "why_similar": "Similar to games you play",
        "why_jackpot": "Jackpot game",
        "why_new": "New on PSK",
        "why_unnamed": "In your history · title not in the catalogue",
        "why_cf": "Because you play %s",
        "why_seq": "After %s, players often play this",
        "badge_new": "NEW",
        "badge_jackpot": "JACKPOT",
        "badge_rising": "RISING",
        "kind_slot": "slot",
        "kind_live": "live game",
        "kind_game": "game",
    },
}


def normalise(lang: Any) -> str:
    """Anything unrecognised falls back to the default rather than erroring."""
    code = str(lang or "").strip().lower()[:2]
    return code if code in STRINGS else DEFAULT_LANG


def t(lang: Any) -> Dict[str, Any]:
    return STRINGS[normalise(lang)]
