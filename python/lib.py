"""Shared definitions for the heliocentrism study. Every function here has a
twin in R/functions.R, pinned to the same fixtures in tests/python and
tests/R.

Creation
--------
Every made field goal is credited to one creator: the passer named in its
"(Name N AST)" suffix when it was assisted, otherwise the shooter. Points
created are the shot's value (2 or 3; the archive's shotValue, or 3 when the
description says 3PT). Free throws are not created by anyone here, since the
feed records no assist on them.

Passer resolution
-----------------
The passer is named by display text, not ID. It is resolved within the
shooter's team in the same game, never to the shooter, in three passes; a
pass is used only when it finds exactly one player:
  1. text equals a player's playerName ("Longley");
  2. text equals a player's playerNameI ("F. Wagner", when two Wagners play);
  3. a player's own play descriptions start with the text and a space
     ("Ar. Johnson", "Diabaté", forms neither name column holds).
Assists still unresolved are left out of creator shares and counted.

Concentration metrics (points created, so a three weighs 3)
------------------------------------------------------------
  top1_share     the top creator's share of the team's created points
  top2_share     the top two creators' combined share
  eff_creators   1 / sum(share^2): the number of equal creators that would
                 give the same concentration
  assisted_share assisted made field goals / all made field goals

Each is computed two ways. Game level (primary, prefix game_): within each
team-game, then averaged over the team's games, so a star's missed games do
not dilute it. Season level: from the team's season totals, which answers
"who carried the season" and is lower whenever stars miss games.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT.parent
sys.path.insert(0, str(FAMILY / "basketball-analysis-tools"))
import pbp_history  # noqa: E402

YEARS = {"nba": range(1996, 2026), "wnba": range(1997, 2027)}
AST_RE = r"\(([^()]+?) (\d+) AST\)\s*$"
COLS = ["gameId", "seq", "teamId", "personId", "playerName", "playerNameI",
        "actionType", "description", "shotValue"]


def made_shots(ev: pl.DataFrame) -> pl.DataFrame:
    """Made field goals with their value and the passer's display text."""
    m = ev.filter(pl.col("actionType") == "Made Shot")
    value = (pl.when(pl.col("shotValue").is_in([2, 3])).then(pl.col("shotValue"))
             .when(pl.col("description").str.contains("3PT")).then(pl.lit(3))
             .otherwise(pl.lit(2))).cast(pl.Int32)
    return m.select("gameId", "seq", "teamId", "personId", value.alias("points"),
                    pl.col("description").str.extract(AST_RE, 1).str.strip_chars().alias("ast_text"))


def _unique_match(cand: pl.DataFrame) -> pl.DataFrame:
    return (cand.group_by("gameId", "seq").agg(pl.col("pid").unique())
                .filter(pl.col("pid").list.len() == 1)
                .with_columns(pl.col("pid").list.first()))


def resolve_passers(ev: pl.DataFrame) -> pl.DataFrame:
    """Made shots with a passer column (personId, or null when unassisted or
    unresolved) and resolved (bool, for assisted shots)."""
    m = made_shots(ev)
    a = m.filter(pl.col("ast_text").is_not_null())
    people = ev.filter(pl.col("personId") > 0)
    done = pl.DataFrame(schema={"gameId": pl.Utf8, "seq": pl.Int32, "pid": pl.Int64})
    for col in ("playerName", "playerNameI"):
        left = a.join(done, on=["gameId", "seq"], how="anti")
        names = people.select("gameId", "teamId", pl.col("personId").alias("pid"),
                              pl.col(col).alias("ast_text")).unique()
        cand = (left.join(names, on=["gameId", "teamId", "ast_text"], how="inner")
                    .filter(pl.col("pid") != pl.col("personId")))
        done = pl.concat([done, _unique_match(cand).select("gameId", "seq", "pid")])
    left = a.join(done, on=["gameId", "seq"], how="anti")
    lead = people.select("gameId", "teamId", pl.col("personId").alias("pid"),
                         pl.col("description").str.replace(r"^MISS ", "").alias("d")).unique()
    cand = (left.join(lead, on=["gameId", "teamId"], how="inner")
                .filter(pl.col("d").str.starts_with(pl.col("ast_text") + " ")
                        & (pl.col("pid") != pl.col("personId"))))
    done = pl.concat([done, _unique_match(cand).select("gameId", "seq", "pid")])
    out = m.join(done, on=["gameId", "seq"], how="left").rename({"pid": "passer"})
    return out.with_columns(assisted=pl.col("ast_text").is_not_null(),
                            resolved=pl.col("passer").is_not_null())


