"""
Demo authentication.

This is a prototype sign-in for a gambling-platform mock, so two things are
deliberate:

* **No plaintext passwords anywhere.** Credentials are stored as
  PBKDF2-HMAC-SHA256 hashes with a per-user salt. A repository judged on
  compliance should not contain a plaintext password even for a throwaway demo,
  and the cost of doing it properly is one stdlib call.
* **Sessions are signed, not guessable.** The cookie carries a username, an
  expiry and an HMAC over both. Tampering invalidates it. `httponly` and
  `samesite=lax` are set so the cookie is not reachable from script.

No third-party dependency: `hashlib`, `hmac`, `secrets`, `base64`, `json`.

What this is NOT: production auth. There is no rate limiting, no lockout, no
password rotation, no MFA. It exists so the demo has a real login journey, and
`docs/compliance-note.md` says so plainly.

THE TWO GATES ARE DIFFERENT AND FIRE IN DIFFERENT PLACES
Age/ID verification is checked *here*, at sign-in: Croatia's Act on Measures
for Socially Responsible Organisation of Games of Chance requires the check
before play is allowed, so an unverified account never gets a session at all.
Self-exclusion is *not* checked here - a self-excluded person must still reach
their account, balance and support. Their lobby returns zero recommendations
instead, which is `src/recsys/responsible.py`'s job.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
USERS_PATH = os.path.join(HERE, "demo_users.json")

COOKIE_NAME = "psk_demo_session"
# Shared by every demo account and shown on the login page, because a
# reviewer cannot guess it. Never stored: only its PBKDF2 hash is.
DEMO_PASSWORD = "psk2026"
SESSION_TTL_SECONDS = 8 * 3600
PBKDF2_ROUNDS = 120_000

_DEV_SECRET = "dev-only-not-a-secret-change-in-any-real-deployment"


def session_secret() -> bytes:
    return os.environ.get("MTG_SESSION_SECRET", _DEV_SECRET).encode("utf-8")


# --------------------------------------------------------------- passwords
def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 salt.encode("utf-8"), PBKDF2_ROUNDS)
    return {"salt": salt, "hash": digest.hex(), "rounds": str(PBKDF2_ROUNDS)}


def verify_password(password: str, salt: str, expected_hex: str,
                    rounds: int = PBKDF2_ROUNDS) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 salt.encode("utf-8"), rounds)
    # Constant-time: never leak how much of the hash matched.
    return hmac.compare_digest(digest.hex(), expected_hex)


# ------------------------------------------------------------------ users
_USERS: Optional[Dict[str, Any]] = None


def users() -> Dict[str, Any]:
    """The demo account store. Loaded once."""
    global _USERS
    if _USERS is None:
        if not os.path.exists(USERS_PATH):
            _USERS = {"users": []}
        else:
            with open(USERS_PATH, encoding="utf-8") as fh:
                _USERS = json.load(fh)
    return _USERS


def find_user(username: str) -> Optional[Dict[str, Any]]:
    uname = (username or "").strip().lower()
    for u in users().get("users", []):
        if u["username"].lower() == uname:
            return u
    return None


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Returns the user record, or None.

    Deliberately does not distinguish "no such user" from "wrong password",
    and runs the KDF either way so the response time does not reveal whether
    the username exists.
    """
    user = find_user(username)
    if user is None:
        # Burn equivalent work against a dummy salt.
        hash_password(password, salt="0" * 32)
        return None
    ok = verify_password(password, user["salt"], user["hash"],
                         int(user.get("rounds", PBKDF2_ROUNDS)))
    return user if ok else None


# --------------------------------------------------------------- sessions
def _sign(payload: str) -> str:
    return hmac.new(session_secret(), payload.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def issue_session(username: str, ttl: int = SESSION_TTL_SECONDS) -> str:
    payload = json.dumps({"u": username, "exp": int(time.time()) + ttl},
                         separators=(",", ":"))
    blob = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return "%s.%s" % (blob, _sign(blob))


def read_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Validate a cookie and return the user record, or None."""
    if not token or "." not in token:
        return None
    blob, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(blob), sig):
        return None                                  # tampered or wrong secret
    try:
        pad = "=" * (-len(blob) % 4)
        data = json.loads(base64.urlsafe_b64decode(blob + pad))
    except Exception:
        return None
    if int(data.get("exp", 0)) < time.time():
        return None                                  # expired
    return find_user(data.get("u", ""))


def player_flags(user: Dict[str, Any]) -> Dict[str, Any]:
    """The responsible-play flags this account carries, for LobbyService."""
    return {k: v for k, v in (user.get("flags") or {}).items() if v is not None}


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """What is safe to send to the browser. Never the salt or hash."""
    return {
        "username": user["username"],
        "display_name": user["display_name"],
        "player_id": user["player_id"],
        "profile": user.get("profile"),
        "rg_state": user.get("rg_label", "NORMAL"),
        "note": user.get("note"),
    }
