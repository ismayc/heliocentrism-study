"""Points created per player and team-season, with the parse checked against
LeagueGameLog, for every regular-season game whose score passes the shared
layer's checks (finals status "ok").

Checks per league-season (output/validation.csv):
  - ast_match: share of team-games whose parsed assist count equals
    LeagueGameLog's AST;
  - fgm_match: the same for made field goals against FGM;
  - resolved: share of assisted shots whose passer was resolved
    (python/lib.py).
--check fails if a season resolves under 99.5% of its passers, if a season
other than WNBA 1997 and 1998 matches LeagueGameLog's assists in under 99%
of team-games (those two are known and reported), if FGM matches in under
99% of team-games, or if either output differs from a fresh build.

Writes (committed, aggregate only):
  output/creators.csv    league, year, season, team_id, team, creator,
                         name, created, fgm_created
  output/team_shots.csv  league, year, team_id, fgm, assisted, unresolved,
                         games, and the game-level metrics averaged over the
                         team's games (game_top1_share, game_top2_share,
                         game_eff_creators)
  output/validation.csv  one row per league-season
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

CREATORS = lib.ROOT / "output" / "creators.csv"
TEAM_SHOTS = lib.ROOT / "output" / "team_shots.csv"
VALID = lib.ROOT / "output" / "validation.csv"
KNOWN_AST_GAPS = {("wnba", 1997), ("wnba", 1998)}


def season(league: str, year: int) -> tuple[pl.DataFrame, dict]:
    fin = lib.pbp_history.load_finals(league, [year]).filter(pl.col("status") == "ok")
    ev = (pl.read_parquet(lib.pbp_history.events_path(league, year), columns=lib.COLS)
            .join(fin.select("gameId"), on="gameId", how="semi"))
    shots = lib.resolve_passers(ev)
    sides = pl.concat([
        fin.select("gameId", pl.col("home_id").alias("teamId"), pl.col("abbr_h").alias("abbr"),
                   pl.col("ast_h").alias("AST"), pl.col("fgm_h").alias("FGM")),
        fin.select("gameId", pl.col("away_id").alias("teamId"), pl.col("abbr_a").alias("abbr"),
                   pl.col("ast_a").alias("AST"), pl.col("fgm_a").alias("FGM"))])
    tg = shots.group_by("gameId", "teamId").agg(ast=pl.col("assisted").sum(), fgm=pl.len())
    cmp = sides.join(tg, on=["gameId", "teamId"], how="left").with_columns(
        pl.col("ast", "fgm").fill_null(0))
    assisted = shots.filter(pl.col("assisted"))
    val = {"league": league, "year": year, "season": lib.pbp_history.season_label(league, year),
           "games": fin.height, "made": shots.height, "assisted": assisted.height,
           "unresolved": int((~assisted["resolved"]).sum()),
           "resolved": float(assisted["resolved"].mean()),
           "ast_match": float((cmp["ast"] == cmp["AST"]).mean()),
           "fgm_match": float((cmp["fgm"] == cmp["FGM"]).mean())}
    # Display names: each person's most frequent non-empty playerNameI (else
    # playerName) on this team.
    names = (ev.filter(pl.col("personId") > 0)
               .with_columns(nm=pl.when(pl.col("playerNameI") != "").then(pl.col("playerNameI"))
                             .otherwise(pl.col("playerName")))
               .filter(pl.col("nm") != "")
               .group_by("teamId", "personId", "nm").len()
               .sort(["teamId", "personId", "len", "nm"], descending=[False, False, True, False])
               .group_by("teamId", "personId", maintain_order=True).first()
               .select("teamId", pl.col("personId").alias("creator"), pl.col("nm").alias("name")))
    abbr = (sides.group_by("teamId", "abbr").len()
                 .sort(["teamId", "len", "abbr"], descending=[False, True, False])
                 .group_by("teamId", maintain_order=True).first().select("teamId", "abbr"))
    # Three creators in 1996-2026 have no display name on any row; name them
    # by ID.
    cr = (lib.creator_table(shots).join(names, on=["teamId", "creator"], how="left")
             .with_columns(name=pl.col("name").fill_null(pl.format("id {}", pl.col("creator"))))
             .join(abbr, on="teamId", how="left")
             .select(pl.lit(league).alias("league"), pl.lit(year).alias("year"),
                     pl.lit(val["season"]).alias("season"), pl.col("teamId").alias("team_id"),
                     pl.col("abbr").alias("team"), "creator", "name", "created", "fgm_created"))
    gm = (lib.game_concentration(shots).group_by("teamId")
             .agg(games=pl.len(), game_top1_share=pl.col("game_top1_share").mean(),
                  game_top2_share=pl.col("game_top2_share").mean(),
                  game_eff_creators=pl.col("game_eff_creators").mean()))
    tsh = (shots.group_by("teamId").agg(fgm=pl.len(), assisted=pl.col("assisted").sum(),
                                        unresolved=(pl.col("assisted") & ~pl.col("resolved")).sum())
                .join(gm, on="teamId")
                .select(pl.lit(league).alias("league"), pl.lit(year).alias("year"),
                        pl.col("teamId").alias("team_id"), "fgm", "assisted", "unresolved",
                        "games", "game_top1_share", "game_top2_share", "game_eff_creators"))
    return cr, tsh, val


def build() -> tuple[pl.DataFrame, pl.DataFrame]:
    crs, tss, vals = [], [], []
    for league, years in lib.YEARS.items():
        for y in years:
            c, t, v = season(league, y)
            crs.append(c)
            tss.append(t)
            vals.append(v)
    cr = pl.concat(crs).sort("league", "year", "team_id", "creator")
    ts = pl.concat(tss).sort("league", "year", "team_id").with_columns(
        pl.col("game_top1_share", "game_top2_share", "game_eff_creators").round(12))
    va = pl.DataFrame(vals).with_columns(pl.col("resolved", "ast_match", "fgm_match").round(12))
    return cr, ts, va


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cr, ts, va = build()
    fails = []
    low = va.filter(pl.col("resolved") < 0.995)
    if low.height:
        fails.append(f"passers resolved under 99.5%: {low.select('league', 'year').rows()}")
    ast = [r for r in va.filter(pl.col("ast_match") < 0.99).select("league", "year").rows()
           if r not in KNOWN_AST_GAPS]
    if ast:
        fails.append(f"assists match LeagueGameLog in under 99% of team-games: {ast}")
    fgm = va.filter(pl.col("fgm_match") < 0.99)
    if fgm.height:
        fails.append(f"made field goals match in under 99%: {fgm.select('league', 'year').rows()}")
    if args.check:
        if not lib.frames_match(cr, pl.read_csv(CREATORS, schema_overrides=cr.schema)):
            fails.append("creators.csv differs from a fresh build")
        if not lib.frames_match(ts, pl.read_csv(TEAM_SHOTS, schema_overrides=ts.schema)):
            fails.append("team_shots.csv differs from a fresh build")
        if not lib.frames_match(va, pl.read_csv(VALID, schema_overrides=va.schema)):
            fails.append("validation.csv differs from a fresh build")
        for f in fails:
            print("FAIL", f)
        print("CREATION", "FAILED" if fails else
              f"PASSED: {va['games'].sum():,} games, {va['assisted'].sum():,} assists, "
              f"{va['unresolved'].sum():,} unresolved")
        return 1 if fails else 0
    cr.write_csv(CREATORS)
    ts.write_csv(TEAM_SHOTS)
    va.write_csv(VALID)
    with pl.Config(tbl_rows=70):
        print(va.select("league", "year", "games", "assisted", "unresolved", "resolved",
                        "ast_match", "fgm_match"))
    for f in fails:
        print("WARN", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
