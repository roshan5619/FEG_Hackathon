"""
Tests for the demo login.

Two of these matter more than the rest, because they encode a legal distinction
that is easy to get backwards:

  * An **age-unverified** account is refused a session entirely. Croatia's Act
    on Measures for Socially Responsible Organisation of Games of Chance
    requires the check before play is allowed, so it cannot be a filter applied
    after sign-in.
  * A **self-excluded** account signs in successfully. Self-exclusion blocks
    inducements, not account access - the person must still reach their account
    and support. Their lobby returns zero recommendations instead.

Getting either the wrong way round would be a real compliance failure, so both
are asserted rather than described.
"""
import os

import pytest
from fastapi.testclient import TestClient

from src.api import auth
from src.api.app import app

pytestmark = pytest.mark.skipif(
    not os.path.exists(auth.USERS_PATH),
    reason="demo accounts not generated (python -m src.api.make_demo_users)")

PW = auth.DEMO_PASSWORD


@pytest.fixture
def client():
    return TestClient(app)


def _account(label):
    for u in auth.users()["users"]:
        if u.get("rg_label") == label:
            return u
    pytest.skip("no %s demo account" % label)


# --------------------------------------------------------------- passwords
def test_no_plaintext_password_is_stored():
    """The whole point of hashing. A regression here is a real problem."""
    with open(auth.USERS_PATH, encoding="utf-8") as fh:
        raw = fh.read()
    assert PW not in raw
    for u in auth.users()["users"]:
        assert "password" not in u
        assert len(u["hash"]) == 64 and len(u["salt"]) == 32


def test_password_hash_round_trips():
    rec = auth.hash_password("hunter2")
    assert auth.verify_password("hunter2", rec["salt"], rec["hash"])
    assert not auth.verify_password("hunter3", rec["salt"], rec["hash"])


def test_two_accounts_have_different_salts():
    salts = [u["salt"] for u in auth.users()["users"]]
    assert len(set(salts)) == len(salts), "salts must be per-user"


# ---------------------------------------------------------------- sessions
def test_session_round_trips_and_rejects_tampering():
    token = auth.issue_session("ana.k")
    assert auth.read_session(token)["username"] == "ana.k"
    blob, sig = token.rsplit(".", 1)
    assert auth.read_session(blob + ".deadbeef") is None
    assert auth.read_session(None) is None
    assert auth.read_session("garbage") is None


def test_expired_session_is_rejected():
    assert auth.read_session(auth.issue_session("ana.k", ttl=-1)) is None


def test_public_user_never_leaks_the_hash():
    pub = auth.public_user(auth.users()["users"][0])
    assert "hash" not in pub and "salt" not in pub


# ------------------------------------------------------------------- login
def test_wrong_password_and_unknown_user_are_indistinguishable(client):
    """Never reveal whether a username exists."""
    a = client.post("/login", json={"username": "ana.k", "password": "nope"})
    b = client.post("/login", json={"username": "nobody", "password": PW})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]
    assert auth.COOKIE_NAME not in client.cookies


def test_valid_login_returns_a_personalised_lobby(client):
    normal = _account("NORMAL")
    r = client.post("/login", json={"username": normal["username"], "password": PW})
    assert r.status_code == 200
    body = client.get("/lobby").json()
    assert body["user"]["username"] == normal["username"]
    assert any(row["personalised"] for row in body["rows"])


def test_age_unverified_is_refused_a_session(client):
    """
    The Croatian gate: the check precedes play, so no session is issued at all.
    """
    u = _account("AGE_UNVERIFIED")
    r = client.post("/login", json={"username": u["username"], "password": PW})
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["state"] == "BLOCKED"
    assert detail["required_surfaces"]
    assert auth.COOKIE_NAME not in client.cookies
    assert client.get("/lobby").status_code == 401


