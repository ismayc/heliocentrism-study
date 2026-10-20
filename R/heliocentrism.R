# The whole heliocentrism pipeline in R, written from the docstrings of
# python/lib.py, 01_creation.py, and 02_metrics.py. It reads the shared
# prepared events, resolves passers itself, and writes an _r twin of every
# committed output. python/03_reconcile.py compares them cell by cell.
#
# Run from the repo root:  Rscript R/heliocentrism.R

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})
source("R/functions.R")

ARCHIVE <- Sys.getenv("PBP_ARCHIVE", "../.pbp-archive")
COLS <- c("gameId", "seq", "teamId", "personId", "playerName", "playerNameI",
          "actionType", "description", "shotValue")
METRICS <- c("game_top1_share", "game_top2_share", "game_eff_creators",
             "top1_share", "top2_share", "eff_creators", "assisted_share")

one_season <- function(league, year) {
  fin <- read_csv(file.path(ARCHIVE, "events", sprintf("%s_%d_rs_finals.csv", league, year)),
                  col_types = cols(gameId = col_character(), abbr_h = col_character(),
                                   abbr_a = col_character(), status = col_character(),
                                   game_date = col_character(), .default = col_double()),
                  progress = FALSE) |>
    filter(status == "ok")
  ev <- nanoparquet::read_parquet(file.path(ARCHIVE, "events", sprintf("%s_%d_rs.parquet", league, year)),
                                  col_select = COLS) |>
    filter(gameId %in% fin$gameId)
  shots <- resolve_passers(ev)
  sides <- bind_rows(
    fin |> transmute(gameId, teamId = home_id, abbr = abbr_h, AST = ast_h, FGM = fgm_h),
    fin |> transmute(gameId, teamId = away_id, abbr = abbr_a, AST = ast_a, FGM = fgm_a))
  tg <- shots |> group_by(gameId, teamId) |> summarise(ast = sum(assisted), fgm = n(), .groups = "drop")
  cmp <- sides |> left_join(tg, by = c("gameId", "teamId")) |>
    mutate(ast = coalesce(ast, 0L), fgm = coalesce(fgm, 0L))
  asd <- shots |> filter(assisted)
  sl <- season_label(league, year)
  val <- tibble(league = league, year = year, season = sl, games = nrow(fin), made = nrow(shots),
                assisted = nrow(asd), unresolved = sum(!asd$resolved),
                resolved = mean(asd$resolved), ast_match = mean(cmp$ast == cmp$AST),
                fgm_match = mean(cmp$fgm == cmp$FGM))
  names <- ev |> filter(personId > 0) |>
    mutate(nm = ifelse(playerNameI != "", playerNameI, playerName)) |>
    filter(nm != "") |>
    count(teamId, personId, nm) |> arrange(teamId, personId, desc(n), nm) |>
    group_by(teamId, personId) |> slice(1) |> ungroup() |>
    transmute(teamId, creator = personId, name = nm)
  abbr <- sides |> count(teamId, abbr) |> arrange(teamId, desc(n), abbr) |>
    group_by(teamId) |> slice(1) |> ungroup() |> select(teamId, abbr)
  cr <- creator_table(shots) |> left_join(names, by = c("teamId", "creator")) |>
    mutate(name = ifelse(is.na(name), sprintf("id %.0f", creator), name)) |>
    left_join(abbr, by = "teamId") |>
    transmute(league = league, year = year, season = sl, team_id = teamId, team = abbr,
              creator, name, created, fgm_created)
  gm <- game_concentration(shots) |> group_by(teamId) |>
    summarise(games = n(), game_top1_share = mean(game_top1_share),
              game_top2_share = mean(game_top2_share),
              game_eff_creators = mean(game_eff_creators), .groups = "drop")
  tsh <- shots |> group_by(teamId) |>
    # unresolved first: in summarise, a later argument would see `assisted`
    # as the count just computed, not the column.
    summarise(unresolved = sum(assisted & !resolved), fgm = n(), assisted = sum(assisted),
              .groups = "drop") |>
    inner_join(gm, by = "teamId") |>
    transmute(league = league, year = year, team_id = teamId, fgm, assisted, unresolved, games,
              game_top1_share, game_top2_share, game_eff_creators)
  list(cr = cr, tsh = tsh, val = val)
}

res <- lapply(names(YEARS), function(lg) lapply(YEARS[[lg]], function(y) one_season(lg, y)))
res <- unlist(res, recursive = FALSE)
cr <- bind_rows(lapply(res, `[[`, "cr")) |> arrange(league, year, team_id, creator)
tsh <- bind_rows(lapply(res, `[[`, "tsh")) |> arrange(league, year, team_id)
val <- bind_rows(lapply(res, `[[`, "val"))
write_csv(cr, "output/creators_r.csv")
write_csv(tsh, "output/team_shots_r.csv")
write_csv(val, "output/validation_r.csv")

