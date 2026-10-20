"""One real team-game, extracted to show the crediting rule on the page.

The diagrams in python/07_diagrams.py explain the method with a real game
instead of made-up numbers. This script picks that game by a fixed rule and
writes its rows (a single illustrative game, so committing it is allowed):

  Team:  the 2025-26 NBA team at the lower median of the season's
         top-creator shares on season totals (output/team_seasons.csv), the
         same "typical team" python/07_diagrams.py sets beside the 2008-09
         Hornets.
  Game:  of that team's games with at most 8 creators (so the diagram can
         name each one), the one whose per-game top-creator share is closest
         to the team's own per-game average (output/team_shots.csv); ties go
         to the earlier gameId.

Writes (committed):
  output/example_game.csv   one row per creator in that team-game: points
                            created on their own unassisted makes and on
                            their assists, the total, and the game's
                            identifying fields
  output/example_plays.csv  two plays from the game: the team's first
                            assisted made three and its first unassisted
                            made two, with the shooter, the passer, and who
                            is credited

The game's shares and effective number of creators are not stored; the
diagram script computes them with lib.concentration. --check rebuilds both
files, compares them, and also checks that lib.game_concentration on the raw
events gives the same top share and effective number of creators as
lib.concentration on the extract, so the diagram's arithmetic is the
study's arithmetic.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

OUT = lib.ROOT / "output"
GAME = OUT / "example_game.csv"
PLAYS = OUT / "example_plays.csv"
LEAGUE, YEAR = "nba", 2025
MAX_CREATORS = 8


def pick_team() -> dict:
    ts = (pl.read_csv(OUT / "team_seasons.csv")
            .filter((pl.col("league") == LEAGUE) & (pl.col("year") == YEAR))
            .sort(["top1_share", "team_id"]))
    return ts.row((ts.height - 1) // 2, named=True)


def build() -> tuple[pl.DataFrame, pl.DataFrame, dict]:
    team = pick_team()
    tid = team["team_id"]
    fin = lib.pbp_history.load_finals(LEAGUE, [YEAR]).filter(pl.col("status") == "ok")
    cols = lib.COLS + ["period", "secs_left"]
    ev = (pl.read_parquet(lib.pbp_history.events_path(LEAGUE, YEAR), columns=cols)
            .join(fin.select("gameId"), on="gameId", how="semi"))
    shots = lib.resolve_passers(ev)
    gc = lib.game_concentration(shots).filter(pl.col("teamId") == tid)
    ok = shots.filter(~pl.col("assisted") | pl.col("resolved")).with_columns(
        creator=pl.when(pl.col("assisted")).then(pl.col("passer")).otherwise(pl.col("personId")))
    ncre = ok.filter(pl.col("teamId") == tid).group_by("gameId").agg(
        n_creators=pl.col("creator").n_unique())
    target = (pl.read_csv(OUT / "team_shots.csv")
                .filter((pl.col("league") == LEAGUE) & (pl.col("year") == YEAR)
                        & (pl.col("team_id") == tid))["game_top1_share"][0])
    pick = (gc.join(ncre, on="gameId").filter(pl.col("n_creators") <= MAX_CREATORS)
              .with_columns(dist=(pl.col("game_top1_share") - target).abs())
              .sort(["dist", "gameId"]).row(0, named=True))
    gid = pick["gameId"]
    g = fin.filter(pl.col("gameId") == gid).row(0, named=True)
    home = g["home_id"] == tid
    opp = g["abbr_a"] if home else g["abbr_h"]
    names = (ev.filter((pl.col("gameId") == gid) & (pl.col("personId") > 0))
               .with_columns(nm=pl.when(pl.col("playerNameI") != "").then(pl.col("playerNameI"))
                             .otherwise(pl.col("playerName")))
               .filter(pl.col("nm") != "")
               .group_by("personId", "nm").len()
               .sort(["personId", "len", "nm"], descending=[False, True, False])
               .group_by("personId", maintain_order=True).first()
               .select("personId", "nm"))
    nm = dict(names.iter_rows())
    mine = ok.filter((pl.col("gameId") == gid) & (pl.col("teamId") == tid))
    game = (mine.group_by("creator")
                .agg(own=pl.col("points").filter(~pl.col("assisted")).sum(),
                     passed=pl.col("points").filter(pl.col("assisted")).sum())
                .with_columns(created=pl.col("own") + pl.col("passed"))
                .sort(["created", "creator"], descending=[True, False])
                .with_columns(name=pl.col("creator").replace_strict(nm, default=None),
                              league=pl.lit(LEAGUE), season=pl.lit(team["season"]),
                              gameId=pl.lit(gid), game_date=pl.lit(str(g["game_date"])),
                              team=pl.lit(team["team"]), opponent=pl.lit(opp),
                              home=pl.lit(home))
                .select("league", "season", "gameId", "game_date", "team", "opponent", "home",
                        "creator", "name", "own", "passed", "created"))
    allm = shots.filter((pl.col("gameId") == gid) & (pl.col("teamId") == tid)).join(
        ev.select("gameId", "seq", "period", "secs_left", "description"), on=["gameId", "seq"])
    a3 = allm.filter(pl.col("assisted") & pl.col("resolved") & (pl.col("points") == 3)).sort("seq").row(0, named=True)
    u2 = allm.filter(~pl.col("assisted") & (pl.col("points") == 2)).sort("seq").row(0, named=True)
    plays = pl.DataFrame([
        {"kind": "assisted", "seq": a3["seq"], "period": a3["period"],
         "description": a3["description"], "points": a3["points"],
         "shooter": nm[a3["personId"]], "passer": nm[a3["passer"]], "credited": nm[a3["passer"]]},
        {"kind": "unassisted", "seq": u2["seq"], "period": u2["period"],
         "description": u2["description"], "points": u2["points"],
         "shooter": nm[u2["personId"]], "passer": None, "credited": nm[u2["personId"]]},
    ], schema={"kind": pl.Utf8, "seq": pl.Int64, "period": pl.Int64, "description": pl.Utf8,
               "points": pl.Int64, "shooter": pl.Utf8, "passer": pl.Utf8, "credited": pl.Utf8})
    return game, plays, pick


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    game, plays, pick = build()
    c = lib.concentration(game["created"].cast(pl.Float64).to_list())
    fails = []
    if not (math.isclose(c["top1_share"], pick["game_top1_share"], abs_tol=1e-12)
            and math.isclose(c["eff_creators"], pick["game_eff_creators"], abs_tol=1e-12)):
        fails.append("extract disagrees with lib.game_concentration on the raw events")
    if game["name"].is_null().any():
        fails.append("a creator in the example game has no display name")
    if args.check:
        if not lib.frames_match(game, pl.read_csv(GAME, schema_overrides=game.schema)):
            fails.append("example_game.csv differs from a fresh build")
        if not lib.frames_match(plays, pl.read_csv(PLAYS, schema_overrides=plays.schema)):
            fails.append("example_plays.csv differs from a fresh build")
        for f in fails:
            print("FAIL", f)
        print("EXAMPLE", "FAILED" if fails else
              f"PASSED: {game['team'][0]} vs {game['opponent'][0]} {game['game_date'][0]}, "
              f"{game.height} creators, matches lib.game_concentration")
        return 1 if fails else 0
    for f in fails:
        print("FAIL", f)
    if fails:
        return 1
    game.write_csv(GAME)
    plays.write_csv(PLAYS)
    print(game)
    print(plays)
    print(c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
