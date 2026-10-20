"""Figures, from committed and R-reconciled outputs only (league_seasons.csv,
league_gap.csv). Plotly originals go to figures/; report_builder.py swaps in
the family's famplot engine at publish time, so only traces famplot draws are
used (scatter lines and markers, error bars, horizontal reference lines).

Figures:
  fig1_game_top1_py      the top creator's share of a team's created points
                         per game, league mean by season with 95% intervals
  fig2_league_gap_py     NBA minus WNBA on the same measure, by season, with
                         95% Welch intervals
  fig3_assisted_share_py share of made field goals that were assisted

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
LIGHT = {"nba": "#8db8ea", "wnba": "#f3a77f"}
GREY = "#898781"


def base_layout(title: str, xtitle: str, ytitle: str, height: int = 420) -> dict:
    return dict(title=title, xaxis_title=xtitle, yaxis_title=ytitle, template="plotly_white",
                height=height, margin=dict(l=70, r=30, t=60, b=60),
                legend=dict(orientation="h", y=-0.2))


def by_season(ls: pl.DataFrame, metric: str, title: str, ytitle: str, scale: float = 100) -> go.Figure:
    f = go.Figure()
    for lg, name in LEAGUES.items():
        r = ls.filter((pl.col("league") == lg) & (pl.col("metric") == metric)).sort("year")
        y = (r["mean"] * scale).to_list()
        f.add_trace(go.Scatter(
            x=r["year"].to_list(), y=y, mode="lines+markers", name=name,
            line=dict(color=COLORS[lg]), marker=dict(size=8, color=COLORS[lg]),
            error_y=dict(type="data", symmetric=False,
                         array=[(h - m) * scale for h, m in zip(r["hi"], r["mean"])],
                         arrayminus=[(m - lo) * scale for m, lo in zip(r["mean"], r["lo"])],
                         color=LIGHT[lg]),
            customdata=list(zip(r["season"].to_list(), r["teams"].to_list())),
            hovertemplate=f"{name} %{{customdata[0]}}: %{{y:.1f}} "
                          "(%{customdata[1]} teams)<extra></extra>"))
    f.update_layout(**base_layout(title, "Season (starting year)", ytitle))
    return f


def fig_gap(gap: pl.DataFrame) -> go.Figure:
    r = gap.filter(pl.col("metric") == "game_top1_share").sort("wnba_year")
    f = go.Figure()
    f.add_trace(go.Scatter(
        x=r["wnba_year"].to_list(), y=(r["gap"] * 100).to_list(), mode="lines+markers",
        name="NBA minus WNBA", line=dict(color=GREY), marker=dict(size=8, color=GREY),
        error_y=dict(type="data", symmetric=False,
                     array=[(h - g) * 100 for h, g in zip(r["hi"], r["gap"])],
                     arrayminus=[(g - lo) * 100 for g, lo in zip(r["gap"], r["lo"])],
                     color="#c3c1bb"),
        customdata=r["nba_season"].to_list(),
        hovertemplate="WNBA %{x} vs NBA %{customdata}: %{y:+.1f} points<extra></extra>"))
    f.add_hline(y=0, line=dict(color="#b5b3ad", width=1))
    f.update_layout(**base_layout(
        "Top-creator share per game, NBA minus WNBA (95% Welch intervals)",
        "WNBA season (NBA season ending that year)",
        "NBA minus WNBA (points)"))
    f.update_layout(showlegend=False)
    return f


def main() -> None:
    FIG.mkdir(exist_ok=True)
    ls = pl.read_csv(OUT / "league_seasons.csv")
    gap = pl.read_csv(OUT / "league_gap.csv")
    figs = [
        ("fig1_game_top1_py", by_season(
            ls, "game_top1_share", "How much of a team's scoring one player creates, per game (95% intervals)",
            "Top creator's share (%)")),
        ("fig2_league_gap_py", fig_gap(gap)),
        ("fig3_assisted_share_py", by_season(
            ls, "assisted_share", "Share of made field goals that were assisted (95% intervals)",
            "Assisted share (%)")),
    ]
    for name, fig in figs:
        fig.write_html(FIG / f"{name}.html", include_plotlyjs="cdn", full_html=True)
        fig.write_image(FIG / f"{name}.png", width=900, height=fig.layout.height or 420, scale=2)
        print("wrote", name)


if __name__ == "__main__":
    main()
