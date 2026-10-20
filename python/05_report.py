"""Write the README's results section from the output tables, so no number in
it is typed by hand. Replaces the text between <!-- gen:results --> and
<!-- /gen:results -->. --check fails if the README is out of date.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
README = ROOT / "README.md"
START, END = "<!-- gen:results -->", "<!-- /gen:results -->"
LEAGUE = {"nba": "NBA", "wnba": "WNBA"}
LABEL = {"game_top1_share": "Top creator's share, per game",
         "game_top2_share": "Top two creators' share, per game",
         "game_eff_creators": "Effective number of creators, per game",
         "top1_share": "Top creator's share, season totals",
         "top2_share": "Top two creators' share, season totals",
         "eff_creators": "Effective number of creators, season totals",
         "assisted_share": "Assisted share of made field goals"}
COUNT = {"game_eff_creators", "eff_creators"}


def fmt(m: str, x: float, signed: bool = False) -> str:
    if m in COUNT:
        return f"{x:+.2f}" if signed else f"{x:.2f}"
    return f"{100 * x:+.1f}" if signed else f"{100 * x:.1f}%"


def join(items: list[str]) -> str:
    """English list with the Oxford comma."""
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def excludes_zero(r: dict) -> bool:
    return r["lo"] > 0 or r["hi"] < 0


def results() -> str:
    val = pl.read_csv(OUT / "validation.csv")
    era = pl.read_csv(OUT / "era_change.csv")
    gap = pl.read_csv(OUT / "league_gap.csv")
    br = pl.read_csv(OUT / "breaks.csv")
    lead = pl.read_csv(OUT / "leaders.csv")

    g = val.group_by("league").agg(pl.col("games", "assisted", "unresolved").sum())
    gl = {r["league"]: r for r in g.iter_rows(named=True)}
    low_ast = val.filter(pl.col("ast_match") < 0.99)
    lines = [
        f"Coverage: {gl['nba']['games']:,} NBA games (1996-97 to 2025-26) and "
        f"{gl['wnba']['games']:,} WNBA games (1997 to 2026), every regular-season game "
        "that passes the shared layer's score checks, with "
        f"{gl['nba']['assisted'] + gl['wnba']['assisted']:,} assisted baskets. "
        f"{gl['nba']['unresolved'] + gl['wnba']['unresolved']:,} passers "
        f"({(gl['nba']['unresolved'] + gl['wnba']['unresolved']) / (gl['nba']['assisted'] + gl['wnba']['assisted']):.2%}) "
        "could not be matched to a player and are left out. Parsed team assists equal "
        f"LeagueGameLog's in at least {val.filter(pl.col('ast_match') >= 0.99)['ast_match'].min():.1%} "
        "of team-games in every season except "
        + join([f"{LEAGUE[r['league']]} {r['season']} ({r['ast_match']:.1%})"
                for r in low_ast.iter_rows(named=True)])
        + "; made field goals match in at least "
        f"{val['fgm_match'].min():.1%}. Every table is computed in Python and again in R "
        "from the same events, and the two agree on every cell.",
        "",
        "### 1. First five seasons against the last five",
        "",
        "Team-season means; the change is last minus first with a 95% Welch interval "
        "(percentage points for shares, creators for counts):",
        "",
        "| Measure | League | First | Last | Change |",
        "|---|---|---|---|---|",
    ]
    for m in LABEL:
        for lg in LEAGUE:
            r = era.filter((pl.col("league") == lg) & (pl.col("metric") == m)).row(0, named=True)
            mark = "" if excludes_zero(r) else " (includes zero)"
            lines.append(f"| {LABEL[m]} | {LEAGUE[lg]} | {fmt(m, r['first_mean'])} | "
                         f"{fmt(m, r['last_mean'])} | {fmt(m, r['change'], True)} "
                         f"({fmt(m, r['lo'], True)} to {fmt(m, r['hi'], True)}){mark} |")
    n1 = era.filter((pl.col("league") == "nba") & (pl.col("metric") == "game_top1_share")).row(0, named=True)
    w1 = era.filter((pl.col("league") == "wnba") & (pl.col("metric") == "game_top1_share")).row(0, named=True)
    na = era.filter((pl.col("league") == "nba") & (pl.col("metric") == "assisted_share")).row(0, named=True)
    nb = br.filter((pl.col("league") == "nba") & (pl.col("metric") == "game_top1_share")).row(0, named=True)
    wb = br.filter((pl.col("league") == "wnba") & (pl.col("metric") == "game_top1_share")).row(0, named=True)
    direction = lambda r: ("fell" if r["hi"] < 0 else "rose" if r["lo"] > 0 else "did not change measurably")  # noqa: E731
    lines += [
        "",
        f"In the NBA the top creator's share per game {direction(n1)}, from "
        f"{fmt('x', n1['first_mean'])} to {fmt('x', n1['last_mean'])}; in the WNBA it "
        f"{direction(w1)} ({fmt('x', w1['first_mean'])} to {fmt('x', w1['last_mean'])}). "
        "Season totals move further than per-game shares in the NBA, which is what a "
        "rise in games missed by top players would produce (not measured here). "
        f"Assisted share {direction(na)} in the NBA ({fmt('x', na['first_mean'])} to "
        f"{fmt('x', na['last_mean'])}): more baskets credited to a passer spreads creation, "
        "so part of the fall is how creation is counted, not only who has the ball (see "
        "Limits).",
        "",
        f"Hinge fits on the season means put the NBA's turn in {nb['break_year']} "
        f"(approximate 95% set {nb['break_lo']} to {nb['break_hi']}; slope "
        f"{100 * nb['slope_before']:+.2f} points a season before, "
        f"{100 * nb['slope_after']:+.2f} after) and the WNBA's in {wb['break_year']} "
        f"({wb['break_lo']} to {wb['break_hi']}; {100 * wb['slope_before']:+.2f}, then "
        f"{100 * wb['slope_after']:+.2f}). Both sets are wide: the data date a drift, not "
        "a moment. Every measure's fit is in `output/breaks.csv`.",
        "",
        "![Top creator's share per game](figures/fig1_game_top1_py.png)",
        "",
        "### 2. NBA against WNBA, season by season",
        "",
    ]
    t1 = gap.filter(pl.col("metric") == "game_top1_share").sort("wnba_year")
    nba_more = t1.filter(pl.col("lo") > 0)
    wnba_more = t1.filter(pl.col("hi") < 0)
    yrs = lambda df: join([str(y) for y in df["wnba_year"].to_list()]) or "none"  # noqa: E731
    last = t1.row(-1, named=True)
    lines += [
        f"On the top creator's share per game, the NBA was the more concentrated league, "
        f"with a 95% Welch interval excluding zero, in {nba_more.height} of {t1.height} "
        f"seasons (WNBA years {yrs(nba_more)}), and the WNBA in {wnba_more.height} "
        f"({yrs(wnba_more)}). In {last['wnba_year']} the gap was "
        f"{100 * last['gap']:+.1f} points ({100 * last['lo']:+.1f} to {100 * last['hi']:+.1f}), "
        f"NBA {last['nba_season']} against WNBA {last['wnba_year']}.",
        "",
        "![NBA minus WNBA](figures/fig2_league_gap_py.png)",
        "",
        "![Assisted share](figures/fig3_assisted_share_py.png)",
        "",
        "### 3. The most heliocentric team-seasons",
        "",
        "By the top creator's share of the team's season created points; z is the same "
        "share against that league-season's teams (sample standard deviation):",
        "",
    ]
    for lg in LEAGUE:
        top = lead.filter((pl.col("league") == lg) & (pl.col("ranked_by") == "top1_share")).sort("rank").head(10)
        lines += [f"**{LEAGUE[lg]}**", "", "| Rank | Season | Team | Top creator | Share | z |",
                  "|---|---|---|---|---|---|"]
        for r in top.iter_rows(named=True):
            lines.append(f"| {r['rank']} | {r['season']} | {r['team']} | {r['top_creator']} | "
                         f"{100 * r['top1_share']:.1f}% | {r['top1_z']:.2f} |")
        lines.append("")
    lines.append("Top 15 by share and by z, per league: `output/leaders.csv`.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = README.read_text()
    a, b = text.index(START) + len(START), text.index(END)
    new = text[:a] + "\n" + results() + "\n" + text[b:]
    if args.check:
        ok = new == text
        print("REPORT", "PASSED: README results match the outputs" if ok else
              "FAILED: README results are stale; run python/05_report.py")
        return 0 if ok else 1
    README.write_text(new)
    print("README results written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
