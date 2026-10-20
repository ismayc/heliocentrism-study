"""Story charts, from committed and R-reconciled outputs only
(league_seasons.csv, league_gap.csv, era_change.csv, team_seasons.csv).
Plotly originals go to figures/; report_builder.py swaps in the family's
famplot engine at publish time, so only what famplot draws is used: scatter
lines, markers, and bands (fill "tonexty"), horizontal and vertical line
shapes, and text annotations. Every number in a title, legend entry, or
annotation is read from those tables here, never typed.

Phones: famplot scales a chart's height with the column (to about 300px at
phone width), so titles stay short, the numbers the chart makes its point
with go in legend entries rather than long in-plot labels, and in-plot text
is a few words.

Figures:
  fig1_game_top1_py      the top creator's share of a team's created points
                         per game, league mean by season with a 95% band, and
                         the NBA's first-five and last-five season means
  fig2_league_gap_py     NBA minus WNBA on the same measure, by season, with
                         a 95% Welch band; seasons whose interval excludes
                         zero are colored by the league that was higher
  fig3_assisted_share_py share of made field goals that were assisted
  fig4_season_vs_game_py the NBA's top-creator share two ways: per game and
                         on season totals
  fig5_team_spread_py    every team-season's top-creator share on season
                         totals, with the league means and the named
                         outlier teams

Run:  python python/04_figures.py
"""
from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
FIG = ROOT / "figures"
LEAGUES = {"nba": "NBA", "wnba": "WNBA"}
COLORS = {"nba": "#2a78d6", "wnba": "#eb6834"}
BAND = {"nba": "rgba(42,120,214,0.13)", "wnba": "rgba(235,104,52,0.13)"}
CLOUD = {"nba": "rgba(42,120,214,0.5)", "wnba": "rgba(235,104,52,0.5)"}
GREY = "#898781"
GREY_BAND = "rgba(137,135,129,0.20)"
INK = "#52514e"
HEIGHT = 600
# The outlier teams the story names, by (league, season, top creator): text
# keys; their numbers are read from team_seasons.csv. The last element is
# where the label sits, in chart units: None puts it beside the dot, a value
# lifts it to that height with a vertical leader line down to the dot (so the
# 2020-2024 cluster's labels stack instead of colliding). Positions only.
NAMED = [("nba", "2008-09", "C. Paul", None, "right"),
         ("nba", "2016-17", "R. Westbrook", 52, "right"),
         ("wnba", "2020", "C. Vandersloot", 58, "right"),
         ("nba", "2021-22", "T. Young", 54, "left"),
         ("nba", "2023-24", "L. Doncic", 50, "left"),
         ("wnba", "2024", "C. Clark", 46, "left")]
Y5_RANGE = [5, 61]


def pct(v: float, d: int = 1) -> str:
    return f"{v * 100:.{d}f}%"


def pts(v: float, d: int = 1) -> str:
    return f"{v * 100:+.{d}f}"


def base_layout(title: str, xtitle: str, ytitle: str, height: int = HEIGHT) -> dict:
    return dict(title=dict(text=title), xaxis_title=xtitle, yaxis_title=ytitle,
                template="plotly_white", height=height,
                margin=dict(l=70, r=30, t=80, b=60),
                legend=dict(orientation="h", y=-0.2))


def band(f: go.Figure, x, lo, hi, fill: str, scale: float = 100) -> None:
    """A 95% band: the lower bound, then the upper bound filled to it."""
    f.add_trace(go.Scatter(x=x, y=[v * scale for v in lo], mode="lines",
                           line=dict(width=0, color=fill), showlegend=False,
                           hoverinfo="skip"))
    f.add_trace(go.Scatter(x=x, y=[v * scale for v in hi], mode="lines",
                           line=dict(width=0, color=fill), fill="tonexty",
                           fillcolor=fill, showlegend=False, hoverinfo="skip"))


def league_series(f: go.Figure, ls: pl.DataFrame, lg: str, metric: str, name: str,
                  color: str, fill: str, dash: str | None = None,
                  label: str | None = None) -> pl.DataFrame:
    r = ls.filter((pl.col("league") == lg) & (pl.col("metric") == metric)).sort("year")
    x = r["year"].to_list()
    band(f, x, r["lo"].to_list(), r["hi"].to_list(), fill)
    f.add_trace(go.Scatter(
        x=x, y=(r["mean"] * 100).to_list(), mode="lines+markers", name=label or name,
        line=dict(color=color, width=2, dash=dash), marker=dict(size=5, color=color),
        customdata=list(zip(r["season"].to_list(), r["teams"].to_list(),
                            (r["lo"] * 100).to_list(), (r["hi"] * 100).to_list())),
        hovertemplate=f"{name} %{{customdata[0]}}: %{{y:.1f}}% "
                      "(95% %{customdata[2]:.1f} to %{customdata[3]:.1f}; "
                      "%{customdata[1]} teams)<extra></extra>"))
    return r


