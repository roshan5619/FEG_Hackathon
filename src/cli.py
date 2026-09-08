"""
One entry point for the whole system.

    python -m src.cli demo                    # start the server and open the browser
    python -m src.cli serve --port 8000       # start the server only
    python -m src.cli explain <player_id>     # one player's lobby, with the reasons
    python -m src.cli evaluate                # model comparison table
    python -m src.cli build --data-dir DIR    # rebuild artifacts from the FEG CSVs
    python -m src.cli train                   # refit models and the ranker
    python -m src.cli all   --data-dir DIR    # build, train, evaluate, serve
    python -m src.cli status                  # what is built, what it contains

`demo`, `serve`, `explain`, `evaluate` and `status` all run from the committed
artifacts. **The FEG source CSVs are not needed** - only `build` reads them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import webbrowser

from src.pipeline.build_dataset import ART

BANNER = "PSK Game Recommender  ·  Q'Makers  ·  FEG Innovation Challenge 2026"


def _rule(char="-", n=74):
    return char * n


def _need_artifacts():
    missing = [f for f in ("interactions.npz", "model.npz", "catalog.json")
               if not os.path.exists(os.path.join(ART, f))]
    if missing:
        sys.exit("Missing artifacts: %s\nRun:  python -m src.cli build --data-dir <FEG csv folder>"
                 % ", ".join(missing))


# ----------------------------------------------------------------- commands
def cmd_status(args):
    print(BANNER)
    print(_rule())
    for name in ("dataset_report.json", "model_report.json", "ranker_report.json"):
        path = os.path.join(ART, name)
        if not os.path.exists(path):
            print("%-22s not built" % name)
            continue
        with open(path, encoding="utf-8") as fh:
            r = json.load(fh)
        print("\n%s" % name)
        if name.startswith("dataset"):
            s = r.get("split", {})
            print("  rows %s | players %s | games %s (%s displayable)"
                  % (format(r["rows"], ","), format(r["players"], ","),
                     r["games_trainable"], r["games_displayable"]))
            print("  split  train %sd / val %sd / test %sd   (%s .. %s)"
                  % (s.get("train_days"), s.get("val_days"), s.get("test_days"),
                     r["date_range"][0], r["date_range"][1]))
            print("  named by event-log bridge: %s | new games: %s | jackpot: %s"
                  % (r["games_named_by_bridge"], r["new_games"], r["jackpot_games"]))
            print("  dropped: %s" % r["dropped"])
        elif name.startswith("model"):
            print("  fitted on %s | blend %s" % (r["fitted_on"], r["blend"]))
            print("  ranker %s, train accuracy %s on %s rows"
                  % (r["ranker"]["kind"], r["ranker"]["train_accuracy"],
                     format(r["ranker"]["n_rows"], ",")))
        else:
            print("  the trained ranker learned these weights:")
            for f in r["features"][:8]:
                bar = "#" * int(min(abs(f["weight"]) * 40, 40))
                print("    %-20s %+7.3f %s" % (f["name"], f["weight"], bar))


def cmd_build(args):
    from src.pipeline.build_dataset import build
    build(args.data_dir, use_sb=not args.no_sb)


def cmd_train(args):
    from src.recsys.train import train
    train(serve_on_all=getattr(args, 'serve_on_all', False), ranker_kind=args.ranker)


def cmd_evaluate(args):
    _need_artifacts()
    from src.recsys.evaluate import main as eval_main
    sys.argv = ["evaluate"] + (["--displayable-only"] if args.displayable_only else [])
    eval_main()


def cmd_explain(args):
    """Print one player's lobby and why each game was chosen."""
    _need_artifacts()
    from src.recsys.serve import LobbyService
    svc = LobbyService()
    pid = args.player_id
    if pid not in svc.row_of:
        cands = [p for p in svc.players if p.startswith(pid)]
        if len(cands) == 1:
            pid = cands[0]
        else:
            print("Unknown player. Try one of:")
            for p in svc.players[:5]:
                print("  " + p)
            return
    out = svc.lobby(pid)
    print(BANNER)
    print(_rule())
    print("player %s…  |  %d games in history  |  responsible play: %s"
          % (pid[:16], svc.X[svc.row_of[pid]].nnz, out["responsible_play"]["state"]))
    if out.get("also_bets_sport"):
        print("also bets sport: %s" % out["also_bets_sport"])
    for row in out["rows"]:
        kind = "personalised" if row["personalised"] else "global"
        print("\n%s  [%s · %s]" % (row["title"], kind, row["source"]))
        print("  %s" % row["subtitle"])
        for t in row["tiles"][:args.top]:
            badge = (" [" + "/".join(t["badges"]) + "]") if t["badges"] else ""
            print("   %-40s %-14s%s" % (t["title"][:40], (t["provider"] or "")[:14], badge))
            print("      why: %s" % t["why"])

    # Feature-level explanation from the trained model, if it is built.
    if os.path.exists(os.path.join(ART, "ranker.pkl")) and out["rows"]:
        # Explain an actual recommendation, not a game from their own history -
        # "continue" is a lookup, not a prediction, so it has nothing to explain.
        target = next((r for r in out["rows"]
                       if r["personalised"] and r["key"] != "continue" and r["tiles"]), None)
        if target:
            code = target["tiles"][0]["code"]
            print("\n%s\nWHAT THE TRAINED RANKER SAW for '%s'"
                  % (_rule(), target["tiles"][0]["title"]))
            exp = svc.explain(pid, code)
            if exp:
                print("  predicted probability: %.4f  (%s attribution)"
                      % (exp["probability"], "exact" if exp["exact"] else "indicative"))
                for f in exp["features"][:8]:
                    bar = "#" * int(min(abs(f["contribution"]) * 25, 30))
                    print("    %-20s value %8.3f  contribution %+7.3f %s"
                          % (f["name"], f["value"], f["contribution"], bar))


