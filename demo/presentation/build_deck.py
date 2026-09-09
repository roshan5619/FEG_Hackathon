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


# ----------------------------------------------------------------- slides
#: Shown on the title slide. Override from the command line if they change:
#:     python demo/presentation/build_deck.py "Lead Name" "A, B"
TEAM_LEAD = "Bandlapalli Roshan Babu"
TEAM_MEMBERS = "C. Kavya Sri · M. Yashwanth"


def build(team_lead=TEAM_LEAD, members=TEAM_MEMBERS):
    F = facts()
    prs = deck()

    # 1 --------------------------------------------------------- title
    s = blank(prs)
    rect(s, Inches(0), Inches(0), W, Inches(0.13), fill=ACCENT)
    txt(s, M, Inches(1.75), CW, Inches(1.1),
        "PSK Personalised Lobby", size=52, bold=True, color=INK)
    txt(s, M, Inches(2.95), Inches(8.4), Inches(0.9),
        "The lobby should know who is looking at it.",
        size=21, color=ACCENT)
    txt(s, M, Inches(3.85), Inches(9.2), Inches(1.0),
        "A game recommender that rebuilds the casino lobby around what each "
        "player actually plays — their history, their favourites, their next game.",
        size=14.5, color=INK2)

    rect(s, M, Inches(5.05), CW, Emu(12700), fill=LINE)
    bits = [("%s players" % format(F["players"], ",")),
            ("%s games" % format(F["games"], ",")),
            ("%s rows" % format(F["rows"], ",")),
            "a trained ranker"]
    for i, b in enumerate(bits):
        txt(s, M + Inches(3.05) * i, Inches(5.3), Inches(2.9), Inches(0.4),
            [[(b, {"font": MONO, "size": 11.5, "color": INK2})]])

    who = "Team Q'Makers"
    if team_lead:
        who += "  ·  " + team_lead
    if members:
        who += "  ·  " + members
    txt(s, M, Inches(6.35), CW, Inches(0.7),
        [who, "FEG Innovation Challenge 2026  ·  Croatian brand (PSK) track"],
        size=13, color=MUTED)

    # 2 ------------------------------------------------------- problem
    s = blank(prs)
    eyebrow(s, "01  /  THE PROBLEM")
    y = title(s, "One lobby. %s players." % format(F["players"], ","),
              "psk.hr's casino lobby is static. The biggest row is Najigranije — "
              "“most played” — and it is identical for every single player, "
              "whether they have played one game or three hundred.")
    gap = Inches(0.28)
    w3 = (CW - gap * 2) / 3
    stat(s, M, y + Inches(0.25), w3, "3,580",
         "launches from SEARCH — the single most common route to a game, ahead "
         "of every browsable surface. If you have to type the name, the lobby "
         "didn't surface it.", color=RED, h=Inches(1.85))
    stat(s, M + w3 + gap, y + Inches(0.25), w3, "%d–%d" % (F["cov_pop_tail"], F["cov_pop_disc"]),
         "games the top row can ever reach, of %s. About 1%% of the library — "
         "the same 1%% for everyone." % format(F["games"], ","),
         color=RED, h=Inches(1.85))
    stat(s, M + (w3 + gap) * 2, y + Inches(0.25), w3, "0",
         "personalised rows today. The widgets exist — top_10, providers, "
         "categories — but not one of them adapts to the player.",
         color=RED, h=Inches(1.85))
    txt(s, M, y + Inches(2.45), CW, Inches(0.8),
        [[("A seventh of all stake ", {"bold": True}),
          ("— €19.6M, 13.7% — sits on games a player was trying for the "
           "first time. That entire flow is served today by a search box and one "
           "row that never changes.", {})]],
        size=15, color=INK)
    footer(s, "01 / 12")

    # 3 ------------------------------------------------------- insight
    s = blank(prs)
    eyebrow(s, "02  /  THE INSIGHT")
    y = title(s, "Players already explore. They just explore badly.", rule=True)
    txt(s, M, y + Inches(0.1), Inches(3.5), Inches(1.5),
        "74%", size=88, bold=True, color=ACCENT)
    txt(s, M, y + Inches(1.5), Inches(4.3), Inches(1.2),
        [[("of plays in a held-out week were games the player had ", {}),
          ("never played before.", {"bold": True, "color": INK})]],
        size=15, color=INK2)

    xr = M + Inches(4.9)
    wr = CW - Inches(4.9)
    txt(s, xr, y + Inches(0.12), wr, Inches(1.0),
        "This is not an audience that needs persuading to try something new. "
        "They try new games constantly — through a search box and one global "
        "row. The demand for discovery is already there. The lobby simply "
        "doesn't serve it.", size=15, color=INK)
    rect(s, xr, y + Inches(1.35), wr, Inches(1.55), fill=PANEL, line=LINE)
    txt(s, xr + Inches(0.28), y + Inches(1.55), wr - Inches(0.56), Inches(1.2),
        [[("And they have clear favourites. ", {"bold": True, "color": INK}),
          ("A median 78% of a player's launches sit in their top-3 games, and "
           "65% come from a single provider.", {})]],
        size=13.5, color=INK2)
    txt(s, xr, y + Inches(3.05), wr, Inches(0.8),
        [[("So the lobby has two jobs, not one: ", {"bold": True, "color": INK}),
          ("get them back to what they love, and show them what's next. We "
           "built and measured both separately.", {})]],
        size=14, color=INK2)
    footer(s, "02 / 12")

    # 4 ----------------------------------------------------- what we built
    s = blank(prs)
    eyebrow(s, "03  /  THE PRODUCT")
    y = title(s, "Sign in, and the lobby becomes yours.",
              "One gesture. Signed out you get what every psk.hr visitor gets "
              "today; signed in, the same page rebuilds from that player's own "
              "history.")
    half = (CW - Inches(0.34)) / 2
    rect(s, M, y + Inches(0.2), half, Inches(1.15), fill=PANEL, line=LINE)
    txt(s, M + Inches(0.26), y + Inches(0.38), half - Inches(0.5), Inches(0.9),
        [[("SIGNED OUT", {"font": MONO, "size": 11, "bold": True, "color": RED})],
         [("2 rows — Popularno, Nove igre. Identical for all %s players."
           % format(F["players"], ","), {"size": 13, "color": INK2})]])
    rect(s, M + half + Inches(0.34), y + Inches(0.2), half, Inches(1.15),
         fill=PANEL, line=LINE)
    txt(s, M + half + Inches(0.6), y + Inches(0.38), half - Inches(0.5), Inches(0.9),
        [[("SIGNED IN", {"font": MONO, "size": 11, "bold": True, "color": GREEN})],
         [("6 rows, built from that player's history by the trained ranker.",
           {"size": 13, "color": INK2})]])

    table(s, M, y + Inches(1.62), CW, [
        ["Row", "What it is"],
        ["Nastavi igrati", "Their own games, recency-weighted. Serves 100% of players"],
        ["Preporučeno za tebe",
         "“Jer igraš 4 Scarab Coins: Hold and Win” — the trained ranker"],
        ["Otkrij nešto novo", "The tail: same model, blockbusters removed"],
        ["Jackpoti", "%d jackpot-eligible titles, ordered by the same model" % F["jackpot"]],
        ["Popularno", "The row PSK ships today — kept unchanged, and that is the point"],
        ["Nove igre", "%d genuinely new titles, from real release age" % F["new_games"]],
    ], [0.26, 0.74], rowh=Inches(0.36))
    footer(s, "03 / 12")

    # 5 ----------------------------------------------------------- demo
    s = blank(prs)
    rect(s, Inches(0), Inches(0), W, H, fill=DARK)
    rect(s, Inches(0), Inches(0), W, Inches(0.13), fill=ACCENT)
    txt(s, M, Inches(1.5), CW, Inches(0.5),
        [[("LIVE  DEMO", {"font": MONO, "size": 13, "bold": True,
                          "color": RGBColor(0x6F, 0xA8, 0xE8)})]])
    txt(s, M, Inches(2.0), Inches(9.5), Inches(1.4),
        "Watch two rows become six.", size=44, bold=True, color=WHITE)
    beats = [
        "The anonymous lobby — what all %s players see today"
        % format(F["players"], ","),
        "Sign in as ana.k — the same page rebuilds into six rows",
        "Read a tile: “Jer igraš …” is the literal top contributor "
        "to that score, not a generated sentence",
        "davor.z — sign-in REFUSED. Age unverified; the check must precede play",
        "lucija.h — signs in, zero rows. Self-exclusion blocks inducements, "
        "not account access",
    ]
    for i, b in enumerate(beats):
        yy = Inches(3.55) + Inches(0.46) * i
        txt(s, M, yy, Inches(0.4), Inches(0.4),
            [[("0%d" % (i + 1), {"font": MONO, "size": 12, "bold": True,
                                 "color": RGBColor(0x6F, 0xA8, 0xE8)})]])
        txt(s, M + Inches(0.55), yy, CW - Inches(0.6), Inches(0.45), b,
            size=14, color=RGBColor(0xC9, 0xD3, 0xE0))
    txt(s, M, H - Inches(0.85), CW, Inches(0.4),
        "12 demo accounts, generated from real player histories in the model. "
        "The change you are watching is the ranker running on that player's data — not a mock-up.",
        size=12, color=RGBColor(0x82, 0x8F, 0xA0))

    # 6 ------------------------------------------------- the honest loss
    s = blank(prs)
    eyebrow(s, "04  /  THE FINDING WE DIDN'T WANT", RED)
    y = title(s, "Our recommender lost.",
              "On predicting the next game a player tries, collaborative "
              "filtering was beaten outright by the global popularity row PSK "
              "already ships.")
    tw = Inches(5.5)
    table(s, M, y + Inches(0.22), tw, [
        ["Model", ("NDCG@10", {"align": PP_ALIGN.RIGHT})],
        [("most_played", {"font": MONO, "bold": True}),
         ("%.3f" % F["disc_pop"], {"align": PP_ALIGN.RIGHT, "bold": True, "color": GREEN})],
        [("provider_popular", {"font": MONO}),
         ("%.3f" % F["prov_disc"], {"align": PP_ALIGN.RIGHT})],
        [("item-item CF  (ours)", {"font": MONO}),
         ("%.3f" % F["cf_disc"], {"align": PP_ALIGN.RIGHT, "color": RED})],
    ], [0.62, 0.38], rowh=Inches(0.42))
    txt(s, M, y + Inches(2.05), tw, Inches(0.7),
        "Discovery task, 9,102 players. We tuned hard before accepting it — "
        "popularity correction, shrinkage, neighbourhood size, and a "
        "popularity-blended hybrid across eight weights. Nothing beat plain popularity.",
        size=12.5, color=MUTED)

    xr = M + tw + Inches(0.5)
    wr = CW - tw - Inches(0.5)
    txt(s, xr, y + Inches(0.22), wr, Inches(0.5),
        "Why — and it is a real fact about PSK", size=15, bold=True, color=INK)
    txt(s, xr, y + Inches(0.75), wr, Inches(1.4),
        "What players try next is overwhelmingly what is already popular. "
        "Spearman correlation between a game's popularity and its next-week "
        "discovery count is 0.79. One title — Goal Goal Goal: Cash Collect — "
        "takes 13% of all discovery plays on its own.", size=13.5, color=INK2)
    rect(s, xr, y + Inches(2.3), wr, Inches(0.95), fill=PANEL, line=ACCENT, lw=1.4)
    txt(s, xr + Inches(0.24), y + Inches(2.5), wr - Inches(0.48), Inches(0.6),
        [[("So we kept the popularity row. ", {"bold": True, "color": INK}),
          ("Replacing it would have made the lobby worse.", {})]],
        size=14, color=INK2)
    footer(s, "04 / 12")

    # 7 --------------------------------------------------- the tail result
    s = blank(prs)
    eyebrow(s, "05  /  THE RESULT THAT JUSTIFIES THE BUILD", GREEN)
    y = title(s, "But popularity only knows %d games." % F["cov_pop_tail"],
              "Remove the global top-50 — the blockbusters everyone already "
              "sees — and the result reverses completely.")
    tw = Inches(5.5)
    table(s, M, y + Inches(0.18), tw, [
        ["Model", ("NDCG@10", {"align": PP_ALIGN.RIGHT})],
        [("Trained ranker", {"bold": True}),
         ("%.4f" % F["ranker_ndcg"], {"align": PP_ALIGN.RIGHT, "bold": True, "color": GREEN})],
        [("Blend (sequence + CF)", {}), ("%.4f" % F["blend"], {"align": PP_ALIGN.RIGHT})],
        [("Sequence", {}), ("%.4f" % F["seq"], {"align": PP_ALIGN.RIGHT})],
        [("Item-item CF", {}), ("%.4f" % F["cf"], {"align": PP_ALIGN.RIGHT})],
        [("most_played", {"font": MONO}),
         ("%.4f" % F["pop_ndcg_tail"], {"align": PP_ALIGN.RIGHT, "color": RED})],
    ], [0.62, 0.38], rowh=Inches(0.355))

    xr = M + tw + Inches(0.5)
    wr = CW - tw - Inches(0.5)
    sw = (wr - Inches(0.24)) / 2
    stat(s, xr, y + Inches(0.18), sw, "%.2f×" % F["ratio"],
         "accuracy on the tail vs the popularity baseline", color=GREEN, bigsize=36)
    stat(s, xr + sw + Inches(0.24), y + Inches(0.18), sw, "%.0f×" % F["cov_mult"],
         "the catalogue reached — %d games instead of %d"
         % (F["cov_ranker"], F["cov_pop_tail"]), color=GREEN, bigsize=36)
    stat(s, xr, y + Inches(1.78), wr, "76.5%",
         "of all discovery plays live in that tail. This is not a niche we "
         "invented — it is where most exploration already happens.",
         color=ACCENT, bigsize=36)

    txt(s, M, y + Inches(2.55), tw, Inches(0.9),
        "Logistic regression over 14 features, ~200,000 labelled rows. "
        "Hyperparameters chosen on a separate validation week — never the "
        "test week. Ordering holds at the top-20 and top-100 boundaries too, "
        "so it is not an artefact of where we drew the line.",
        size=12, color=MUTED)
    footer(s, "05 / 12")

    # 8 ------------------------------------------------------ the design
    s = blank(prs)
    eyebrow(s, "06  /  THE DESIGN THAT FOLLOWS")
    y = title(s, "Popularity owns the head. We own the tail.",
              "The recommender is additive. Nothing that already worked was "
              "removed, so the downside is bounded at screen space — and every "
              "row ships behind its own feature flag.")
    table(s, M, y + Inches(0.2), CW, [
        ["Row", "Source", "Why it earns its place"],
        [("Popularno", {"bold": True}), "popularity",
         "The incumbent row (Najigranije), unchanged — because it wins its job"],
        [("Nastavi igrati", {"bold": True}), "recency-weighted history",
         "Their own games, most recent first. NDCG 0.73 — and we label it the easy task it is"],
        [("Preporučeno za tebe", {"bold": True}), "trained ranker",
         "“Because you played X” — the literal top contributor to the score"],
        [("Otkrij nešto novo", {"bold": True}), "ranker, top-50 removed",
         "Where the %.2f× lives" % F["ratio"]],
        [("Jackpoti", {"bold": True}), "ranker + eligibility",
         "%d jackpot titles, ordered by the model rather than by prize size" % F["jackpot"]],
        [("Nove igre", {"bold": True}), "cold items",
         "12.1% of discovery is on games with zero history — no CF can ever reach them"],
    ], [0.21, 0.22, 0.57], rowh=Inches(0.44))
    footer(s, "06 / 12")

    # 9 -------------------------------------------------------- compliance
    s = blank(prs)
    eyebrow(s, "07  /  COMPLIANCE BY DESIGN")
    y = title(s, "The gate runs before the model.",
              "And there are two of them, firing at different points, because "
              "the law treats them differently. Getting either backwards would "
              "be a real compliance failure — so both are asserted in tests "
              "rather than described in prose.")
    table(s, M, y + Inches(0.18), CW, [
        ["Gate", "Where it fires", "Why there"],
        [("Age / ID unverified", {"bold": True, "color": RED}),
         ("At sign-in — refused, no session issued", {"bold": True}),
         "Croatia's Act on Measures for Socially Responsible Organisation of "
         "Games of Chance: the check must precede play"],
        [("Self-excluded", {"bold": True, "color": RED}),
         ("After sign-in — account opens, lobby returns zero rows", {"bold": True}),
         "Self-exclusion blocks inducements, not account access. The person "
         "must still reach their account and support"],
    ], [0.19, 0.31, 0.50], rowh=Inches(0.66))
    bullets(s, M, y + Inches(1.98), CW, [
        [[("Graded inversion. ", {"bold": True, "color": INK}),
          ("From MODERATE the objective flips — every engagement row is withheld, "
           "only Nastavi igrati survives, and the withheld rows come back in the "
           "response so the decision is auditable.", {})]],
        [[("Explainable by construction. ", {"bold": True, "color": INK}),
          ("Every tile carries the literal top contributor to its score, and a "
           "test proves that attribution reconstructs the model's probability "
           "exactly. EU AI Act 2024/1689.", {})]],
        [[("No stake suggestion exists in the codebase. ", {"bold": True, "color": INK}),
          ("Games, never amounts. No countdowns, no scarcity, no “others are "
           "playing”, no near-miss framing.", {})]],
    ], size=13)
    footer(s, "07 / 12")

    # 10 ------------------------------------------------- the business case
    s = blank(prs)
    eyebrow(s, "08  /  BUSINESS IMPACT — AND WHAT WE COULD NOT PROVE", GOLD)
    y = title(s, "We refuse to give you a revenue number.",
              "We looked for one. Three tests, and it did not survive contact "
              "with the data. Reporting it anyway would have been the easy thing to do.")
    half = (CW - Inches(0.4)) / 2
    rect(s, M, y + Inches(0.18), half, Inches(2.5), fill=PANEL, line=LINE)
    txt(s, M + Inches(0.26), y + Inches(0.38), half - Inches(0.52), Inches(2.1),
        [[("What is real", {"size": 14, "bold": True, "color": INK})],
         [("€19.6M — 13.7% of all stake — sits on games a player was "
           "trying for the first time. 138,041 first-time adoptions a fortnight, "
           "median €16.16 each.", {"size": 13, "color": INK2})],
         [("Tail games are not the cheap end: median stake €17.00 against "
           "€10.50 for a top-50 game.", {"size": 13, "color": INK2})]],
        spacing=1.3)
    rect(s, M + half + Inches(0.4), y + Inches(0.18), half, Inches(2.5),
         fill=WHITE, line=RED, lw=1.2)
    txt(s, M + half + Inches(0.66), y + Inches(0.38), half - Inches(0.52), Inches(2.1),
        [[("What failed", {"size": 14, "bold": True, "color": RED})],
         [("Breadth correlates hugely with value (1–2 games €16 → 26+ "
           "games €5,446) — but it is confounded by activity level.",
           {"size": 13, "color": INK2})],
         [("Matched on week-3 activity, adopters retain no better: 56.8% vs 57.6%.",
           {"size": 13, "color": INK2})],
         [("And they stake less the following week at every matched band — "
           "€155 against €246.", {"size": 13, "color": INK2})]],
        spacing=1.3)
    reframe = ("The reframe. Exploration correlates with lower value because "
               "exploration currently fails — players hunt and don't find. The "
               "product's job is not more exploration; it is making the "
               "exploration they already do succeed. The experiment that "
               "settles it: A/B on the lobby, primary metric = first-time "
               "adoptions replayed within 7 days. That separates found "
               "something good from tried and bounced — exactly what the "
               "failed tests could not.")
    rh = text_h(reframe, (CW - Inches(0.56)) / 914400.0, 13, 1.25)
    rect(s, M, y + Inches(2.9), CW, rh + Inches(0.44), fill=PANEL,
         line=ACCENT, lw=1.4)
    txt(s, M + Inches(0.28), y + Inches(3.12), CW - Inches(0.56), rh,
        [[("The reframe. ", {"bold": True, "color": INK}),
          ("Exploration correlates with lower value because exploration currently "
           "fails — players hunt and don't find. The product's job is not more "
           "exploration; it is making the exploration they already do succeed. ",
           {}),
          ("The experiment that settles it: ", {"bold": True, "color": INK}),
          ("A/B on the lobby, primary metric = first-time adoptions replayed "
           "within 7 days. That separates “found something good” from "
           "“tried and bounced” — exactly what the failed tests could not.",
           {})]],
        size=13, color=INK2, spacing=1.25)
    footer(s, "08 / 12")

    # 11 ------------------------------------------------- constraint & ask
    s = blank(prs)
    eyebrow(s, "09  /  THE CONSTRAINT, AND THE ONE ASK")
    y = title(s, "%.0f%% of stake is on games we cannot name." % F["unnamed_pct"],
              "The export identifies most games by opaque codes like "
              "pop_9f571b7a_egtfeg. They train the model — their co-occurrence "
              "is real signal — but they can never be recommended, because a "
              "player has no way to know what they are being offered.")
    gap = Inches(0.28)
    w3 = (CW - gap * 2) / 3
    stat(s, M, y + Inches(0.2), w3, "%.0f%%" % F["unnamed_pct"],
         "of all stake still sits on games with no title we can show a player",
         color=RED, h=Inches(1.5))
    stat(s, M + w3 + gap, y + Inches(0.2), w3, str(F["bridge_codes"]),
         "codes our name bridge recovered from behavioural co-occurrence alone "
         "— %.0f%% of all stake, taking the catalogue to %d games"
         % (F["bridged_pct"], F["displayable"]), color=GREEN, h=Inches(1.5))
    stat(s, M + (w3 + gap) * 2, y + Inches(0.2), w3, "~9×",
         "the addressable inventory, if FEG shares a game catalogue",
         color=ACCENT, h=Inches(1.5))
    txt(s, M, y + Inches(1.95), CW, Inches(0.8),
        [[("The bridge validates itself. ", {"bold": True, "color": INK}),
          ("It independently produced gpas_3chken_pop → “4 Crazy "
           "Cluckers” (111 votes) and gpas_wpisto_pop → “Mega Fire "
           "Blaze: Wild Pistolero” (48). Both slugs decode to their resolved "
           "titles — which the algorithm has no way to read.", {})]],
        size=13.5, color=INK2)
    rect(s, M, y + Inches(2.72), CW, Inches(1.0), fill=DARK)
    txt(s, M + Inches(0.3), y + Inches(2.92), CW - Inches(0.6), Inches(0.7),
        [[("The ask: a game catalogue — code → title, category, thumbnail. ",
           {"bold": True, "color": WHITE}),
          ("It costs FEG a database export, it is the single highest-value thing "
           "we could be given, and it is the only limit here we cannot engineer "
           "around.", {"color": RGBColor(0xC9, 0xD3, 0xE0)})]],
        size=14)
    footer(s, "09 / 12")

    # 12 ---------------------------------------------------------- close
    s = blank(prs)
    eyebrow(s, "10  /  WHERE IT STANDS")
    y = title(s, "The lobby should know who is looking at it.",
              "Today it doesn't — one row, %s players, %d games. We measured "
              "what personalisation can and cannot do here, kept the row that "
              "already worked, and added the %d games it could never reach."
              % (format(F["players"], ","), F["cov_pop_disc"], F["cov_ranker"]))
    half = (CW - Inches(0.4)) / 2
    rect(s, M, y + Inches(0.18), half, Inches(2.55), fill=PANEL, line=LINE)
    txt(s, M + Inches(0.26), y + Inches(0.38), half - Inches(0.52), Inches(2.2),
        [[("Shipped", {"size": 14, "bold": True, "color": GREEN})],
         [("Pipeline → model → API → lobby, end to end", {"size": 12.5, "color": INK2})],
         [("A real login journey — anonymous landing, 12 demo accounts", {"size": 12.5, "color": INK2})],
         [("~25 ms per personalised lobby. No GPU, no model fit at request time", {"size": 12.5, "color": INK2})],
         [("54 tests, green on a clean clone", {"size": 12.5, "color": INK2})],
         [("Eight documents — including the evaluation with the negative result in it", {"size": 12.5, "color": INK2})]],
        spacing=1.35)
    rect(s, M + half + Inches(0.4), y + Inches(0.18), half, Inches(2.55),
         fill=WHITE, line=LINE)
    txt(s, M + half + Inches(0.66), y + Inches(0.38), half - Inches(0.52), Inches(2.2),
        [[("Not built — and we say so", {"size": 14, "bold": True, "color": GOLD})],
         [("No Vue SDK yet — the dashboard is plain HTML", {"size": 12.5, "color": INK2})],
         [("No Kafka/Redis — the pipeline is offline, daily batch", {"size": 12.5, "color": INK2})],
         [("Prototype auth: hashed and signed, but no rate limiting or MFA", {"size": 12.5, "color": INK2})],
         [("No session-level sequence model", {"size": 12.5, "color": INK2})],
         [("No online experiment. Every number here is offline — “longer "
           "sessions” is an assumption an A/B test must check", {"size": 12.5, "color": INK2})]],
        spacing=1.35)
    rect(s, M, y + Inches(2.95), CW, Emu(12700), fill=LINE)
    txt(s, M, y + Inches(3.15), CW, Inches(0.5),
        [[("Team Q'Makers  ·  feg-hackathon-2026-QMakers  ·  "
           "FEG Innovation Challenge 2026",
           {"font": MONO, "size": 11.5, "color": MUTED})]])
    footer(s, "10 / 12")

    prs.save(OUT)
    return OUT, F


if __name__ == "__main__":
    lead = sys.argv[1] if len(sys.argv) > 1 else TEAM_LEAD
    members = sys.argv[2] if len(sys.argv) > 2 else TEAM_MEMBERS
    path, F = build(lead, members)
    print("wrote %s" % path)
    print("  %.2fx tail ratio · %d vs %d games · %.1f%% unnameable"
          % (F["ratio"], F["cov_ranker"], F["cov_pop_tail"], F["unnamed_pct"]))
