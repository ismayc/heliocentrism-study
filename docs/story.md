# Did NBA offenses become solar systems?

"Heliocentrism" is the idea that modern NBA offenses orbit one star who
creates most of the scoring, while the WNBA stayed more egalitarian. This
study tests both halves of that idea on every regular-season game the
play-by-play covers: 35,492 NBA games from 1996-97 to 2025-26 and 6,469 WNBA
games from 1997 to 2026, with 1,838,338 assisted baskets. The short answer:
the typical NBA team spreads its scoring slightly more than it did thirty
years ago, not less; the WNBA has not changed measurably; and 2026 is the only
one of the 30 seasons compared in which the WNBA was clearly the more
concentrated league.

<div class="tiles">
<div class="tile"><div class="label">NBA top creator, per game</div>
<div class="value">31.5% to 30.5%</div>
<div class="sub">First five seasons against the last five: a change of -1.0 point (95% interval -1.9 to -0.1).</div></div>
<div class="tile"><div class="label">WNBA top creator, per game</div>
<div class="value">31.0% to 31.5%</div>
<div class="sub">A change of +0.4 points (95% interval -0.8 to +1.7): no measurable shift.</div></div>
<div class="tile"><div class="label">2026 league gap</div>
<div class="value">-3.0 points</div>
<div class="sub">NBA 2025-26 minus WNBA 2026 (95% interval -5.3 to -0.6): the WNBA's top creators carried more.</div></div>
<div class="tile"><div class="label">Season totals overstate</div>
<div class="value">-3.9 vs -1.0</div>
<div class="sub">The NBA's fall in points on season totals, against the per-game measure that removes missed games.</div></div>
</div>

<div class="eyebrow beat">The question</div>

## Crediting every basket to the player who created it

The play-by-play records one thing about who set up a basket: on an
assisted make, the passer. So every made field goal is credited to one
creator, the passer when it was assisted and the shooter when it was not,
weighted by the shot's points. For each team the study then measures the
top creator's share of the points created, the top two creators' share, and
the effective number of creators (1 divided by the sum of squared shares,
which weighs the large shares and barely moves for a bench player with two
assists).

The primary measures are computed within each game and averaged over a
team's games. That choice came from the first pass: on season totals, a star
who misses games lowers the share even if the offense runs through them
every night they play. Both versions are reported. Eras are compared by the
first five seasons against the last five, with 95% Welch intervals for the
change; season means carry 95% t intervals across teams.

{{svg:dg1_crediting|The crediting rule on a real Minnesota game from the 2025-26 season. The assisted three counts for the passer, not the shooter; the unassisted putback counts for the shooter. Adding up the game gives each player's share, the top creator's share, and the effective number of creators, and every measure in this study starts from that arithmetic.}}

Passers are matched to players by name within the shooter's team and game,
in three passes, each accepted only when it finds exactly one player. At
least 99.8% of assisted baskets resolve in every season, and 993 (0.05%)
are left out. Parsed team assists equal the league's game logs in at least
99.7% of team-games in every season except WNBA 1997 (92.1%) and WNBA 1998
(94.2%), and made field goals match in at least 99.9%. Every table was
computed in Python and again in R from the same events, and the two agree
on every cell.

<div class="eyebrow beat">The NBA</div>

## The typical NBA offense spread out slightly

Over 1996-97 to 2000-01, the average NBA team's top creator accounted for
31.5% of its created points in a game. Over 2021-22 to 2025-26 it was 30.5%,
a change of -1.0 point with a 95% interval of -1.9 to -0.1. The effective number
of creators per game rose from 5.32 to 5.53 (+0.21, interval +0.08 to
+0.34). The most recent season, 2025-26, was the least concentrated NBA
season of the 30, at 29.1% (27.8% to 30.5%).

