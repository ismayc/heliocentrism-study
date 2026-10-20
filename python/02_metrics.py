"""Team-season concentration of shot creation, league trends, break points,
and the NBA against the WNBA. Definitions in python/lib.py.

Writes (committed):
  output/team_seasons.csv   one row per team-season: created points, made
                            field goals, assisted share, the game-level and
                            season-level metrics (python/lib.py), the top
                            creator and their created points, and top1_z
                            (top1_share as a z-score within its
                            league-season, sample sd)
  output/league_seasons.csv league x season x metric: teams, mean, 95% t
                            interval
  output/breaks.csv         league x metric: best hinge break (season start
                            year) and its approximate 95% set, plus slopes
                            before and after, per season
  output/league_gap.csv     season x metric, seasons both leagues played
                            (the NBA season starting the year before the WNBA
                            season, so NBA 2024-25 sits beside WNBA 2025):
                            NBA mean minus WNBA mean with a 95% Welch interval
  output/leaders.csv        the 15 highest top1_share team-seasons per league,
                            and the 15 highest top1_z
  output/era_change.csv     league x metric: first five seasons against the
                            last five, difference in team-season means with a
                            95% Welch interval
--check recomputes everything from output/creators.csv and
output/team_shots.csv and fails on any difference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

OUT = lib.ROOT / "output"
METRICS = ["game_top1_share", "game_top2_share", "game_eff_creators",
           "top1_share", "top2_share", "eff_creators", "assisted_share"]
FILES = ["team_seasons", "league_seasons", "breaks", "league_gap", "leaders", "era_change"]
ERA_LEN = 5


def team_seasons(cr: pl.DataFrame, shots: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for (league, year, team_id), g in cr.group_by("league", "year", "team_id", maintain_order=True):
        g = g.sort(["created", "creator"], descending=[True, False])
        c = lib.concentration(g["created"].cast(pl.Float64).to_list())
        rows.append({"league": league, "year": year, "season": g["season"][0],
                     "team_id": team_id, "team": g["team"][0],
                     "created": int(g["created"].sum()), **c,
                     "top_creator": g["name"][0], "top_created": int(g["created"][0])})
    ts = pl.DataFrame(rows).join(shots, on=["league", "year", "team_id"], how="left")
    ts = ts.with_columns(
        top1_z=(pl.col("top1_share") - pl.col("top1_share").mean().over("league", "year"))
               / pl.col("top1_share").std().over("league", "year"))
    return ts.sort("league", "year", "team_id")


def league_seasons(ts: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for (league, year), g in ts.group_by("league", "year", maintain_order=True):
        for m in METRICS:
            mean, lo, hi = lib.mean_ci(g[m].to_list())
            rows.append({"league": league, "year": year, "season": g["season"][0],
                         "metric": m, "teams": g.height, "mean": mean, "lo": lo, "hi": hi})
    return pl.DataFrame(rows).sort("league", "metric", "year")


def breaks(ls: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for (league, m), g in ls.group_by("league", "metric", maintain_order=True):
        g = g.sort("year")
        t, y = g["year"].cast(pl.Float64).to_list(), g["mean"].to_list()
        prof = lib.hinge_profile(t, y)
        k, klo, khi = lib.break_set(prof, len(t))
        T = np.asarray(t)
        X = np.column_stack([np.ones_like(T), T, np.maximum(0.0, T - k)])
        b = np.linalg.solve(X.T @ X, X.T @ np.asarray(y))
        rows.append({"league": league, "metric": m, "break_year": int(k),
                     "break_lo": int(klo), "break_hi": int(khi),
                     "slope_before": float(b[1]), "slope_after": float(b[1] + b[2]),
                     "seasons": len(t)})
    return pl.DataFrame(rows).sort("league", "metric")


def league_gap(ts: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for wy in lib.YEARS["wnba"]:
        ny = wy - 1
        if ny not in lib.YEARS["nba"]:
            continue
        n = ts.filter((pl.col("league") == "nba") & (pl.col("year") == ny))
        w = ts.filter((pl.col("league") == "wnba") & (pl.col("year") == wy))
        for m in METRICS:
            d, lo, hi = lib.welch(n[m].to_list(), w[m].to_list())
            rows.append({"wnba_year": wy, "nba_season": lib.pbp_history.season_label("nba", ny),
                         "metric": m, "nba_mean": float(n[m].mean()), "wnba_mean": float(w[m].mean()),
                         "gap": d, "lo": lo, "hi": hi})
    return pl.DataFrame(rows).sort("metric", "wnba_year")


def era_change(ts: pl.DataFrame) -> pl.DataFrame:
    """First five seasons against the last five, per league and metric: the
    difference in team-season means with a 95% Welch interval. Team-seasons of
    one franchise in one block are treated as independent, which is
    approximate (a franchise's seasons are correlated)."""
    rows = []
    for league, years in lib.YEARS.items():
        ys = list(years)
        first, last = ys[:ERA_LEN], ys[-ERA_LEN:]
        a = ts.filter((pl.col("league") == league) & pl.col("year").is_in(first))
        b = ts.filter((pl.col("league") == league) & pl.col("year").is_in(last))
        for m in METRICS:
            d, lo, hi = lib.welch(b[m].to_list(), a[m].to_list())
            rows.append({"league": league, "metric": m,
                         "first": f"{lib.pbp_history.season_label(league, first[0])} to "
                                  f"{lib.pbp_history.season_label(league, first[-1])}",
                         "last": f"{lib.pbp_history.season_label(league, last[0])} to "
                                 f"{lib.pbp_history.season_label(league, last[-1])}",
                         "first_mean": float(a[m].mean()), "last_mean": float(b[m].mean()),
                         "first_n": a.height, "last_n": b.height,
                         "change": d, "lo": lo, "hi": hi})
    return pl.DataFrame(rows).sort("league", "metric")


def leaders(ts: pl.DataFrame) -> pl.DataFrame:
    out = []
    for league in lib.YEARS:
        x = ts.filter(pl.col("league") == league)
        for by in ("top1_share", "top1_z"):
            top = x.sort([by, "year", "team_id"], descending=[True, False, False]).head(15)
            out.append(top.select(pl.lit(by).alias("ranked_by"), pl.int_range(1, 16).alias("rank"),
                                  "league", "season", "team", "top_creator", "top1_share",
                                  "top1_z", "eff_creators"))
    return pl.concat(out)


def compute() -> dict[str, pl.DataFrame]:
    cr = pl.read_csv(OUT / "creators.csv")
    shots = pl.read_csv(OUT / "team_shots.csv").select(
        "league", "year", "team_id", "fgm", "assisted", "games", "game_top1_share",
        "game_top2_share", "game_eff_creators",
        assisted_share=pl.col("assisted") / pl.col("fgm"))
    ts = team_seasons(cr, shots)
    ls = league_seasons(ts)
    r12 = lambda df: df.with_columns(pl.col(pl.Float64).round(12))  # noqa: E731
    return {"team_seasons": r12(ts), "league_seasons": r12(ls), "breaks": r12(breaks(ls)),
            "league_gap": r12(league_gap(ts)), "leaders": r12(leaders(ts)),
            "era_change": r12(era_change(ts))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    res = compute()
    if args.check:
        fails = [f"{n}.csv differs from a fresh build" for n, df in res.items()
                 if not lib.frames_match(df, pl.read_csv(OUT / f"{n}.csv", schema_overrides=df.schema))]
        for f in fails:
            print("FAIL", f)
        print("METRICS", "FAILED" if fails else
              f"PASSED: {res['team_seasons'].height:,} team-seasons")
        return 1 if fails else 0
    for n, df in res.items():
        df.write_csv(OUT / f"{n}.csv")
    with pl.Config(tbl_rows=40, tbl_width_chars=200):
        print(res["era_change"].select("league", "metric", "first_mean", "last_mean",
                                       "change", "lo", "hi"))
        print(res["league_gap"].filter(pl.col("metric") == "game_top1_share"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
