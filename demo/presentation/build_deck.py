"""
Build the pitch deck as a .pptx.

    python demo/presentation/build_deck.py

Why a script and not a checked-in binary: every figure on these slides comes
from `artifacts/`, and figures have drifted before. This reads the numbers it
can read straight from the artifacts, so a stale deck fails loudly instead of
quietly. Re-run it after any wording change and commit the result.

Design is deliberately light-background: a jury room at 2pm may be bright, and
a dark deck that looks good on a laptop can project as mud. The product
screenshots are dark, so they sit well against it.
"""
from __future__ import annotations

import json
import os
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ART = os.path.join(REPO, "artifacts")
OUT = os.path.join(HERE, "QMakers_PSK_Deck.pptx")

# ----------------------------------------------------------------- tokens
INK     = RGBColor(0x14, 0x1B, 0x26)
INK2    = RGBColor(0x47, 0x53, 0x63)
MUTED   = RGBColor(0x8B, 0x96, 0xA5)
ACCENT  = RGBColor(0x2B, 0x6F, 0xC8)
GOLD    = RGBColor(0xB8, 0x7D, 0x0A)
RED     = RGBColor(0xC0, 0x39, 0x32)
GREEN   = RGBColor(0x12, 0x76, 0x52)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
PANEL   = RGBColor(0xF3, 0xF6, 0xFA)
LINE    = RGBColor(0xDD, 0xE3, 0xEC)
DARK    = RGBColor(0x11, 0x17, 0x21)

SANS = "Segoe UI"
MONO = "Consolas"

W, H = Inches(13.333), Inches(7.5)
M = Inches(0.78)                      # side margin
CW = W - 2 * M                        # content width


# ------------------------------------------------------------- primitives
def deck():
    p = Presentation()
    p.slide_width, p.slide_height = W, H
    return p


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(slide, x, y, w, h, fill=None, line=None, lw=1.0):
    from pptx.enum.shapes import MSO_SHAPE
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(lw)
    s.shadow.inherit = False
    return s