def creator_table(shots: pl.DataFrame) -> pl.DataFrame:
    """Points created per (team, creator) from resolved shots: unassisted
    shots credit the shooter, assisted ones the resolved passer; assisted
    shots with no resolved passer are dropped."""
    s = shots.filter(~pl.col("assisted") | pl.col("resolved")).with_columns(
        creator=pl.when(pl.col("assisted")).then(pl.col("passer")).otherwise(pl.col("personId")))
    return (s.group_by("teamId", "creator")
             .agg(created=pl.col("points").sum(), fgm_created=pl.len())
             .sort("teamId", "creator"))


def game_concentration(shots: pl.DataFrame) -> pl.DataFrame:
    """Per team-game: game_top1_share, game_top2_share, game_eff_creators,
    from resolved shots (same crediting rule as creator_table)."""
    s = shots.filter(~pl.col("assisted") | pl.col("resolved")).with_columns(
        creator=pl.when(pl.col("assisted")).then(pl.col("passer")).otherwise(pl.col("personId")))
    g = (s.group_by("gameId", "teamId", "creator").agg(c=pl.col("points").sum())
          .with_columns(sh=pl.col("c") / pl.col("c").sum().over("gameId", "teamId")))
    g = g.sort(["gameId", "teamId", "sh"], descending=[False, False, True])
    return (g.group_by("gameId", "teamId", maintain_order=True)
             .agg(game_top1_share=pl.col("sh").first(),
                  game_top2_share=pl.col("sh").head(2).sum(),
                  game_eff_creators=1 / (pl.col("sh") ** 2).sum()))


def concentration(created: list[float]) -> dict:
    """top1_share, top2_share, eff_creators from one team's created points."""
    tot = float(sum(created))
    s = sorted((c / tot for c in created), reverse=True)
    return {"top1_share": s[0], "top2_share": s[0] + (s[1] if len(s) > 1 else 0.0),
            "eff_creators": 1.0 / sum(x * x for x in s)}


def mean_ci(x: list[float]) -> tuple[float, float, float]:
    """Mean and 95% t interval (sample sd, n - 1 df)."""
    n = len(x)
    m = sum(x) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    h = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)
    return m, m - h, m + h


def welch(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """mean(x) - mean(y) with a 95% Welch interval."""
    nx, ny = len(x), len(y)
    mx, my = sum(x) / nx, sum(y) / ny
    vx = sum((v - mx) ** 2 for v in x) / (nx - 1)
    vy = sum((v - my) ** 2 for v in y) / (ny - 1)
    se = math.sqrt(vx / nx + vy / ny)
    df = (vx / nx + vy / ny) ** 2 / ((vx / nx) ** 2 / (nx - 1) + (vy / ny) ** 2 / (ny - 1))
    h = stats.t.ppf(0.975, df) * se
    return mx - my, mx - my - h, mx - my + h


def hinge_profile(t: list[float], y: list[float], min_side: int = 3) -> list[tuple[float, float]]:
    """SSE of y = a + b t + c max(0, t - k) for each candidate break k, the
    observed t values with at least min_side points on each side."""
    T = np.asarray(t, float)
    Y = np.asarray(y, float)
    out = []
    for k in sorted(set(t))[min_side:-min_side]:
        X = np.column_stack([np.ones_like(T), T, np.maximum(0.0, T - k)])
        beta = np.linalg.solve(X.T @ X, X.T @ Y)
        r = Y - X @ beta
        out.append((float(k), float(r @ r)))
    return out


def break_set(profile: list[tuple[float, float]], n: int) -> tuple[float, float, float]:
    """Best break and an approximate 95% set: every k whose SSE is within
    F(0.95; 1, n - 4) / (n - 4) of the minimum, in relative terms. Returns
    (best k, lowest k in the set, highest k in the set)."""
    kbest, smin = min(profile, key=lambda p: (p[1], p[0]))
    cut = smin * (1 + stats.f.ppf(0.95, 1, n - 4) / (n - 4))
    inset = [k for k, s in profile if s <= cut]
    return kbest, min(inset), max(inset)


def frames_match(new: pl.DataFrame, old: pl.DataFrame, tol: float = 1e-9) -> bool:
    """The --check comparison: same columns and rows, text and integers
    exact, floats within tol. Exact equality is not used for floats because
    polars group_by aggregates in thread order, so a rerun can move the last
    bit of a mean (seen in this study's team_shots.csv: 2 of 5 reruns)."""
    if new.columns != old.columns or new.height != old.height:
        return False
    for c in new.columns:
        a, b = new[c], old[c]
        if (a.is_null() != b.is_null()).any():
            return False
        if a.dtype.is_float() or b.dtype.is_float():
            d = (a.cast(pl.Float64) - b.cast(pl.Float64)).abs().max()
            if d is not None and d > tol:
                return False
        elif not (a.cast(pl.Utf8) == b.cast(pl.Utf8)).fill_null(True).all():
            return False
    return True