# 02: team-season metrics
ts <- cr |> group_by(league, year, season, team_id) |>
  arrange(desc(created), creator, .by_group = TRUE) |>
  summarise(team = team[1], created_total = sum(created),
            top1_share = concentration(created)[["top1_share"]],
            top2_share = concentration(created)[["top2_share"]],
            eff_creators = concentration(created)[["eff_creators"]],
            top_creator = name[1], top_created = created[1], .groups = "drop") |>
  rename(created = created_total) |>
  left_join(tsh |> mutate(assisted_share = assisted / fgm) |>
              select(league, year, team_id, fgm, assisted, games, game_top1_share,
                     game_top2_share, game_eff_creators, assisted_share),
            by = c("league", "year", "team_id")) |>
  group_by(league, year) |>
  mutate(top1_z = (top1_share - mean(top1_share)) / sd(top1_share)) |> ungroup() |>
  select(league, year, season, team_id, team, created, top1_share, top2_share, eff_creators,
         top_creator, top_created, fgm, assisted, games, game_top1_share, game_top2_share,
         game_eff_creators, assisted_share, top1_z) |>
  arrange(league, year, team_id)
write_csv(ts, "output/team_seasons_r.csv")

ls <- bind_rows(lapply(METRICS, function(m) ts |> group_by(league, year, season) |>
  summarise(metric = m, teams = n(), mean = mean_ci(.data[[m]])[1],
            lo = mean_ci(.data[[m]])[2], hi = mean_ci(.data[[m]])[3], .groups = "drop"))) |>
  arrange(league, metric, year)
write_csv(ls, "output/league_seasons_r.csv")

br <- ls |> group_by(league, metric) |> group_modify(function(g, key) {
  g <- arrange(g, year)
  t <- as.numeric(g$year); y <- g$mean
  b <- break_set(hinge_profile(t, y), length(t))
  X <- cbind(1, t, pmax(0, t - b[1]))
  beta <- solve(crossprod(X), crossprod(X, y))
  tibble(break_year = as.integer(b[1]), break_lo = as.integer(b[2]), break_hi = as.integer(b[3]),
         slope_before = beta[2], slope_after = beta[2] + beta[3], seasons = length(t))
}) |> ungroup() |> arrange(league, metric)
write_csv(br, "output/breaks_r.csv")

gap <- bind_rows(lapply(YEARS$wnba, function(wy) {
  ny <- wy - 1
  if (!(ny %in% YEARS$nba)) return(NULL)
  n <- ts |> filter(league == "nba", year == ny)
  w <- ts |> filter(league == "wnba", year == wy)
  bind_rows(lapply(METRICS, function(m) {
    d <- welch(n[[m]], w[[m]])
    tibble(wnba_year = wy, nba_season = season_label("nba", ny), metric = m,
           nba_mean = mean(n[[m]]), wnba_mean = mean(w[[m]]), gap = d[1], lo = d[2], hi = d[3])
  }))
})) |> arrange(metric, wnba_year)
write_csv(gap, "output/league_gap_r.csv")

lead <- bind_rows(lapply(names(YEARS), function(lg) bind_rows(lapply(c("top1_share", "top1_z"), function(by) {
  ts |> filter(league == lg) |> arrange(desc(.data[[by]]), year, team_id) |> head(15) |>
    transmute(ranked_by = by, rank = 1:15, league, season, team, top_creator, top1_share,
              top1_z, eff_creators)
}))))
write_csv(lead, "output/leaders_r.csv")

era <- bind_rows(lapply(names(YEARS), function(lg) {
  ys <- YEARS[[lg]]
  first <- head(ys, 5); last <- tail(ys, 5)
  a <- ts |> filter(league == lg, year %in% first)
  b <- ts |> filter(league == lg, year %in% last)
  bind_rows(lapply(METRICS, function(m) {
    d <- welch(b[[m]], a[[m]])
    tibble(league = lg, metric = m,
           first = paste(season_label(lg, first[1]), "to", season_label(lg, first[5])),
           last = paste(season_label(lg, last[1]), "to", season_label(lg, last[5])),
           first_mean = mean(a[[m]]), last_mean = mean(b[[m]]),
           first_n = nrow(a), last_n = nrow(b), change = d[1], lo = d[2], hi = d[3])
  }))
})) |> arrange(league, metric)
write_csv(era, "output/era_change_r.csv")
cat("R pipeline:", nrow(cr), "creator rows,", nrow(ts), "team-seasons\n")