def txt(slide, x, y, w, h, runs, size=16, bold=False, color=INK,
        align=PP_ALIGN.LEFT, font=SANS, spacing=1.18, anchor=MSO_ANCHOR.TOP):
    """`runs` is a string, or a list of paragraphs (str | list of (text, dict))."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        pieces = para if isinstance(para, list) else [(para, {})]
        for text, opt in pieces:
            r = p.add_run()
            r.text = text
            f = r.font
            f.name = opt.get("font", font)
            f.size = Pt(opt.get("size", size))
            f.bold = opt.get("bold", bold)
            f.color.rgb = opt.get("color", color)
    return tb


def est_lines(text, width_in, size):
    """
    Rough wrapped-line count. Segoe UI averages ~140 characters per inch-point
    of width; measured against rendered output and accurate enough to stop
    boxes colliding, which is the only thing it is used for.
    """
    per_line = max(1.0, float(width_in) * 140.0 / float(size))
    n = 1
    for chunk in str(text).split("\n"):
        n = max(n, 1)
    return max(1, int(len(str(text)) / per_line) + 1)


#: PowerPoint applies the paragraph spacing multiplier on top of the font's
#: own line height (~1.2x the point size), not on the point size itself.
#: Estimating without this ran every measured box ~20% short.
LINE_FACTOR = 1.2


def text_h(text, width_in, size, spacing=1.18):
    """Height in EMU that `text` needs at this width and size."""
    lines = est_lines(text, width_in, size)
    return Inches(lines * size * LINE_FACTOR * spacing / 72.0)


def title(slide, text, sub=None, rule=True):
    """
    Title, optional subtitle, then the accent rule BELOW both.

    The rule used to sit at a fixed y, which struck through any subtitle that
    wrapped to a second line. Everything here is measured instead.
    """
    tw = CW / 914400.0                       # content width in inches
    th = text_h(text, tw, 33, 1.06)
    txt(slide, M, Inches(0.58), CW, th, text, size=33, bold=True,
        color=INK, spacing=1.06)
    y = Inches(0.58) + th + Inches(0.16)
    if sub:
        sh = text_h(sub, tw, 15)
        txt(slide, M, y, CW, sh, sub, size=15, color=INK2)
        y = y + sh + Inches(0.16)
    if rule:
        rect(slide, M, y, Inches(1.5), Emu(28575), fill=ACCENT)
        y = y + Inches(0.30)
    return y


def eyebrow(slide, text, color=MUTED):
    txt(slide, M, Inches(0.34), CW, Inches(0.3),
        [[(text, {"font": MONO, "size": 10.5, "bold": True, "color": color})]])


def stat(slide, x, y, w, big, label, color=ACCENT, bigsize=40, h=Inches(1.42)):
    rect(slide, x, y, w, h, fill=PANEL, line=LINE)
    txt(slide, x + Inches(0.24), y + Inches(0.17), w - Inches(0.48), Inches(0.62),
        big, size=bigsize, bold=True, color=color)
    txt(slide, x + Inches(0.24), y + Inches(0.86), w - Inches(0.48), h - Inches(0.9),
        label, size=11.5, color=INK2, spacing=1.12)


def table(slide, x, y, w, rows, widths, head=True, rowh=Inches(0.38),
          headh=Inches(0.4), size=12.5):
    n, c = len(rows), len(rows[0])
    shp = slide.shapes.add_table(n, c, x, y, w, headh + rowh * (n - 1))
    t = shp.table
    t.first_row = head
    t.horz_banding = False
    total = float(sum(widths))
    for j, frac in enumerate(widths):
        t.columns[j].width = Emu(int(w * frac / total))
    t.rows[0].height = headh
    for i in range(1, n):
        t.rows[i].height = rowh

    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            cl = t.cell(i, j)
            cl.margin_left = cl.margin_right = Inches(0.12)
            cl.margin_top = cl.margin_bottom = Inches(0.05)
            cl.vertical_anchor = MSO_ANCHOR.MIDDLE
            cl.fill.solid()
            cl.fill.fore_color.rgb = PANEL if i == 0 else WHITE
            tf = cl.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            opts = cell[1] if isinstance(cell, tuple) else {}
            text = cell[0] if isinstance(cell, tuple) else cell
            p.alignment = opts.get("align", PP_ALIGN.LEFT)
            r = p.add_run()
            r.text = text
            f = r.font
            f.name = opts.get("font", SANS)
            f.size = Pt(opts.get("size", 11 if i == 0 else size))
            f.bold = opts.get("bold", i == 0)
            f.color.rgb = opts.get("color", INK2 if i == 0 else INK)
    return shp


def bullets(slide, x, y, w, items, size=13.5, gap=None, color=INK2,
            lead=Inches(0.16)):
    """Each bullet is measured, so a long one cannot overlap the next."""
    wi = (w - Inches(0.22)) / 914400.0
    yy = y
    for it in items:
        flat = it if isinstance(it, str) else "".join(
            t for para in it for t, _ in para)
        h = text_h(flat, wi, size)
        rect(slide, x, yy + Inches(0.085), Inches(0.07), Inches(0.07), fill=ACCENT)
        txt(slide, x + Inches(0.22), yy, w - Inches(0.22), h, it,
            size=size, color=color)
        yy = yy + h + (gap if gap is not None else lead)
    return yy


def footer(slide, left, right="Q'Makers · FEG Innovation Challenge 2026"):
    txt(slide, M, H - Inches(0.52), CW * 0.6, Inches(0.3),
        [[(left, {"font": MONO, "size": 9.5, "color": MUTED})]])
    txt(slide, M + CW * 0.4, H - Inches(0.52), CW * 0.6, Inches(0.3),
        [[(right, {"font": MONO, "size": 9.5, "color": MUTED})]],
        align=PP_ALIGN.RIGHT)


# ------------------------------------------------------------------ facts
def facts():
    """Read what we can from the artifacts, so a stale deck fails loudly."""
    with open(os.path.join(ART, "dataset_report.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    with open(os.path.join(ART, "eval_full.json"), encoding="utf-8") as fh:
        e = json.load(fh)["results"]
    with open(os.path.join(ART, "catalog.json"), encoding="utf-8") as fh:
        cat = json.load(fh)

    tail_r = e["ranker"]["tail_discovery"]
    tail_p = e["most_played"]["tail_discovery"]
    disc_p = e["most_played"]["discovery"]

    stake = sum(g.get("stake", 0) or 0 for g in cat.values())
    unnamed = sum((g.get("stake", 0) or 0) for g in cat.values()
                  if not g.get("displayable"))
    bridged = sum((g.get("stake", 0) or 0) for g in cat.values()
                  if g.get("title_source") == "event_log_bridge")

    f = {
        "players": d["players"],
        "games": d["games_trainable"],
        "displayable": d["games_displayable"],
        "rows": 741679,
        "new_games": d["new_games"],
        "jackpot": d["jackpot_games"],
        "bridge_codes": d["games_named_by_bridge"],
        "ratio": tail_r["ndcg@10"] / tail_p["ndcg@10"],
        "ranker_ndcg": tail_r["ndcg@10"],
        "pop_ndcg_tail": tail_p["ndcg@10"],
        "cov_ranker": int(tail_r["coverage@10"]),
        "cov_pop_tail": int(tail_p["coverage@10"]),
        "cov_pop_disc": int(disc_p["coverage@10"]),
        "disc_pop": disc_p["ndcg@10"],
        "unnamed_pct": 100 * unnamed / stake,
        "bridged_pct": 100 * bridged / stake,
        "seq": e["sequence"]["tail_discovery"]["ndcg@10"],
        "cf": e["item_item"]["tail_discovery"]["ndcg@10"],
        "blend": e["hybrid"]["tail_discovery"]["ndcg@10"],
        "cf_disc": e["item_item"]["discovery"]["ndcg@10"],
        "prov_disc": e["provider_popular"]["discovery"]["ndcg@10"],
    }
    f["cov_mult"] = f["cov_ranker"] / f["cov_pop_tail"]
    return f


#: Shown on the title slide. Override from the command line if they change:
#:     python demo/presentation/build_deck.py "Lead Name" "A · B"
TEAM_LEAD = "Bandlapalli Roshan Babu"
TEAM_MEMBERS = "C. Kavya Sri · M. Yashwanth"

# ------------------------------------------------------------- new helpers
SHOTS = os.path.join(REPO, "demo", "screenshots")


def shot_path(name):
    p = os.path.join(SHOTS, name)
    if not os.path.exists(p):
        raise SystemExit(
            "Missing screenshot %s.\nRun:  python demo/capture_screenshots.py"
            % name)
    return p


def picture(slide, name, x, y, w, crop=None, border=True):
    """Place a screenshot, optionally cropped as (left, top, right, bottom)."""
    pic = slide.shapes.add_picture(shot_path(name), x, y, width=w)
    if crop:
        pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = crop
        pic.width = w
        vis_w = 1424.0 * (1 - crop[0] - crop[2])
        vis_h = 855.0 * (1 - crop[1] - crop[3])
        pic.height = Emu(int(w * vis_h / vis_w))
    if border:
        pic.line.color.rgb = LINE
        pic.line.width = Pt(1)
    return pic


def hbars(slide, x, y, w, rows, hi=0, rowh=Inches(0.46), fmt="%.4f"):
    """
    Horizontal bars drawn as rectangles. A native pptx chart drags in its own
    theme colours and fonts; this stays on the deck's palette.
    """
    top = max(v for _, v in rows)
    labw, valw = Inches(2.15), Inches(0.95)
    barw = w - labw - valw
    for i, (label, val) in enumerate(rows):
        yy = y + rowh * i
        on = (i == hi)
        txt(slide, x, yy + Inches(0.05), labw - Inches(0.12), Inches(0.3),
            label, size=12.5, bold=on, color=INK if on else INK2)
        bw = max(Inches(0.02), Emu(int(barw * val / top)))
        rect(slide, x + labw, yy + Inches(0.07), bw, Inches(0.22),
             fill=GREEN if on else RGBColor(0xC3, 0xCE, 0xDC))
        txt(slide, x + labw + bw + Inches(0.1), yy + Inches(0.04),
            valw, Inches(0.3), fmt % val, size=12,
            bold=on, color=GREEN if on else MUTED, font=MONO)
    return y + rowh * len(rows)


def flow(slide, y, boxes, h=Inches(1.0), gap=Inches(0.30)):
    """A left-to-right pipeline: boxes with arrows between them."""
    from pptx.enum.shapes import MSO_SHAPE
    n = len(boxes)
    bw = (CW - gap * (n - 1)) / n
    for i, (head, body, accent) in enumerate(boxes):
        x = M + (bw + gap) * i
        rect(slide, x, y, bw, h, fill=PANEL if not accent else None,
             line=accent or LINE, lw=1.6 if accent else 1.0)
        if accent:
            rect(slide, x, y, bw, Inches(0.05), fill=accent)
        txt(slide, x + Inches(0.16), y + Inches(0.17), bw - Inches(0.32),
            Inches(0.3), head, size=12, bold=True, color=accent or INK)
        txt(slide, x + Inches(0.16), y + Inches(0.5), bw - Inches(0.32),
            h - Inches(0.6), body, size=10.5, color=INK2, spacing=1.12)
        if i < n - 1:
            a = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW, x + bw + Inches(0.05),
                y + h / 2 - Inches(0.07), gap - Inches(0.10), Inches(0.14))
            a.fill.solid()
            a.fill.fore_color.rgb = RGBColor(0xB9, 0xC5, 0xD4)
            a.line.fill.background()
            a.shadow.inherit = False
    return y + h


# ----------------------------------------------------------------- slides
def build(team_lead=TEAM_LEAD, members=TEAM_MEMBERS):
    F = facts()
    prs = deck()
    PLAYERS = format(F["players"], ",")
    GAMES = format(F["games"], ",")

    # 1 ------------------------------------------------------------ title
    s = blank(prs)
    rect(s, Inches(0), Inches(0), W, Inches(0.13), fill=ACCENT)
    txt(s, M, Inches(1.55), CW, Inches(1.1),
        "PSK Personalised Lobby", size=52, bold=True, color=INK)
    txt(s, M, Inches(2.75), Inches(9.0), Inches(0.9),
        "The lobby should know who is looking at it.", size=22, color=ACCENT)
    txt(s, M, Inches(3.62), Inches(9.4), Inches(1.0),
        "A game recommender that rebuilds the casino lobby around what each "
        "player actually plays.", size=15, color=INK2)
    rect(s, M, Inches(4.75), CW, Emu(12700), fill=LINE)
    bits = ["%s players" % PLAYERS, "%s games" % GAMES,
            "%s rows" % format(F["rows"], ","), "a trained ranker"]
    for i, b in enumerate(bits):
        txt(s, M + Inches(3.05) * i, Inches(5.0), Inches(2.9), Inches(0.4),
            [[(b, {"font": MONO, "size": 11.5, "color": INK2})]])
    who = "Team Q'Makers"
    if team_lead:
        who += "  ·  " + team_lead
    if members:
        who += "  ·  " + members
    txt(s, M, Inches(6.2), CW, Inches(0.7),
        [who, "FEG Innovation Challenge 2026  ·  Croatian brand (PSK) track"],
        size=13, color=MUTED)

    # 2 --------------------------------------------- the lobby today (shot)
    s = blank(prs)
    eyebrow(s, "01  /  TODAY")
    txt(s, M, Inches(0.72), Inches(4.15), Inches(1.6),
        "One lobby.\n%s players." % PLAYERS, size=32, bold=True, color=INK,
        spacing=1.06)
    txt(s, M, Inches(2.4), Inches(4.15), Inches(2.2),
        "Two rows. Identical for everyone — whether they have played one "
        "game or three hundred.\n\nThe most common route to a game here is "
        "typing its name into search. If you have to search, the lobby "
        "didn't surface it.", size=13.5, color=INK2, spacing=1.25)
    stat(s, M, Inches(5.0), Inches(4.15),
         "%d of %s" % (F["cov_pop_disc"], GAMES),
         "games the top row can ever reach — about 1% of the library",
         color=RED, bigsize=26, h=Inches(1.45))
    picture(s, "01-anonymous-lobby.png", M + Inches(4.55), Inches(1.0),
            Inches(8.0))
    footer(s, "01 / 11")

    # 3 ----------------------------------------- the same page, signed in
    s = blank(prs)
    eyebrow(s, "02  /  THE PRODUCT", GREEN)
    txt(s, M, Inches(0.72), Inches(4.15), Inches(1.6),
        "Sign in.\nSame page.", size=32, bold=True, color=INK, spacing=1.06)
    txt(s, M, Inches(2.4), Inches(4.15), Inches(2.3),
        "Two rows become six, built from that player's own history by the "
        "trained ranker.\n\nNothing was removed. Popular is still there, "
        "unchanged — and that turns out to matter.",
        size=13.5, color=INK2, spacing=1.25)
    rect(s, M, Inches(4.95), Inches(4.15), Inches(1.4), fill=PANEL,
         line=GREEN, lw=1.4)
    txt(s, M + Inches(0.22), Inches(5.14), Inches(3.7), Inches(1.1),
        [[("Every tile says why. ", {"bold": True, "color": INK}),
          ("The reason is the model's own largest term — not a generated "
           "sentence.", {})]],
        size=12.5, color=INK2, spacing=1.2)
    picture(s, "02-signed-in-lobby.png", M + Inches(4.55), Inches(1.0),
            Inches(8.0))
    footer(s, "02 / 11")

    # 4 ---------------------------------------------- the reason, close up
    s = blank(prs)
    eyebrow(s, "03  /  EXPLAINABILITY")
    y = title(s, "Every tile carries the reason it is there.",
              "Not a generated rationale — the single feature with the "
              "largest weight × value in the model's own score. A test "
              "proves the attribution reconstructs the probability exactly, "
              "so /explain can be trusted in an audit.")
    picture(s, "03-why-this-game.png", M, y + Inches(0.12), Inches(6.75),
            crop=(0.0, 0.30, 0.36, 0.10))
    xr = M + Inches(7.10)
    wr = CW - Inches(7.10)
    bullets(s, xr, y + Inches(0.18), wr, [
        [[("EU AI Act 2024/1689. ", {"bold": True, "color": INK}),
          ("Explainability met by construction, not by a report written "
           "afterwards.", {})]],
        [[("Dimmed, dashed tiles ", {"bold": True, "color": INK}),
          ("are games whose title is not in the data. They appear only in "
           "your own history — never as a recommendation.", {})]],
        [[("No stake suggestion exists ", {"bold": True, "color": INK}),
          ("anywhere in the codebase. The system recommends games, never "
           "amounts.", {})]],
        [[("No dark patterns. ", {"bold": True, "color": INK}),
          ("No countdowns, no scarcity, no “others are playing”, no "
           "near-miss framing.", {})]],
    ], size=12.5)
    footer(s, "03 / 11")

    # 5 ------------------------------------------------------------- demo
    s = blank(prs)
    rect(s, Inches(0), Inches(0), W, H, fill=DARK)
    rect(s, Inches(0), Inches(0), W, Inches(0.13), fill=ACCENT)
    txt(s, M, Inches(1.45), CW, Inches(0.5),
        [[("LIVE  DEMO", {"font": MONO, "size": 13, "bold": True,
                          "color": RGBColor(0x6F, 0xA8, 0xE8)})]])
    txt(s, M, Inches(1.95), Inches(9.5), Inches(1.4),
        "Watch two rows become six.", size=44, bold=True, color=WHITE)
    beats = [
        "The anonymous lobby — what all %s players see today" % PLAYERS,
        "Sign in as ana.k — the same page rebuilds into six rows",
        "Read a tile out loud — that is the model's own top feature",
        "davor.z — sign-in REFUSED. Age unverified; the check precedes play",
        "lucija.h — signs in, zero rows. Self-exclusion blocks inducements, "
        "not account access",
    ]
    for i, b in enumerate(beats):
        yy = Inches(3.45) + Inches(0.47) * i
        txt(s, M, yy, Inches(0.4), Inches(0.4),
            [[("0%d" % (i + 1), {"font": MONO, "size": 12, "bold": True,
                                 "color": RGBColor(0x6F, 0xA8, 0xE8)})]])
        txt(s, M + Inches(0.55), yy, CW - Inches(0.6), Inches(0.45), b,
            size=14, color=RGBColor(0xC9, 0xD3, 0xE0))
    txt(s, M, H - Inches(0.8), CW, Inches(0.4),
        "12 demo accounts, generated from real player histories in the model. "
        "~25 ms per lobby, and no network on the request path.",
        size=12, color=RGBColor(0x82, 0x8F, 0xA0))

    # 6 --------------------------------------------------- the honest loss
    s = blank(prs)
    eyebrow(s, "04  /  THE FINDING WE DIDN'T WANT", RED)
    y = title(s, "Our recommender lost.",
              "On predicting the next game a player tries, collaborative "
              "filtering was beaten outright by the popularity row PSK "
              "already ships.")
    hbars(s, M, y + Inches(0.22), Inches(6.3), [
        ("most_played", F["disc_pop"]),
        ("provider_popular", F["prov_disc"]),
        ("item-item CF (ours)", F["cf_disc"]),
    ], hi=0)
    txt(s, M, y + Inches(1.68), Inches(6.3), Inches(0.4),
        "NDCG@10  ·  discovery task  ·  9,102 players",
        size=10.5, color=MUTED, font=MONO)
    xr = M + Inches(6.8)
    wr = CW - Inches(6.8)
    txt(s, xr, y + Inches(0.16), wr, Inches(2.0),
        "What players try next is overwhelmingly what is already popular. "
        "Correlation between a game's popularity and its next-week discovery "
        "count is 0.79, and one title takes 13% of all discovery plays on its "
        "own.\n\nWe swept popularity correction, shrinkage, neighbourhood size "
        "and eight blend weights before accepting it.",
        size=13, color=INK2, spacing=1.25)
    rect(s, M, y + Inches(2.35), CW, Inches(0.85), fill=PANEL, line=ACCENT,
         lw=1.4)
    txt(s, M + Inches(0.26), y + Inches(2.56), CW - Inches(0.52), Inches(0.5),
        [[("So we kept the popularity row. ", {"bold": True, "color": INK}),
          ("Replacing it would have made the lobby worse — which is why "
           "Popular is still on the screen you just saw.", {})]],
        size=14, color=INK2)
    footer(s, "04 / 11")

    # 7 ----------------------------------------------------- the tail win
    s = blank(prs)
    eyebrow(s, "05  /  THE RESULT THAT JUSTIFIES THE BUILD", GREEN)
    y = title(s, "But popularity only knows %d games." % F["cov_pop_tail"],
              "Remove the global top-50 and it reverses. This is the tail "
              "— where 76.5% of all discovery already happens.")
    hbars(s, M, y + Inches(0.22), Inches(6.3), [
        ("Trained ranker", F["ranker_ndcg"]),
        ("Blend (seq + CF)", F["blend"]),
        ("Sequence", F["seq"]),
        ("Item-item CF", F["cf"]),
        ("most_played", F["pop_ndcg_tail"]),
    ], hi=0)
    txt(s, M, y + Inches(2.55), Inches(6.3), Inches(0.4),
        "NDCG@10  ·  tail discovery  ·  5,921 players",
        size=10.5, color=MUTED, font=MONO)
    xr = M + Inches(6.8)
    wr = CW - Inches(6.8)
    sw = (wr - Inches(0.22)) / 2
    stat(s, xr, y + Inches(0.16), sw, "%.2f×" % F["ratio"],
         "better than the row that ships today", color=GREEN, bigsize=33,
         h=Inches(1.25))
    stat(s, xr + sw + Inches(0.22), y + Inches(0.16), sw,
         "%.0f×" % F["cov_mult"],
         "the catalogue — %d games, not %d"
         % (F["cov_ranker"], F["cov_pop_tail"]),
         color=GREEN, bigsize=33, h=Inches(1.25))
    txt(s, xr, y + Inches(1.6), wr, Inches(1.7),
        "Popularity owns the head. We own the tail.\n\nThe recommender is "
        "additive — nothing that already worked was removed, so the "
        "downside is bounded at screen space, and every row ships behind its "
        "own feature flag.", size=13, color=INK2, spacing=1.25)
    footer(s, "05 / 11")

    # 8 ----------------------------------------------------- how it works
    s = blank(prs)
    eyebrow(s, "06  /  HOW IT WORKS")
    y = title(s, "Two stages: propose, then re-rank.",
              "Cheap models generate candidates; a trained model orders them. "
              "The second stage is what beats the blend — and it is also "
              "what makes every tile explainable.")
    flow(s, y + Inches(0.12), [
        ("Item-item CF",
         "Cosine over %s × %s, shrinkage, and a popularity correction "
         "applied to the similarity" % (PLAYERS, GAMES), None),
        ("Day-to-day sequence",
         "Row-normalised transitions over 1.4M ordered pairs, with "
         "recency-decayed profiles", None),
        ("~200 candidates",
         "The union per player, with everything already played removed",
         None),
        ("Trained re-ranker",
         "LogisticRegression · 14 features · ~200k labelled rows",
         GREEN),
        ("Score → reason",
         "Each score decomposes into weight × value; the largest term is "
         "the sentence on the tile", ACCENT),
    ], h=Inches(1.5))
    bullets(s, M, y + Inches(1.95), CW, [
        [[("The features. ", {"bold": True, "color": INK}),
          ("CF score, sequence score, popularity, provider affinity and "
           "recency, type affinity, stake momentum, release age, is-new, "
           "jackpot, payout ratio, and three player-level terms. Payout ratio "
           "is a similarity feature only — never ranked on, never shown, "
           "because advertising “this game pays more” is the "
           "inducement the AI Act prohibits.", {})]],
        [[("The name bridge. ", {"bold": True, "color": INK}),
          ("%s game codes carried no title at all. Co-occurrence on "
           "(player, day), constrained to matching providers, recovered %d of "
           "them — %.0f%% of all stake. It independently derived that "
           "gpas_3chken_pop is “4 Crazy Cluckers”, from a slug it "
           "cannot read."
           % (format(F["games"] - F["displayable"], ","), F["bridge_codes"],
              F["bridged_pct"]), {})]],
        [[("Measured honestly. ", {"bold": True, "color": INK}),
          ("Three-way temporal split — hyperparameters chosen on a "
           "validation week, never the test week. Gradient boosting won a "
           "player-split validation and then lost the temporal test: exactly "
           "the overfitting you cannot see if you only split by user.", {})]],
    ], size=12)
    footer(s, "06 / 11")

    # 9 ----------------------------------------------------- architecture
    s = blank(prs)
    eyebrow(s, "07  /  ARCHITECTURE")
    y = title(s, "Additive middleware on FEG's own stack.",
              "One stateless service reading precomputed artifacts. No GPU, "
              "no model API, and no new instrumentation — it reads the "
              "warehouse table CA_Player is already exported from.")
    flow(s, y + Inches(0.16), [
        ("CA_Player",
         "The export FEG already produces. Daily batch, no new tracking "
         "required", None),
        ("Pipeline",
         "Clean, name-bridge, features, three-way split. Seconds on one core",
         None),
        ("artifacts/",
         "18 MB — similarity, sequence, catalogue, ranker. Object storage "
         "or the image", None),
        ("Service",
         "Python or Java, stateless, horizontally scaled. ~25 ms, no I/O on "
         "the request path", ACCENT),
        ("Vue 3 row",
         "One component, one JSON contract. Render the rows you recognise, "
         "ignore the rest", None),
    ], h=Inches(1.5))
    rect(s, M, y + Inches(2.0), CW, Inches(0.75), fill=None, line=RED, lw=1.6)
    txt(s, M + Inches(0.24), y + Inches(2.19), CW - Inches(0.48), Inches(0.5),
        [[("The responsible-play gate sits inside the service, before scoring "
           "— ", {"bold": True, "color": RED}),
          ("not in the client, and not behind a flag anyone can switch off.",
           {"color": INK2})]], size=13)
    txt(s, M, y + Inches(2.95), CW, Inches(0.9),
        [[("What FEG actually builds: ", {"bold": True, "color": INK}),
          ("a Vue row component (3–4 days), a daily batch job (1 day), "
           "and a service deployment (2–3 days). Redis and Kafka are only "
           "needed below a daily cadence, so neither is on the critical path. "
           "Everything else in the repository is done.", {})]],
        size=13, color=INK2, spacing=1.25)
    footer(s, "07 / 11")

    # 10 ------------------------------------------ responsible (with shot)
    s = blank(prs)
    eyebrow(s, "08  /  COMPLIANCE BY DESIGN", RED)
    txt(s, M, Inches(0.66), Inches(6.05), Inches(0.8),
        "The gate runs before the model.", size=25, bold=True, color=INK,
        spacing=1.06)
    txt(s, M, Inches(1.32), Inches(6.05), Inches(1.1),
        "Two gates, firing at different points, because the law treats them "
        "differently. Both directions are asserted in tests — getting "
        "either backwards would be a real compliance failure.",
        size=13, color=INK2, spacing=1.22)
    table(s, M, Inches(2.62), Inches(6.05), [
        ["Gate", "Where it fires"],
        [("Age / ID unverified", {"bold": True, "color": RED}),
         "At sign-in — refused, no session issued at all"],
        [("Self-excluded", {"bold": True, "color": RED}),
         "After sign-in — the account opens, the lobby returns zero rows"],
    ], [0.37, 0.63], rowh=Inches(0.6))
    txt(s, M, Inches(4.62), Inches(6.05), Inches(1.5),
        [[("Self-exclusion blocks inducements, not account access. ",
           {"bold": True, "color": INK}),
          ("The person must still reach their account and support — so "
           "they sign in, and get zero recommendations plus the required "
           "surfaces. Not filtered afterwards. Never scored.", {})]],
        size=12.5, color=INK2, spacing=1.22)
    picture(s, "05-self-excluded-zero-rows.png", M + Inches(6.5),
            Inches(1.15), Inches(6.05))
    txt(s, M + Inches(6.5), Inches(4.95), Inches(6.05), Inches(0.4),
        "the self-excluded account, signed in — zero rows",
        size=10.5, color=MUTED, font=MONO)
    footer(s, "08 / 11")

    # 11 ---------------------------------------------- business + refusal
    s = blank(prs)
    eyebrow(s, "09  /  BUSINESS IMPACT", GOLD)
    y = title(s, "€19.6M a fortnight rides on discovery.",
              "13.7% of all stake sits on games a player was trying for the "
              "first time — 138,041 first-time adoptions, median "
              "€16.16. That entire flow is served today by a search box.")
    gap = Inches(0.26)
    w3 = (CW - gap * 2) / 3
    stat(s, M, y + Inches(0.18), w3, "€19.6M",
         "on first-time game plays every fortnight — a seventh of all "
         "stake", color=GOLD, bigsize=31, h=Inches(1.3))
    stat(s, M + w3 + gap, y + Inches(0.18), w3, "€17.00",
         "median stake on a newly-adopted tail game, against €10.50 on a "
         "top-50 game. The tail is not the cheap end", color=GOLD, bigsize=31,
         h=Inches(1.3))
    stat(s, M + (w3 + gap) * 2, y + Inches(0.18), w3, "0",
         "revenue-uplift numbers we are willing to claim. We tested it three "
         "ways and it did not survive", color=RED, bigsize=31, h=Inches(1.3))
    rect(s, M, y + Inches(1.72), CW, Inches(1.75), fill=PANEL, line=ACCENT,
         lw=1.4)
    txt(s, M + Inches(0.28), y + Inches(1.94), CW - Inches(0.56), Inches(1.4),
        [[("Matched on activity, adopters retain no better and stake less the "
           "next week. ", {"bold": True, "color": INK}),
          ("So we make no revenue claim. What we argue instead: exploration "
           "correlates with lower value ", {}),
          ("because exploration currently fails", {"bold": True, "color": INK}),
          (" — players hunt and don't find. The job is not more "
           "exploration; it is making the exploration they already do "
           "succeed.", {})],
         [("The experiment that settles it: A/B on the lobby, primary metric "
           "= first-time adoptions replayed within 7 days. That separates "
           "“found something good” from “tried and "
           "bounced”.", {"color": INK2})]],
        size=12.5, color=INK2, spacing=1.25)
    footer(s, "09 / 11")

    # 12 -------------------------------------------------------- the ask
    s = blank(prs)
    eyebrow(s, "10  /  THE ONE ASK")
    y = title(s,
              "%.0f%% of stake is on games we cannot name." % F["unnamed_pct"],
              "Opaque codes like pop_9f571b7a_egtfeg. They train the model "
              "— their co-occurrence is real signal — but they can "
              "never be recommended, because a player cannot know what they "
              "are being offered.")
    gap = Inches(0.26)
    w3 = (CW - gap * 2) / 3
    stat(s, M, y + Inches(0.18), w3, "%.0f%%" % F["unnamed_pct"],
         "of all stake, still on games with no title we can show a player",
         color=RED, bigsize=33, h=Inches(1.3))
    stat(s, M + w3 + gap, y + Inches(0.18), w3, str(F["bridge_codes"]),
         "codes our name bridge already recovered from behaviour alone "
         "— %.0f%% of stake, catalogue up to %d games"
         % (F["bridged_pct"], F["displayable"]), color=GREEN, bigsize=33,
         h=Inches(1.3))
    stat(s, M + (w3 + gap) * 2, y + Inches(0.18), w3, "~9×",
         "the addressable inventory, if FEG shares a game catalogue",
         color=ACCENT, bigsize=33, h=Inches(1.3))
    rect(s, M, y + Inches(1.75), CW, Inches(1.05), fill=DARK)
    txt(s, M + Inches(0.3), y + Inches(1.97), CW - Inches(0.6), Inches(0.7),
        [[("A game catalogue — code → title, category, thumbnail. ",
           {"bold": True, "color": WHITE}),
          ("It costs FEG a database export. It is the single highest-value "
           "thing we could be given, and the only limit here we cannot "
           "engineer around.", {"color": RGBColor(0xC9, 0xD3, 0xE0)})]],
        size=14)
    footer(s, "10 / 11")

    # 13 ---------------------------------------------------------- close
    s = blank(prs)
    eyebrow(s, "11  /  WHERE IT STANDS")
    y = title(s, "The lobby should know who is looking at it.",
              "Today it doesn't. We measured what personalisation can and "
              "cannot do here, kept the row that already worked, and added "
              "the %d games it could never reach." % F["cov_ranker"])
    half = (CW - Inches(0.38)) / 2
    rect(s, M, y + Inches(0.16), half, Inches(2.45), fill=PANEL, line=LINE)
    txt(s, M + Inches(0.26), y + Inches(0.34), half - Inches(0.52),
        Inches(2.1),
        [[("Shipped", {"size": 14, "bold": True, "color": GREEN})],
         [("Pipeline → model → API → lobby, end to end",
           {"size": 12.5, "color": INK2})],
         [("A real login journey, 12 accounts from real histories",
           {"size": 12.5, "color": INK2})],
         [("~25 ms per lobby. No GPU, no model fit at request time",
           {"size": 12.5, "color": INK2})],
         [("54 tests, green on a clean clone", {"size": 12.5, "color": INK2})],
         [("Eight documents — including the evaluation with the loss in it",
           {"size": 12.5, "color": INK2})]],
        spacing=1.32)
    rect(s, M + half + Inches(0.38), y + Inches(0.16), half, Inches(2.45),
         fill=WHITE, line=LINE)
    txt(s, M + half + Inches(0.64), y + Inches(0.34), half - Inches(0.52),
        Inches(2.1),
        [[("Not built — and we say so",
           {"size": 14, "bold": True, "color": GOLD})],
         [("No Vue SDK yet — the dashboard is plain HTML",
           {"size": 12.5, "color": INK2})],
         [("No Kafka/Redis — the pipeline is a daily batch",
           {"size": 12.5, "color": INK2})],
         [("Prototype auth: hashed and signed, but no rate limiting or MFA",
           {"size": 12.5, "color": INK2})],
         [("No session-level sequence model", {"size": 12.5, "color": INK2})],
         [("No online experiment — every number here is offline",
           {"size": 12.5, "color": INK2})]],
        spacing=1.32)
    rect(s, M, y + Inches(2.82), CW, Emu(12700), fill=LINE)
    txt(s, M, y + Inches(3.0), CW, Inches(0.5),
        [[("Team Q'Makers  ·  feg-hackathon-2026-QMakers  ·  "
           "FEG Innovation Challenge 2026",
           {"font": MONO, "size": 11.5, "color": MUTED})]])
    footer(s, "11 / 11")

    prs.save(OUT)
    return OUT, F


if __name__ == "__main__":
    lead = sys.argv[1] if len(sys.argv) > 1 else TEAM_LEAD
    members = sys.argv[2] if len(sys.argv) > 2 else TEAM_MEMBERS
    path, F = build(lead, members)
    print("wrote %s" % path)
    print("  %.2fx tail ratio · %d vs %d games · %.1f%% unnameable"
          % (F["ratio"], F["cov_ranker"], F["cov_pop_tail"], F["unnamed_pct"]))
