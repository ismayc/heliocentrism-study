"""Explainer diagrams for the story page, drawn with the family's famdiagram
(../basketball-analysis-tools/famdiagram.py) and saved to figures/<ref>.svg
(plus a <ref>_narrow.svg phone layout). report_builder.py inlines them.

Every number drawn is read from a committed output, except the clearly
labeled illustration in dg3 (ILLUSTRATION below), which is a made-up team
and says so on the diagram.

Diagrams:
  dg1_crediting     how a basket is credited and how one real team-game's
                    credited points become shares, the top creator's share,
                    and the effective number of creators
                    (output/example_game.csv, output/example_plays.csv)
  dg2_two_teams     the 2008-09 Hornets against the typical 2025-26 NBA team
                    (the lower median of that season's top-creator shares),
                    every creator's share of the season's created points
                    (output/creators.csv, output/team_seasons.csv)
  dg3_missed_games  why season totals overstate the decline: an illustration
                    of a star who misses games, beside the real NBA change
                    measured both ways (output/era_change.csv)

Run:     python python/07_diagrams.py
--check: rebuild every SVG in memory and fail if a committed one differs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
FIG = ROOT / "figures"
sys.path.insert(0, str(ROOT.parent / "basketball-analysis-tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import famdiagram as fd  # noqa: E402
import lib  # noqa: E402

WORD = {2: "two", 3: "three"}
# dg3's made-up team. Labeled "Illustration" on the diagram; not data.
ILLUSTRATION = {"games": 10, "missed": (4, 7, 8), "team_points": 100,
                "star": 30, "deputy_with_star": 15, "deputy_without_star": 25}
TYPICAL_YEAR = 2025          # the season python/06_example_game.py uses
HELIO = ("nba", "2008-09", "C. Paul")   # text keys; numbers from creators.csv


def pct(v: float, d: int = 1) -> str:
    return f"{v * 100:.{d}f}%"


def wrap(s: str, width: float, size: float) -> list[str]:
    """Greedy word wrap on an estimated glyph width."""
    per = size * 0.55
    out, cur = [], ""
    for w in s.split():
        t = f"{cur} {w}".strip()
        if len(t) * per > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        out.append(cur)
    return out


def para(d: fd.Diagram, x, y, s, width, size, lh=None, **kw) -> float:
    """Wrapped text; returns the baseline after the last line."""
    lh = lh or size * 1.35
    for i, line in enumerate(wrap(s, width, size)):
        d.text(x, y + i * lh, line, size=size, **kw)
    return y + (len(wrap(s, width, size)) - 1) * lh


# ---------------------------------------------------------------- dg1
def crediting(narrow: bool) -> fd.Diagram:
    game = pl.read_csv(OUT / "example_game.csv")
    plays = {r["kind"]: r for r in pl.read_csv(OUT / "example_plays.csv").iter_rows(named=True)}
    c = lib.concentration(game["created"].cast(pl.Float64).to_list())
    total = int(game["created"].sum())
    shares = [v / total for v in game["created"].to_list()]
    sumsq = sum(s * s for s in shares)
    g0 = game.row(0, named=True)
    date = dt.date.fromisoformat(g0["game_date"])
    where = "vs" if g0["home"] else "at"
    gtitle = (f"{g0['team']} {where} {g0['opponent']}, "
              f"{date.strftime('%B')} {date.day}, {date.year}")

    W = 360 if narrow else 760
    fs, small, head = (13, 12, 17) if narrow else (15, 14, 20)
    d = fd.Diagram(W, 10, "How a basket is credited and how one game's credit becomes shares")
    pad = 12
    y = 28
    d.text(pad, y, "1. Credit each made basket to one creator", size=head, display=True,
           weight="600")
    y += 14
    cards = [("assisted", "Assisted make", "nba"), ("unassisted", "Unassisted make", "ink2")]
    cw = W - 2 * pad if narrow else (W - 3 * pad) / 2
    ch = 132 if narrow else 140
    for i, (k, lab, col) in enumerate(cards):
        p = plays[k]
        cx = pad if narrow else pad + i * (cw + pad)
        cy = y + (i * (ch + 10) if narrow else 0)
        d.rect(cx, cy, cw, ch, fill="surface2", stroke="rule", rx=8)
        d.text(cx + 12, cy + 24, lab, size=fs + 1, weight="700", fill=col)
        made = f"{p['shooter']} makes a {WORD[p['points']]}"
        how = (f"assisted by {p['passer']}" if k == "assisted" else "with no assist recorded")
        d.text(cx + 12, cy + 50, made + ",", size=fs, fill="ink")
        d.text(cx + 12, cy + 50 + fs * 1.4, how, size=fs, fill="ink")
        role = "the passer" if k == "assisted" else "the shooter"
        py = cy + ch - 38
        d.rect(cx + 12, py, cw - 24, 26, fill=col if k == "assisted" else "ink3", rx=13)
        d.text(cx + cw / 2, py + 18, f"+{p['points']} points to {p['credited']}, {role}",
               size=fs, fill="surface", anchor="middle", weight="600")
    y += (2 * ch + 10 if narrow else ch) + 40

    para(d, pad, y, f"2. Add up one game: {gtitle}", W - 2 * pad, head, display=True,
         weight="600")
    y += (len(wrap(f"2. Add up one game: {gtitle}", W - 2 * pad, head)) - 1) * head * 1.35
    y += 20
    # legend
    d.rect(pad, y - 10, 12, 12, fill="nba", rx=2)
    d.text(pad + 18, y, "own unassisted makes", size=small, fill="ink2")
    lx = pad + 18 + len("own unassisted makes") * small * 0.55 + 14
    d.rect(lx, y - 10, 12, 12, fill="nba", rx=2, opacity=0.4)
    d.text(lx + 18, y, "assists to teammates", size=small, fill="ink2")
    y += 14
    name_w = 104 if narrow else 120
    bar_x = pad + name_w + 6
    bar_max = (W - bar_x - 96) if narrow else 220
    top = game["created"].max()
    rh = 24 if narrow else 26
    for j, r in enumerate(game.iter_rows(named=True)):
        ry = y + j * rh
        d.text(bar_x - 6, ry + rh * 0.68, r["name"], size=small, fill="ink",
               anchor="end", weight="700" if j == 0 else None)
        wo = bar_max * r["own"] / top
        wp = bar_max * r["passed"] / top
        if wo:
            d.rect(bar_x, ry + 4, wo, rh - 8, fill="nba", rx=2)
        if wp:
            d.rect(bar_x + wo, ry + 4, wp, rh - 8, fill="nba", rx=2, opacity=0.4)
        d.text(bar_x + wo + wp + 6, ry + rh * 0.68,
               f"{r['created']} ({pct(r['created'] / total)})", size=small, fill="ink2")
    y_bars_end = y + game.height * rh

    # arithmetic
    if narrow:
        ax, ay, aw = pad, y_bars_end + 18, W - 2 * pad
    else:
        ax, ay, aw = 470, y - 14, W - 470 - pad
    ah = 236
    d.rect(ax, ay, aw, ah, fill="surface2", stroke="rule", rx=8)
    tx = ax + 14
    d.text(tx, ay + 26, f"Created points in the game: {total}", size=fs, fill="ink")
    d.text(tx, ay + 58, "Top creator's share", size=fs, fill="ink2")
    d.text(tx, ay + 84, f"{g0['created']} / {total} = {pct(c['top1_share'])}", size=fs + 5,
           fill="nba", weight="700")
    d.text(tx, ay + 118, "Effective number of creators", size=fs, fill="ink2")
    d.text(tx, ay + 140, "1 / sum of squared shares", size=small, fill="ink2")
    d.text(tx, ay + 168, f"1 / {sumsq:.3f} = {c['eff_creators']:.2f}", size=fs + 5,
           fill="nba", weight="700")
    para(d, tx, ay + 194, "equal creators would give the same concentration",
         aw - 28, small, fill="ink3", italic=True)
    y = max(y_bars_end, ay + ah) + 34
    last = para(d, pad, y, "3. Repeat for every game. A team's measure is the average over "
                "its games, and a season's league value is the average over its teams.",
                W - 2 * pad, fs, fill="ink2")
    d.h = last + 16
    return d


# ---------------------------------------------------------------- dg2
def two_teams(narrow: bool) -> fd.Diagram:
    cr = pl.read_csv(OUT / "creators.csv")
    ts = pl.read_csv(OUT / "team_seasons.csv")
    lg, season, who = HELIO
    h = ts.filter((pl.col("league") == lg) & (pl.col("season") == season)
                  & (pl.col("top_creator") == who)).row(0, named=True)
    tt = (ts.filter((pl.col("league") == "nba") & (pl.col("year") == TYPICAL_YEAR))
            .sort(["top1_share", "team_id"]))
    t = tt.row((tt.height - 1) // 2, named=True)
    rows = []
    for r, tag in ((h, "The most concentrated NBA team-season"),
                   (t, f"The typical {t['season']} NBA team (median top share)")):
        g = (cr.filter((pl.col("league") == r["league"]) & (pl.col("year") == r["year"])
                       & (pl.col("team_id") == r["team_id"]))
               .sort(["created", "creator"], descending=[True, False]))
        tot = g["created"].sum()
        rows.append((r, tag, [(n, v / tot) for n, v in zip(g["name"], g["created"])]))

    W = 360 if narrow else 760
    fs, small, head = (13, 12, 17) if narrow else (15, 14, 20)
    pad = 12
    d = fd.Diagram(W, 10, "Two teams' creators as shares of their created points")
    bar_x = pad
    bar_w = (W - 2 * pad) if narrow else 520
    y = 26
    d.text(pad, y, "Each bar is one team's created points for a season;", size=fs, fill="ink2")
    d.text(pad, y + fs * 1.4, "each segment is one player's share", size=fs, fill="ink2")
    y += fs * 1.4 + 22
    for r, tag, segs in rows:
        d.text(pad, y + 4, f"{r['team']} {r['season']}", size=head + 2, display=True,
               weight="700")
        y = para(d, pad, y + 26, tag, (W - 2 * pad) if narrow else 500, small, fill="ink2") + 14
        # top creator label above the bar
        n0, s0 = segs[0]
        d.text(bar_x, y + 6, f"{n0} {pct(s0)}", size=fs + 2, fill="nba", weight="700")
        by = y + 16
        bh = 34
        x = bar_x
        for k, (n, s) in enumerate(segs):
            w = bar_w * s
            if k == 0:
                d.rect(x, by, w, bh, fill="nba")
            else:
                d.rect(x, by, w, bh, fill="ink3", opacity=0.62 if k % 2 else 0.38)
            if k > 0:
                d.line(x, by, x, by + bh, stroke="surface", sw=1.2)
            x += w
        d.rect(bar_x, by, bar_w, bh, fill="none", stroke="rule", sw=1)
        n1, s1 = segs[1]
        x1 = bar_x + bar_w * s0
        d.line(x1 + 2, by + bh + 2, x1 + 2, by + bh + 10, stroke="ink3", sw=1)
        d.text(x1 + 2, by + bh + 24, f"next: {n1} {pct(s1)}", size=small, fill="ink2")
        if narrow:
            d.text(bar_x, by + bh + 44, f"{len(segs)} players created points;", size=small,
                   fill="ink3")
            d.text(bar_x, by + bh + 64, f"effective creators {r['eff_creators']:.1f}",
                   size=fs + 1, fill="ink", weight="700")
            y = by + bh + 100
        else:
            ex = bar_x + bar_w + 24
            d.text(ex, by - 4, "Effective", size=small, fill="ink2")
            d.text(ex, by + 12, "creators", size=small, fill="ink2")
            d.text(ex, by + bh + 8, f"{r['eff_creators']:.1f}", size=34, display=True,
                   weight="700", fill="ink")
            d.text(ex, by + bh + 30, f"of {len(segs)} players", size=small, fill="ink3")
            y = by + bh + 78
    d.h = y - 18
    return d


# ---------------------------------------------------------------- dg3
def missed_games(narrow: bool) -> fd.Diagram:
    era = pl.read_csv(OUT / "era_change.csv").filter(pl.col("league") == "nba")
    per = era.filter(pl.col("metric") == "game_top1_share").row(0, named=True)
    sea = era.filter(pl.col("metric") == "top1_share").row(0, named=True)
    I = ILLUSTRATION
    games = list(range(1, I["games"] + 1))
    star = [0 if g in I["missed"] else I["star"] for g in games]
    dep = [I["deputy_without_star"] if g in I["missed"] else I["deputy_with_star"] for g in games]
    per_game = sum(max(a, b) for a, b in zip(star, dep)) / (I["team_points"] * I["games"])
    season_tot = max(sum(star), sum(dep)) / (I["team_points"] * I["games"])

    W = 360 if narrow else 760
    fs, small, head = (13, 12, 16) if narrow else (15, 14, 19)
    pad = 12
    d = fd.Diagram(W, 10, "Why season totals overstate the decline")
    lw = (W - 2 * pad) if narrow else 420
    # ---- illustration panel
    y = 26
    d.rect(pad, y - 18, 96, 24, fill="c4", rx=12, opacity=0.25)
    d.text(pad + 48, y - 1, "Illustration", size=small, fill="ink", anchor="middle",
           weight="700")
    d.text(pad + 106, y - 1, f"a made-up team, {I['games']} games", size=small, fill="ink2")
    y += 16
    plot_top, plot_h = y + 10, 120
    gx0 = pad + 4
    gw = (lw - 8) / I["games"]
    scale = plot_h / max(max(star), max(dep))
    base = plot_top + plot_h
    for i, g in enumerate(games):
        x = gx0 + i * gw
        bw = gw * 0.36
        if star[i]:
            d.rect(x + gw * 0.12, base - star[i] * scale, bw, star[i] * scale, fill="nba", rx=2)
        else:
            d.text(x + gw * 0.12 + bw / 2, base - 6, "out", size=small,
                   fill="nba", anchor="middle", italic=True)
        d.rect(x + gw * 0.12 + bw + 2, base - dep[i] * scale, bw, dep[i] * scale, fill="ink3",
               rx=2, opacity=0.7)
        d.text(x + gw / 2, base + 18, str(g), size=small,
               fill="ink3", anchor="middle")
    d.line(gx0, base, gx0 + lw - 8, base, stroke="rule", sw=1)
    ly = base + 40
    d.rect(pad, ly - 10, 12, 12, fill="nba", rx=2)
    d.text(pad + 18, ly, f"star: {I['star']} of {I['team_points']} points when playing",
           size=small, fill="ink2")
    d.rect(pad, ly + 10, 12, 12, fill="ink3", rx=2, opacity=0.7)
    d.text(pad + 18, ly + 20, f"teammate: {I['deputy_with_star']}, or "
           f"{I['deputy_without_star']} when the star is out", size=small, fill="ink2")
    ry = ly + 50
    d.text(pad, ry, "Top share in each game, averaged:", size=fs, fill="ink2")
    d.text(lw + pad, ry, pct(per_game), size=fs + 3, fill="nba", anchor="end", weight="700")
    d.text(pad, ry + 26, "Star's share of season totals:", size=fs, fill="ink2")
    d.text(lw + pad, ry + 26, pct(season_tot), size=fs + 3, fill="ink", anchor="end",
           weight="700")
    yb = para(d, pad, ry + 52, "Same star, same role every night; only the missed games "
              "pull the season-total share down.", lw, small, fill="ink3", italic=True)

    # ---- real result panel
    if narrow:
        px, py0, pw = pad, yb + 44, W - 2 * pad
    else:
        px, py0, pw = 470, 8, W - 470 - pad
    d.rect(px, py0, pw, 6 + 250, fill="surface2", stroke="rule", rx=8)
    tx = px + 14
    d.text(tx, py0 + 26, "The real NBA change", size=fs + 1, fill="ink", weight="700")
    yy = para(d, tx, py0 + 48, f"{sea['first']} against {sea['last']}, in points",
              pw - 28, small, fill="ink2")
    zero_x = px + pw - 22
    lo_all = min(sea["lo"], per["lo"])
    sc = (pw - 60) / abs(lo_all * 100)
    rows = [("Season totals", sea, "ink3"), ("Per game", per, "nba")]
    for k, (lab, r, col) in enumerate(rows):
        by = yy + 30 + k * 82
        d.text(tx, by, lab, size=fs, fill="ink", weight="600")
        bt = by + 10
        x0 = zero_x + r["change"] * 100 * sc
        d.rect(x0, bt, zero_x - x0, 20, fill=col, rx=2, opacity=0.85)
        xl, xh = zero_x + r["lo"] * 100 * sc, zero_x + r["hi"] * 100 * sc
        d.line(xl, bt + 10, xh, bt + 10, stroke="ink", sw=1.5)
        d.line(xl, bt + 4, xl, bt + 16, stroke="ink", sw=1.5)
        d.line(xh, bt + 4, xh, bt + 16, stroke="ink", sw=1.5)
        d.text(zero_x - 6, by, f"{r['change'] * 100:+.1f}", size=fs + 2,
               fill=col if col == "nba" else "ink", anchor="end", weight="700")
        d.text(tx, bt + 40, f"95% interval {r['lo'] * 100:+.1f} to {r['hi'] * 100:+.1f}",
               size=small, fill="ink3")
    d.line(zero_x, yy + 30, zero_x, yy + 30 + 2 * 82 - 30, stroke="ink2", sw=1)
    d.text(zero_x, yy + 30 + 2 * 82 - 12, "0", size=small, fill="ink2", anchor="middle")
    d.h = max(yb + 20, py0 + 262) if not narrow else py0 + 262
    return d


DIAGRAMS = {"dg1_crediting": crediting, "dg2_two_teams": two_teams,
            "dg3_missed_games": missed_games}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        fails = []
        with tempfile.TemporaryDirectory() as tmp:
            for ref, fn in DIAGRAMS.items():
                for p in fd.save(Path(tmp), ref, fn(False), fn(True)):
                    old = FIG / p.name
                    if not old.exists() or old.read_text() != p.read_text():
                        fails.append(p.name)
        for f in fails:
            print("FAIL", f, "differs from a fresh build")
        print("DIAGRAMS", "FAILED" if fails else f"PASSED: {len(DIAGRAMS)} diagrams rebuild identically")
        return 1 if fails else 0
    for ref, fn in DIAGRAMS.items():
        for p in fd.save(FIG, ref, fn(False), fn(True)):
            print("wrote", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