def test_self_excluded_signs_in_but_gets_nothing_to_play(client):
    """
    Self-exclusion blocks inducements, NOT account access. Both halves matter.
    """
    u = _account("BLOCKED")
    r = client.post("/login", json={"username": u["username"], "password": PW})
    assert r.status_code == 200, "a self-excluded person must still reach their account"
    body = client.get("/lobby").json()
    assert body["rows"] == []
    assert body["responsible_play"]["state"] == "BLOCKED"
    assert body["required_surfaces"]


def test_moderate_risk_keeps_only_continue_playing(client):
    u = _account("MODERATE")
    client.post("/login", json={"username": u["username"], "password": PW})
    body = client.get("/lobby").json()
    assert [r["key"] for r in body["rows"]] == ["continue"]
    assert body["suppressed_rows"]


def test_lobby_requires_a_session(client):
    assert client.get("/lobby").status_code == 401
    client.cookies.set(auth.COOKIE_NAME, "forged.token")
    assert client.get("/lobby").status_code == 401


def test_logout_ends_the_session(client):
    normal = _account("NORMAL")
    client.post("/login", json={"username": normal["username"], "password": PW})
    assert client.get("/lobby").status_code == 200
    client.post("/logout")
    assert client.get("/lobby").status_code == 401


# ------------------------------------------------------------------- pages
def test_root_serves_the_landing_page_when_signed_out(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"This is the lobby everyone sees" in r.content


def test_fresh_clears_a_live_session(client):
    """
    The demo opens with `?fresh=1`. Sessions last 8 hours, so without this,
    giving the demo twice in one afternoon lands the second audience on the
    lobby and the "here is what everyone sees today" opening is lost.
    """
    normal = _account("NORMAL")
    client.post("/login", json={"username": normal["username"], "password": PW})
    assert client.get("/lobby").status_code == 200

    r = client.get("/?fresh=1")
    assert b"This is the lobby everyone sees" in r.content, "must land signed out"
    assert client.get("/me").json()["authenticated"] is False
    assert client.get("/lobby").status_code == 401

    # and signing back in still works, so the reset is not destructive
    client.post("/login", json={"username": normal["username"], "password": PW})
    assert client.get("/lobby").status_code == 200


def test_root_is_never_cached(client):
    """
    `/` returns a different page depending on the session cookie, so a cached
    copy is a real bug, not a nicety: the browser served the signed-out page
    from cache after a successful sign-in and the login silently appeared to
    do nothing.

    TestClient has no HTTP cache, so this asserts the header rather than the
    behaviour - the header is what the browser acts on.
    """
    r = client.get("/")
    assert "no-store" in r.headers.get("cache-control", "")
    assert "Cookie" in r.headers.get("vary", "")


def test_language_switch_translates_the_rows(client):
    """
    The product ships Croatian; English exists so a reviewer who does not read
    Croatian can still judge whether the rows make sense. Both must work, and
    an unknown code must fall back rather than error.
    """
    normal = _account("NORMAL")
    client.post("/login", json={"username": normal["username"], "password": PW})
    en = [r["title"] for r in client.get("/lobby?lang=en").json()["rows"]]
    hr = [r["title"] for r in client.get("/lobby?lang=hr").json()["rows"]]
    assert "Continue playing" in en and "Nastavi igrati" in hr
    assert en != hr and len(en) == len(hr)
    # unknown language falls back to the default, it does not 500
    assert [r["title"] for r in client.get("/lobby?lang=zz").json()["rows"]] == en


def test_anonymous_lobby_has_no_personalised_rows(client):
    rows = client.get("/anonymous-lobby").json()["rows"]
    assert rows, "an anonymous visitor should still see something"
    assert not any(r["personalised"] for r in rows)


def test_demo_accounts_endpoint_exposes_no_secrets(client):
    d = client.get("/demo-accounts").json()
    assert len(d["accounts"]) >= 10
    blob = str(d)
    for u in auth.users()["users"]:
        assert u["hash"] not in blob and u["salt"] not in blob