{{fig:fig1_game_top1_py|The top creator's share of a team's created points per game, averaged across teams, with 95% bands. The dashed segments are the NBA's first-five and last-five season means. The NBA line drifts down after the late 2000s and ends at its lowest season; the WNBA line moves around a flat level.}}

A hinge fit on the season means puts the NBA's turn in 2008, but its
approximate 95% set runs from 2005 to 2022. The data date a slow drift, not
a moment when the league changed.

<div class="eyebrow beat">Season totals</div>

## Counting by season overstates the decline nearly four times over

On season totals the NBA's top creator share fell from 25.9% to 22.0%, a change
of -3.9 points (95% interval -5.3 to -2.5), and the effective number of
creators rose from 7.32 to 8.87. That reads like a league moving away from
stars. Per game, the change is -1.0 point. The difference is what a rise in
games missed by top players would produce, though games played were not
measured here, so that cause is unverified. Any usage or concentration claim
built on season totals mixes availability into it.

{{svg:dg3_missed_games|Left, an illustration with a made-up team: the star's role is the same in every game played, yet the season-total share comes out well below the per-game average, because the games the star missed count in the denominator. Right, the real NBA change from the first five seasons to the last five, measured both ways, with 95% intervals.}}

The same gap runs through every season, not only the two eras compared.

{{fig:fig4_season_vs_game_py|The NBA's top creator share by season, per game (blue) and on season totals (grey, dotted), with 95% bands. The season-total line sits lower and falls further.}}

<div class="eyebrow beat">League against league</div>

## The WNBA is now the more concentrated league

Season by season, the NBA's per-game top creator share was higher than the
WNBA's, with an interval excluding zero, in 5 of 30 seasons (WNBA years
2001, 2006, 2007, 2009, and 2016). The WNBA's was higher in one: 2026, where
the gap was -3.0 points (-5.3 to -0.6), the NBA's 29.1% against the WNBA's
32.1%. In most seasons the two leagues cannot be told apart.

{{fig:fig2_league_gap_py|NBA minus WNBA in the per-game top creator share, each WNBA season paired with the NBA season ending that year, with a 95% Welch band. Blue points are seasons where the NBA was clearly more concentrated, grey points are seasons the two leagues cannot be told apart, and the one orange point, 2026, is the season the WNBA was clearly more concentrated.}}

Both leagues assist more of their baskets than they did, which spreads
creation by how it is counted. The NBA's assisted share rose from 60.9% to
62.3% (+1.4 points, interval +0.4 to +2.3), and the WNBA's from 62.4% to
67.4% (+4.9, interval +3.5 to +6.4). Part of the NBA's per-game fall is
this counting effect, not only a change in who has the ball.

{{fig:fig3_assisted_share_py|Share of made field goals that were assisted, by season, with 95% bands. Both leagues rise, the WNBA by more. More assists spread credit away from the scorer by construction, which ties this rise to the NBA's per-game fall above.}}

<div class="eyebrow beat">The stars</div>

## Heliocentric teams exist; a heliocentric league does not

Individual team-seasons do orbit one player. On season totals, the 2008-09
Hornets ran 47.9% of their created points through Chris Paul, and the
2016-17 Thunder 46.8% through Russell Westbrook. Against their own league
and season, the standouts include Trae Young's 2021-22 Hawks (39.1%, 2.84
standard deviations above that season's teams) and Luka Doncic's 2023-24
Mavericks (37.4%, 2.62). In the WNBA, Courtney Vandersloot's 2020 Sky
(39.6%) and Caitlin Clark's 2024 Fever (39.5%) top the list. These teams are
outliers in their seasons. The league averages show the typical NBA team did
not follow them.

{{svg:dg2_two_teams|The 2008-09 Hornets beside the typical 2025-26 NBA team (Minnesota, the median of that season's top creator shares), each bar split into every player's share of the season's created points. Chris Paul's segment is nearly half the Hornets' bar; Minnesota's is about a fifth, and its credit is spread across more players.}}

Set against every team-season, those standouts sit far above their leagues
in every era, while the league means stay flat or drift down.

{{fig:fig5_team_spread_py|Every team-season's top creator share on season totals (NBA blue, WNBA orange), the two league means, and the six teams named above. Teams above the cloud appear in the late 1990s and in every decade since; the league mean never rises toward them.}}

<div class="eyebrow beat">Limits</div>

## What this does not show

An assist credits only the last pass. A drive and kick credits the player
who kicked, and the pass before it is invisible, so creation by primary ball
handlers is undercounted, and a rise in assists spreads creation by
construction. Assists are also a scorekeeper's judgment that varies by arena
and era, which this study does not adjust for. Free throws carry no assist
in the feed and are left out, so a star who draws fouls creates more than
these shares show. The study covers the regular season only, and
team-seasons from one franchise inside a five-season block are treated as
independent, so the era intervals are somewhat narrow. Passers are matched
by name text, and a confident wrong match is possible where two teammates
share it, though the matcher refuses any name that fits more than one
player.