def era_row(era: pl.DataFrame, lg: str, metric: str) -> dict:
    return era.filter((pl.col("league") == lg) & (pl.col("metric") == metric)).row(0, named=True)


def fig_game_top1(ls: pl.DataFrame, era: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    rows = {}
    for lg, name in LEAGUES.items():
        e = era_row(era, lg, "game_top1_share")
        rows[lg] = league_series(f, ls, lg, "game_top1_share", name, COLORS[lg], BAND[lg],
                                 label=f"{name} ({pts(e['change'])} points)")
    e = era_row(era, "nba", "game_top1_share")
    yr = dict(zip(rows["nba"]["season"].to_list(), rows["nba"]["year"].to_list()))
    for k, (lab, mean) in enumerate(((e["first"], e["first_mean"]),
                                     (e["last"], e["last_mean"]))):
        span = [yr[s] for s in lab.split(" to ")]
        f.add_trace(go.Scatter(
            x=span, y=[mean * 100] * 2, mode="lines", showlegend=k == 0,
            name=f"NBA first and last five seasons ({pct(e['first_mean'])} to "
                 f"{pct(e['last_mean'])})",
            line=dict(color=INK, width=2.5, dash="dash"),
            hovertemplate=f"NBA {lab}: {pct(mean)}<extra></extra>"))
    f.update_layout(**base_layout(
        "NBA top creators carry slightly less of each game; the WNBA's have not measurably changed"
        "<br>Top creator's share per game, league mean with 95% band; legend: "
        "first five seasons to last five",
        "Season (starting year)", "Top creator's share (%)"))
    return f


def fig_gap(gap: pl.DataFrame) -> go.Figure:
    r = gap.filter(pl.col("metric") == "game_top1_share").sort("wnba_year")
    x = r["wnba_year"].to_list()
    f = go.Figure()
    band(f, x, r["lo"].to_list(), r["hi"].to_list(), GREY_BAND)
    f.add_trace(go.Scatter(x=x, y=(r["gap"] * 100).to_list(), mode="lines",
                           line=dict(color=GREY, width=1.5), showlegend=False,
                           hoverinfo="skip"))
    nba_hi = r.filter(pl.col("lo") > 0)
    wnba_hi = r.filter(pl.col("hi") < 0)
    neither = r.filter((pl.col("lo") <= 0) & (pl.col("hi") >= 0))
    for sub, name, color in (
            (nba_hi, f"NBA higher ({nba_hi.height})", COLORS["nba"]),
            (wnba_hi, f"WNBA higher ({wnba_hi.height})", COLORS["wnba"]),
            (neither, f"Cannot tell apart ({neither.height})", GREY)):
        f.add_trace(go.Scatter(
            x=sub["wnba_year"].to_list(), y=(sub["gap"] * 100).to_list(), mode="markers",
            name=name, marker=dict(size=9, color=color),
            customdata=list(zip(sub["nba_season"].to_list(), (sub["lo"] * 100).to_list(),
                                (sub["hi"] * 100).to_list())),
            hovertemplate="WNBA %{x} vs NBA %{customdata[0]}: %{y:+.1f} points "
                          "(95% %{customdata[1]:+.1f} to %{customdata[2]:+.1f})<extra></extra>"))
    f.add_hline(y=0, line=dict(color="#b5b3ad", width=1))
    w = wnba_hi.sort("wnba_year").row(-1, named=True)
    ann = [dict(x=w["wnba_year"], y=w["gap"] * 100, xanchor="right", yanchor="middle",
                xshift=-8, showarrow=False, font=dict(size=12, color=COLORS["wnba"]),
                text=f"{w['wnba_year']}: {pts(w['gap'])}"),
           dict(x=0, y=1, xref="paper", yref="paper", xanchor="left", yanchor="top",
                showarrow=False, font=dict(size=12, color=INK),
                text="Above zero: NBA more concentrated")]
    f.update_layout(**base_layout(
        f"Only in {w['wnba_year']} was the WNBA clearly the more concentrated league"
        "<br>Top creator's share per game, NBA minus WNBA, with 95% Welch band; "
        "legend counts seasons",
        "WNBA season (NBA season ending that year)", "NBA minus WNBA (points)"))
    f.update_layout(annotations=ann)
    return f


def fig_assisted(ls: pl.DataFrame, era: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    for lg, name in LEAGUES.items():
        e = era_row(era, lg, "assisted_share")
        league_series(f, ls, lg, "assisted_share", name, COLORS[lg], BAND[lg],
                      label=f"{name} ({pts(e['change'])} points)")
    f.update_layout(**base_layout(
        "Both leagues assist more of their baskets, the WNBA by more"
        "<br>Share of made field goals assisted, league mean with 95% band; legend: "
        "first five seasons to last five",
        "Season (starting year)", "Assisted share (%)"))
    return f


def fig_season_vs_game(ls: pl.DataFrame, era: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    eg, es = era_row(era, "nba", "game_top1_share"), era_row(era, "nba", "top1_share")
    league_series(f, ls, "nba", "game_top1_share", "Per game", COLORS["nba"], BAND["nba"],
                  label=f"Per game ({pts(eg['change'])} points)")
    league_series(f, ls, "nba", "top1_share", "Season totals", GREY, GREY_BAND, dash="dot",
                  label=f"Season totals ({pts(es['change'])} points)")
    f.update_layout(**base_layout(
        "Season totals make the NBA's fall look far larger than it is per game"
        "<br>NBA top creator's share, league mean with 95% band; legend: first five "
        "seasons to last five",
        "Season (starting year)", "Top creator's share (%)"))
    return f


def fig_team_spread(ts: pl.DataFrame, ls: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    off = {"nba": -0.2, "wnba": 0.2}
    for lg, name in LEAGUES.items():
        r = ts.filter(pl.col("league") == lg).sort("year", "team_id")
        f.add_trace(go.Scatter(
            x=[y + off[lg] for y in r["year"].to_list()], y=(r["top1_share"] * 100).to_list(),
            mode="markers", name=name, marker=dict(size=5, color=CLOUD[lg]),
            customdata=list(zip(r["season"].to_list(), r["team"].to_list(),
                                r["top_creator"].to_list())),
            hovertemplate="%{customdata[1]} %{customdata[0]}: %{customdata[2]} "
                          "%{y:.1f}%<extra></extra>"))
    for lg, name in LEAGUES.items():
        m = ls.filter((pl.col("league") == lg) & (pl.col("metric") == "top1_share")).sort("year")
        f.add_trace(go.Scatter(
            x=m["year"].to_list(), y=(m["mean"] * 100).to_list(), mode="lines",
            name=f"{name} mean", showlegend=False, line=dict(color=COLORS[lg], width=2.5),
            customdata=m["season"].to_list(),
            hovertemplate=f"{name} mean %{{customdata}}: %{{y:.1f}}%<extra></extra>"))
    hx, hy, hcd, ann, shapes = [], [], [], [], []
    for lg, season, who, label_y, side in NAMED:
        row = ts.filter((pl.col("league") == lg) & (pl.col("season") == season)
                        & (pl.col("top_creator") == who)).row(0, named=True)
        x, y = row["year"] + off[lg], row["top1_share"] * 100
        hx.append(x)
        hy.append(y)
        hcd.append([row["season"], row["team"], who])
        if label_y is not None:
            shapes.append(dict(type="line", x0=x, x1=x, y0=y + 0.8, y1=label_y - 0.3,
                               line=dict(color=INK, width=1)))
        ann.append(dict(x=x, y=y if label_y is None else label_y, xanchor=side,
                        yanchor="middle" if label_y is None else "bottom",
                        xshift=(-7 if side == "right" else 7) if label_y is None else 0,
                        showarrow=False, font=dict(size=12, color=INK),
                        text=who.split(". ", 1)[1]))
    f.add_trace(go.Scatter(
        x=hx, y=hy, mode="markers", name="Named in the story", showlegend=False,
        marker=dict(size=9, color=INK),
        customdata=hcd, hovertemplate="%{customdata[1]} %{customdata[0]}: %{customdata[2]} "
                                      "%{y:.1f}%<extra></extra>"))
    f.update_layout(**base_layout(
        "Heliocentric teams stand out in every era; the league average never followed"
        "<br>Each dot is a team-season's top creator share on season totals; "
        "lines are league means",
        "Season (starting year)", "Top creator's share (%)", height=640))
    f.update_layout(annotations=ann, shapes=shapes, yaxis=dict(range=Y5_RANGE))
    return f


def main() -> None:
    FIG.mkdir(exist_ok=True)
    ls = pl.read_csv(OUT / "league_seasons.csv")
    gap = pl.read_csv(OUT / "league_gap.csv")
    era = pl.read_csv(OUT / "era_change.csv")
    ts = pl.read_csv(OUT / "team_seasons.csv")
    figs = [
        ("fig1_game_top1_py", fig_game_top1(ls, era)),
        ("fig2_league_gap_py", fig_gap(gap)),
        ("fig3_assisted_share_py", fig_assisted(ls, era)),
        ("fig4_season_vs_game_py", fig_season_vs_game(ls, era)),
        ("fig5_team_spread_py", fig_team_spread(ts, ls)),
    ]
    for name, fig in figs:
        fig.write_html(FIG / f"{name}.html", include_plotlyjs="cdn", full_html=True)
        fig.write_image(FIG / f"{name}.png", width=900, height=fig.layout.height or 420, scale=2)
        print("wrote", name)


if __name__ == "__main__":
    main()
