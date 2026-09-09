"""
Capture the demo journey as real screenshots.

    python demo/capture_screenshots.py

Drives headless Chrome over the DevTools protocol against the real API, so
every image is the actual product rendering actual model output. Nothing is
mocked or drawn by hand - if a row is empty in a screenshot, it is empty
because the responsible-play gate emptied it.

These land in demo/screenshots/ and are embedded in the pitch deck. They are
also the fallback if the laptop dies mid-presentation.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

import requests
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(HERE, "screenshots")
sys.path.insert(0, REPO)

W, H = 1440, 950


def free_port():
    """A leftover Chrome on a fixed port silently serves the OLD flags."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = 8077
CDP_PORT = None

CHROME = None
for c in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
    if os.path.exists(c):
        CHROME = c
        break


# ------------------------------------------------------------------ server
def serve():
    import uvicorn
    from src.api.app import app
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="error")


def wait_port(port, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            s.settimeout(0.4)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


# --------------------------------------------------------------------- cdp
class Chrome:
    def __init__(self):
        global CDP_PORT
        CDP_PORT = free_port()
        self.profile = tempfile.mkdtemp(prefix="psk-shot-")
        self.proc = subprocess.Popen([
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-first-run", "--no-default-browser-check",
            "--remote-debugging-port=%d" % CDP_PORT,
            "--remote-allow-origins=*",
            "--user-data-dir=%s" % self.profile,
            "--window-size=%d,%d" % (W, H), "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_port(CDP_PORT, 40):
            raise RuntimeError("Chrome did not open its debugging port")
        url = None
        for _ in range(40):
            try:
                for t in requests.get("http://127.0.0.1:%d/json" % CDP_PORT,
                                      timeout=3).json():
                    if t.get("type") == "page":
                        url = t["webSocketDebuggerUrl"]
                        break
            except Exception:
                pass
            if url:
                break
            time.sleep(0.3)
        if not url:
            raise RuntimeError("no CDP page target")
        self.ws = websocket.create_connection(url, timeout=30)
        self.n = 0
        self.send("Network.enable")
        self.send("Page.enable")
        # Without this Chrome serves "/" from its memory cache after the first
        # visit, so a newly-set session cookie never reaches the server and the
        # signed-in pages render as the signed-out one.
        self.send("Network.setCacheDisabled", cacheDisabled=True)

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method,
                                 "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    def cookie(self, value):
        """
        Set the session cookie by URL, not by domain. The domain form is
        accepted by CDP and then silently ignored, which produced a set of
        screenshots that were all the signed-out page.
        """
        self.send("Network.clearBrowserCookies")
        if value:
            self.send("Network.setCookie", name="psk_demo_session",
                      value=value, url="http://127.0.0.1:%d/" % PORT,
                      path="/", httpOnly=True)

    def expect(self, expr, what):
        """Fail loudly rather than save a screenshot of the wrong page."""
        r = self.js(expr)
        if not (r.get("result") or {}).get("value"):
            raise AssertionError("expected %s - got the wrong page" % what)

    def go(self, path, wait_for=None, settle=2.2):
        # Navigate via about:blank. Going straight from "/" to "/" is treated
        # as a no-op, so the previous page stays up and we screenshot it with
        # the new cookie never applied - which is exactly the bug that made
        # every signed-in shot come out as the landing page.
        self.send("Page.navigate", url="about:blank")
        time.sleep(0.25)
        self.send("Page.navigate", url="http://127.0.0.1:%d%s" % (PORT, path))
        time.sleep(settle)
        if wait_for:
            for _ in range(50):
                r = self.send("Runtime.evaluate",
                              expression="document.querySelectorAll(%r).length"
                                         % wait_for, returnByValue=True)
                if (r.get("result") or {}).get("value", 0) > 0:
                    break
                time.sleep(0.25)
        time.sleep(0.5)

    def js(self, expr):
        return self.send("Runtime.evaluate", expression=expr,
                         returnByValue=True, awaitPromise=True)

    def shot(self, name):
        r = self.send("Page.captureScreenshot", format="png",
                      captureBeyondViewport=False)
        p = os.path.join(OUT, name)
        with open(p, "wb") as fh:
            fh.write(base64.b64decode(r["data"]))
        print("  %-34s %6.0f KB" % (name, os.path.getsize(p) / 1024.0))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        self.proc.terminate()
        shutil.rmtree(self.profile, ignore_errors=True)


def main():
    if CHROME is None:
        sys.exit("No Chrome or Edge found.")
    os.makedirs(OUT, exist_ok=True)

    from src.api import auth
    if not auth.users().get("users"):
        sys.exit("No demo accounts. Run:  python -m src.api.make_demo_users")

    threading.Thread(target=serve, daemon=True).start()
    if not wait_port(PORT, 90):
        sys.exit("API did not start")
    print("API up on :%d" % PORT)

    def tok(username):
        return auth.issue_session(username)

    c = Chrome()
    try:
        # 1 - what every visitor sees today
        c.cookie(None)
        c.go("/", wait_for=".strip")
        c.expect("!!document.querySelector('#loginForm')", "the landing page")
        c.shot("01-anonymous-lobby.png")

        # 2 - the same page, signed in
        c.cookie(tok("ana.k"))
        c.go("/", wait_for="section.row")
        c.expect("document.querySelectorAll('section.row').length >= 5",
                 "the signed-in lobby with six rows")
        c.shot("02-signed-in-lobby.png")

        # 3 - the tile reasons, scrolled to the ranker's row
        c.js("window.scrollTo(0, 420)")
        time.sleep(0.6)
        c.shot("03-why-this-game.png")

        # 4 - a different player, same page
        c.cookie(tok("ivana.s"))
        c.go("/", wait_for="section.row")
        c.expect("!!document.querySelector('#who')", "a signed-in lobby")
        c.shot("04-different-player.png")

        # 5 - self-excluded: signs in, zero rows
        c.cookie(tok("lucija.h"))
        c.go("/", wait_for="#who", settle=2.4)
        c.expect("document.querySelectorAll('section.row').length === 0",
                 "a signed-in page with ZERO recommendation rows")
        c.shot("05-self-excluded-zero-rows.png")

        # 6 - moderate risk: only Nastavi igrati survives
        c.cookie(tok("tomislav.j"))
        c.go("/", wait_for="section.row")
        c.expect("document.querySelectorAll('section.row').length === 1",
                 "exactly one surviving row")
        c.shot("06-moderate-risk.png")

        # 7 - the age gate refusing sign-in, driven through the real form
        c.cookie(None)
        c.go("/", wait_for=".acct")
        c.js("""(function(){
                 document.querySelector('#u').value='davor.z';
                 document.querySelector('#p').value='psk2026';
                 document.querySelector('#loginForm')
                   .dispatchEvent(new Event('submit',{cancelable:true}));
               })()""")
        time.sleep(2.2)
        c.shot("07-age-gate-refused.png")

        # 8 - the backend view
        c.cookie(tok("ana.k"))
        c.go("/backend", settle=2.8)
        c.shot("08-backend-evaluation.png")
    finally:
        c.close()
    print("\nWrote %d screenshots to demo/screenshots/"
          % len([f for f in os.listdir(OUT) if f.endswith(".png")]))


if __name__ == "__main__":
    main()
