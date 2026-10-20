# Design

## Question

Did NBA offenses become solar systems, one star creating most of the scoring,
and when? Did the WNBA stay more egalitarian? From the backlog idea "The
heliocentrism index" (`../hub/ideas/historical-analysis-ideas.md`, Round 2 #4).

## Decisions

Made by Chester Ismay on October 19, 2026, before any result was computed:

1. **Its own private repo**, one of three studies built on the shared
   PlayByPlayV3 layer.
2. **Full history**: NBA 1996-97 to 2025-26, WNBA 1997 to 2026, regular
   season.

Made while building (October 19, 2026), each for the reason given:

3. **Creation, not shot attempts.** A made field goal's creator is the passer
   when it was assisted, otherwise the shooter, weighted by the shot's points.
   This uses the passer-scorer pair the backlog idea names, and it is the one
   thing the play-by-play records about who set up a basket.
4. **Per-game metrics are primary.** The first season-level pass showed the
   NBA's top-creator share falling by about 4 points; a star who misses games
   lowers a season share even if the offense runs through them every night
   they play. Per-game concentration, averaged over a team's games, removes
   that. Both are reported; the per-game fall is a quarter the size.
5. **1 / HHI for the effective number of creators**, not exp(entropy): it
   weighs the large shares, so a bench player with two assists barely moves
   it.
6. **Era comparison: the first five seasons against the last five**, the same
   blocks the safe-lead study uses, chosen before results. Hinge fits date the
   turn; their break-year sets are approximate (an F-based profile set) and
   reported as such.

## Data checks

- Passers are resolved within the shooter's team in the same game, never to
  the shooter, in three passes (playerName, playerNameI, then the text that
  begins the player's own play descriptions), each accepted only when it
  finds one player. Resolution is at least 99.85% in every season.
- Parsed team assists are compared with LeagueGameLog's AST for every
  team-game, and made field goals with FGM (`output/validation.csv`). WNBA
  1997 and 1998 match in 92% and 94% of team-games (the gamelog or the feed
  differs by an assist or two); every other season matches in at least 99.7%.
- Games come only from the shared layer's finals status `ok` (see
  `../safe-lead-study/docs/findings/score-stamp-jumps.md` for the score-jump
  check behind that status).
