# Heliocentrism study

How concentrated is shot creation on NBA (1996-97 to 2025-26) and WNBA (1997
to 2026) teams, and how has it changed? Personal research in the
basketball-data-science family (backlog: `../hub/ideas/historical-analysis-ideas.md`,
Round 2 #4). Decisions and their dates: `docs/design.md`. Public repo with
Pages from main:/docs; findings live in the memory dir, not `docs/findings/`.

## Data context

- **Source:** the shared PlayByPlayV3 layer,
  `../basketball-analysis-tools/pbp_history.py`; prepared events and finals
  checks under `../.pbp-archive/events/`. Only finals status `ok` games.
- **Grain:** creation events: one made field goal (`gameId`, `seq`). Outputs:
  team-season (`league`, `year`, `team_id`) and player-team-season
  (`creator` = personId).
- **Keys:** `gameId` 10-character text; archive years are season start years.
- **Definitions:** in `python/lib.py` and its R twin `R/functions.R`.
- **Known issues:** passers are named by display text, not ID (three-pass
  resolver); WNBA 1997-98 team assists differ from LeagueGameLog in 6-8% of
  team-games; three creators have no display name (named "id <personId>").
- **Sources of truth:** LeagueGameLog AST and FGM per team-game.
- **Suspicious results:** a season resolving under 99.5% of passers, a top
  creator share over 50%, or a team-season with fewer than 10 creators means
  stop and check.

Data sources and licenses: `DATA_SOURCES.md`. Raw rows stay local.

## How work is done here

- Family layout: `python/NN_*.py`, `python/lib.py` with its R twin,
  `R/heliocentrism.R` for the full R pipeline, tests in both languages on
  shared fixtures, `output/` committed, `run_checks.sh` as the gate. Python
  uses polars and plotly; the shared venv is `../.venv`.
- Python and R agree on every reconciled cell within 1e-9, so methods are
  deterministic (t and Welch intervals, closed-form hinge fits). No
  bootstrap.
- In R `summarise()`, never reuse a column name as an aggregate before a
  later argument reads the column (it bit `unresolved` here).
- README results are generated (`python/05_report.py`); never type a number
  into them.
- **Plan mode first** for any step that drops games, changes the crediting
  rule, or joins tables. Label anything not checked against data as
  unverified.
