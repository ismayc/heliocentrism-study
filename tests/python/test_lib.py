"""python/lib.py against hand-built fixtures. tests/R/test_functions.R
asserts the same results for R/functions.R."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import polars as pl
import pytest
from scipy import stats

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def lib():
    spec = importlib.util.spec_from_file_location("helio_lib", REPO / "python" / "lib.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["helio_lib"] = mod
    spec.loader.exec_module(mod)
    return mod


def events():
    """One game, team 1. Players: 10 Longley, 11 and 12 both Wagner
    (playerNameI F. Wagner and M. Wagner), 13 Johnson whose plays read
    "Ar. Johnson", 14 Jordan. Team 2 has its own Longley (20)."""
    rows = [
        # seq, team, person, playerName, playerNameI, actionType, description, shotValue
        (1, 1, 14, "Jordan", "M. Jordan", "Made Shot", "Jordan 2' Layup (2 PTS) (Longley 1 AST)", 2),
        (2, 1, 10, "Longley", "L. Longley", "Made Shot", "Longley 8' Hook Shot (2 PTS) (F. Wagner 1 AST)", 2),
        (3, 1, 11, "Wagner", "F. Wagner", "Missed Shot", "MISS Wagner 20' Jump Shot", 0),
        (4, 1, 12, "Wagner", "M. Wagner", "Rebound", "Wagner REBOUND (Off:0 Def:1)", 0),
        (5, 1, 13, "Johnson", "A. Johnson", "Missed Shot", "MISS Ar. Johnson 3PT Jump Shot", 0),
        (6, 1, 14, "Jordan", "M. Jordan", "Made Shot", "Jordan 25' 3PT Jump Shot (5 PTS) (Ar. Johnson 1 AST)", 3),
        (7, 1, 14, "Jordan", "M. Jordan", "Made Shot", "Jordan 15' Jump Shot (7 PTS)", 2),
        (8, 1, 14, "Jordan", "M. Jordan", "Made Shot", "Jordan Dunk (9 PTS) (Nobody 1 AST)", 2),
        (9, 2, 20, "Longley", "X. Longley", "Made Shot", "Longley Layup (2 PTS)", 2),
        # A three whose shotValue is missing: the description decides.
        (10, 1, 10, "Longley", "L. Longley", "Made Shot", "Longley 24' 3PT Jump Shot (5 PTS) (Jordan 1 AST)", 0),
    ]
    return pl.DataFrame(
        [{"gameId": "g", "seq": s, "teamId": t, "personId": p, "playerName": n, "playerNameI": ni,
          "actionType": a, "description": d, "shotValue": v} for s, t, p, n, ni, a, d, v in rows],
        schema={"gameId": pl.Utf8, "seq": pl.Int32, "teamId": pl.Int64, "personId": pl.Int64,
                "playerName": pl.Utf8, "playerNameI": pl.Utf8, "actionType": pl.Utf8,
                "description": pl.Utf8, "shotValue": pl.Int32})


def test_resolve_passers_three_passes(lib):
    out = lib.resolve_passers(events()).sort("seq")
    got = dict(zip(out["seq"].to_list(), out["passer"].to_list()))
    # pass 1 (playerName; team 2's Longley is not a candidate), pass 2
    # (playerNameI), pass 3 (description prefix), unassisted, unresolvable.
    assert got == {1: 10, 2: 11, 6: 13, 7: None, 8: None, 9: None, 10: 14}
    assert dict(zip(out["seq"], out["points"])) == {1: 2, 2: 2, 6: 3, 7: 2, 8: 2, 9: 2, 10: 3}
    assert out.filter(pl.col("seq") == 8)["resolved"].to_list() == [False]


def test_creator_table_credits_passers_and_drops_unresolved(lib):
    cr = lib.creator_table(lib.resolve_passers(events()))
    got = {(t, c): v for t, c, v in cr.select("teamId", "creator", "created").rows()}
    # Credited: seq 1 -> 10 (2), seq 2 -> 11 (2), seq 6 -> 13 (3), seq 7 and
    # seq 10 -> 14 (2 + 3); seq 8 is dropped; team 2: seq 9 -> 20 (2).
    assert got == {(1, 10): 2, (1, 11): 2, (1, 13): 3, (1, 14): 5, (2, 20): 2}


def test_game_concentration(lib):
    g = lib.game_concentration(lib.resolve_passers(events())).sort("teamId")
    t1 = g.row(0, named=True)
    shares = [5 / 12, 3 / 12, 2 / 12, 2 / 12]
    assert t1["game_top1_share"] == pytest.approx(5 / 12)
    assert t1["game_top2_share"] == pytest.approx(8 / 12)
    assert t1["game_eff_creators"] == pytest.approx(1 / sum(s * s for s in shares))
    assert g.row(1, named=True)["game_eff_creators"] == pytest.approx(1.0)


def test_concentration(lib):
    c = lib.concentration([50, 30, 20])
    assert c["top1_share"] == pytest.approx(0.5)
    assert c["top2_share"] == pytest.approx(0.8)
    assert c["eff_creators"] == pytest.approx(1 / (0.25 + 0.09 + 0.04))
    assert lib.concentration([7])["top2_share"] == pytest.approx(1.0)


def test_mean_ci_and_welch_match_scipy(lib):
    x, y = [1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 9.0, 1.0]
    m, lo, hi = lib.mean_ci(x)
    ci = stats.t.interval(0.95, 3, loc=2.5, scale=stats.sem(x))
    assert (m, lo, hi) == pytest.approx((2.5, *ci))
    d, dlo, dhi = lib.welch(x, y)
    ref = stats.ttest_ind(x, y, equal_var=False).confidence_interval(0.95)
    assert (d, dlo, dhi) == pytest.approx((2.5 - 4.4, ref.low, ref.high))


def test_hinge_finds_an_exact_kink(lib):
    t = list(range(2000, 2012))
    y = [1.0 + 0.1 * (v - 2000) + (0.5 * (v - 2006) if v > 2006 else 0.0) for v in t]
    prof = lib.hinge_profile([float(v) for v in t], y)
    k, lo, hi = lib.break_set(prof, len(t))
    assert k == 2006 and lo == 2006 and hi == 2006
    assert min(s for _, s in prof) == pytest.approx(0.0, abs=1e-18)


def test_frames_match_tolerates_noise_but_not_differences(lib):
    a = pl.DataFrame({"k": ["x", "y"], "n": [1, 2], "v": [0.5, 0.25]})
    assert lib.frames_match(a, a.with_columns(pl.col("v") + 1e-13))
    assert not lib.frames_match(a, a.with_columns(pl.col("v") + 1e-6))
    assert not lib.frames_match(a, a.with_columns(pl.col("n") + 1))
    assert not lib.frames_match(a, a.with_columns(pl.lit("z").alias("k")))
    assert not lib.frames_match(a, a.head(1))
    assert not lib.frames_match(a, a.with_columns(pl.lit(None, pl.Float64).alias("v")))
