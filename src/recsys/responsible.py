"""
Responsible play. Runs before any recommendation is generated, and can veto all
of them.

Two distinct mechanisms live here and they must not be confused:

1. **Hard gates.** Age/identity not verified, or a hit on the register of
   excluded players, or an active self-exclusion. These are legal
   preconditions, not scores. Nothing the intelligence layer produces can
   override them, and the check runs before any surface renders - Croatia's
   Act on Measures for Socially Responsible Organisation of Games of Chance
   requires the check to precede play, so a UI checkbox does not satisfy it.

2. **Graded inversion.** The same signals that drive engagement, read with the
   opposite objective. As indicators accumulate, the lobby's target moves from
   surfacing more to surfacing less: at MODERATE every engagement-driving row is
   withheld and only "Continue playing" survives.

Every decision this module makes is returned with the reason that produced it,
so the whole path is auditable after the fact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Graded states, least to most restrictive.
NORMAL = "NORMAL"
MILD = "MILD"
MODERATE = "MODERATE"
SEVERE = "SEVERE"
BLOCKED = "BLOCKED"

ORDER = [NORMAL, MILD, MODERATE, SEVERE, BLOCKED]

# Thresholds are configuration, not law. config/thresholds.example.yaml holds
# the deployable copy; these are the defaults the prototype runs on.
LONG_SESSION_S = 60 * 60
VERY_LONG_SESSION_S = 2 * 60 * 60
DEPOSIT_REENTRY_LIMIT = 2


@dataclass
class ResponsiblePlayState:
    state: str
    reasons: List[str] = field(default_factory=list)
    hard_gate: bool = False
    required_surfaces: List[str] = field(default_factory=list)

    @property
    def suppresses_conversion(self) -> bool:
        """True once engagement-driving rows must be withheld."""
        return ORDER.index(self.state) >= ORDER.index(MODERATE)

    @property
    def blocks_everything(self) -> bool:
        return self.state == BLOCKED

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "hard_gate": self.hard_gate,
            "reasons": self.reasons,
            "required_surfaces": self.required_surfaces,
            "conversion_nudges_suppressed": self.suppresses_conversion,
        }


def assess(payload: Dict[str, Any], _unused: Optional[Any] = None) -> ResponsiblePlayState:
    """
    Evaluate hard gates first, then grade behavioural risk.

    The second argument is vestigial - this module was written against session
    features and the recommender has no session. Account-level flags supplied by
    the caller are what matter here, and they are never inferred.
    """
    player = payload.get("player") or {}
    reasons: List[str] = []

    # ---- hard gates -------------------------------------------------------
    if player.get("self_excluded"):
        return ResponsiblePlayState(
            BLOCKED,
            ["Active self-exclusion on the account."],
            hard_gate=True,
            required_surfaces=["self_exclusion_status", "support_contact"],
        )
    if player.get("on_exclusion_register"):
        return ResponsiblePlayState(
            BLOCKED,
            ["Match against the national register of excluded players."],
            hard_gate=True,
            required_surfaces=["exclusion_notice", "support_contact"],
        )
    if player.get("age_verified") is False:
        return ResponsiblePlayState(
            BLOCKED,
            ["Age and identity not verified for this account."],
            hard_gate=True,
            required_surfaces=["age_verification"],
        )
    if player.get("deposit_limit_reached"):
        return ResponsiblePlayState(
            SEVERE,
            ["Deposit limit reached - limit is a hard gate, not a prompt."],
            hard_gate=True,
            required_surfaces=["limit_status", "cool_off"],
        )

    # ---- graded behavioural indicators -----------------------------------
    score = 0
    duration = float(payload.get("session_duration_s") or 0)
    if duration >= VERY_LONG_SESSION_S:
        score += 2
        reasons.append("Session past %d hours." % (VERY_LONG_SESSION_S // 3600))
    elif duration >= LONG_SESSION_S:
        score += 1
        reasons.append("Session past one hour.")

    deposits = int(player.get("deposits_this_session") or 0)
    if deposits >= DEPOSIT_REENTRY_LIMIT:
        score += 2
        reasons.append("Repeated deposits inside a single session (%d)." % deposits)

    if player.get("stake_above_own_history"):
        score += 2
        reasons.append("Stakes running above the player's own established pattern.")

    if player.get("chasing_losses"):
        score += 2
        reasons.append("Re-stake pattern consistent with loss chasing.")

    if player.get("limit_change_requested"):
        score += 1
        reasons.append("Requested a limit increase during the session.")

    if player.get("night_play_streak", 0) >= 3:
        score += 1
        reasons.append("Sustained overnight play across consecutive days.")

    state = SEVERE if score >= 5 else MODERATE if score >= 3 else MILD if score >= 1 else NORMAL

    required: List[str] = []
    if state == MILD:
        required = ["session_timer"]
    elif state == MODERATE:
        required = ["session_timer", "reality_check"]
    elif state == SEVERE:
        required = ["session_timer", "reality_check", "limit_tools", "cool_off"]

    if not reasons:
        reasons = ["No harmful-play indicators in this session."]

    return ResponsiblePlayState(state, reasons, hard_gate=False, required_surfaces=required)