def _serve(port: int, open_browser: bool):
    import uvicorn
    from src.api.app import app
    if open_browser:
        def _open():
            time.sleep(1.6)
            webbrowser.open("http://127.0.0.1:%d/" % port)
        threading.Thread(target=_open, daemon=True).start()
    print(_rule())
    print("  lobby    http://127.0.0.1:%d/" % port)
    print("  backend  http://127.0.0.1:%d/backend      <- the visualisations" % port)
    print("  api docs http://127.0.0.1:%d/docs" % port)
    print(_rule())
    print("  Ctrl-C to stop.")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def cmd_serve(args):
    _need_artifacts()
    _serve(args.port, open_browser=False)


def cmd_demo(args):
    _need_artifacts()
    print(BANNER)
    print(_rule())
    with open(os.path.join(ART, "dataset_report.json"), encoding="utf-8") as fh:
        r = json.load(fh)
    print("  %s players · %s games · %s displayable · %s interactions"
          % (format(r["players"], ","), r["games_trainable"], r["games_displayable"],
             format(r["interactions_fit"], ",")))
    print("  Opening the lobby. Switch player to see the rows change.")
    _serve(args.port, open_browser=True)


def cmd_all(args):
    cmd_build(args)
    cmd_train(args)
    cmd_evaluate(args)
    cmd_demo(args)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(prog="python -m src.cli", description=BANNER)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="rebuild artifacts from the FEG CSVs")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--no-sb", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("train", help="refit models and train the ranker")
    p.add_argument("--serve-on-all", action="store_true")
    p.add_argument("--ranker", default="logreg", choices=["logreg", "gbm"])
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("evaluate", help="model comparison table")
    p.add_argument("--displayable-only", action="store_true")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("explain", help="one player's lobby with reasons")
    p.add_argument("player_id")
    p.add_argument("--top", type=int, default=5)
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("serve", help="run the API and site")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("demo", help="run and open the browser")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("status", help="what is built")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("all", help="build, train, evaluate, then demo")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--no-sb", action="store_true")
    p.add_argument("--serve-on-all", action="store_true")
    p.add_argument("--ranker", default="logreg", choices=["logreg", "gbm"])
    p.add_argument("--displayable-only", action="store_true")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_all)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
