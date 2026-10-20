# The R twins of python/lib.py, written from its docstrings. tests/R pins
# them to the same fixtures as tests/python.

suppressPackageStartupMessages(library(dplyr))

YEARS <- list(nba = 1996:2025, wnba = 1997:2026)
AST_RE <- "\\(([^()]+?) (\\d+) AST\\)\\s*$"

season_label <- function(league, year) {
  if (league == "nba") sprintf("%d-%02d", year, (year + 1) %% 100) else as.character(year)
}

made_shots <- function(ev) {
  m <- ev |> filter(actionType == "Made Shot")
  has <- grepl(AST_RE, m$description, perl = TRUE)
  txt <- rep(NA_character_, nrow(m))
  txt[has] <- trimws(sub(paste0("^.*", AST_RE), "\\1", m$description[has], perl = TRUE))
  m |> transmute(gameId, seq, teamId, personId,
                 points = as.integer(ifelse(shotValue %in% c(2L, 3L), shotValue,
                                            ifelse(grepl("3PT", description, fixed = TRUE), 3L, 2L))),
                 ast_text = txt)
}

unique_match <- function(cand) {
  cand |> distinct(gameId, seq, pid) |> group_by(gameId, seq) |>
    filter(n() == 1) |> ungroup()
}

resolve_passers <- function(ev) {
  m <- made_shots(ev)
  a <- m |> filter(!is.na(ast_text))
  people <- ev |> filter(personId > 0)
  done <- tibble(gameId = character(), seq = integer(), pid = numeric())
  for (col in c("playerName", "playerNameI")) {
    left <- a |> anti_join(done, by = c("gameId", "seq"))
    names <- people |> transmute(gameId, teamId, pid = personId, ast_text = .data[[col]]) |> distinct()
    cand <- left |> inner_join(names, by = c("gameId", "teamId", "ast_text"),
                               relationship = "many-to-many") |>
      filter(pid != personId)
    done <- bind_rows(done, unique_match(cand))
  }
  left <- a |> anti_join(done, by = c("gameId", "seq"))
  lead <- people |> transmute(gameId, teamId, pid = personId, d = sub("^MISS ", "", description)) |>
    distinct()
  cand <- left |> inner_join(lead, by = c("gameId", "teamId"), relationship = "many-to-many") |>
    filter(startsWith(d, paste0(ast_text, " ")), pid != personId)
  done <- bind_rows(done, unique_match(cand))
  m |> left_join(done |> rename(passer = pid), by = c("gameId", "seq")) |>
    mutate(assisted = !is.na(ast_text), resolved = !is.na(passer))
}

credited <- function(shots) {
  shots |> filter(!assisted | resolved) |>
    mutate(creator = ifelse(assisted, passer, personId))
}

creator_table <- function(shots) {
  credited(shots) |> group_by(teamId, creator) |>
    summarise(created = sum(points), fgm_created = n(), .groups = "drop") |>
    arrange(teamId, creator)
}

game_concentration <- function(shots) {
  credited(shots) |> group_by(gameId, teamId, creator) |>
    summarise(c = sum(points), .groups = "drop") |>
    group_by(gameId, teamId) |> mutate(sh = c / sum(c)) |>
    arrange(desc(sh), .by_group = TRUE) |>
    summarise(game_top1_share = sh[1], game_top2_share = sum(head(sh, 2)),
              game_eff_creators = 1 / sum(sh^2), .groups = "drop")
}

concentration <- function(created) {
  s <- sort(created / sum(created), decreasing = TRUE)
  c(top1_share = s[1], top2_share = s[1] + (if (length(s) > 1) s[2] else 0),
    eff_creators = 1 / sum(s^2))
}

mean_ci <- function(x) {
  n <- length(x); m <- mean(x)
  h <- qt(0.975, n - 1) * sd(x) / sqrt(n)
  c(m, m - h, m + h)
}

welch <- function(x, y) {
  nx <- length(x); ny <- length(y)
  vx <- var(x); vy <- var(y)
  se <- sqrt(vx / nx + vy / ny)
  df <- (vx / nx + vy / ny)^2 / ((vx / nx)^2 / (nx - 1) + (vy / ny)^2 / (ny - 1))
  d <- mean(x) - mean(y)
  h <- qt(0.975, df) * se
  c(d, d - h, d + h)
}

hinge_profile <- function(t, y, min_side = 3L) {
  ks <- sort(unique(t))
  ks <- ks[(min_side + 1):(length(ks) - min_side)]
  sse <- sapply(ks, function(k) {
    X <- cbind(1, t, pmax(0, t - k))
    beta <- solve(crossprod(X), crossprod(X, y))
    r <- y - X %*% beta
    sum(r^2)
  })
  data.frame(k = ks, sse = sse)
}

break_set <- function(prof, n) {
  o <- order(prof$sse, prof$k)
  kbest <- prof$k[o[1]]
  cut <- prof$sse[o[1]] * (1 + qf(0.95, 1, n - 4) / (n - 4))
  inset <- prof$k[prof$sse <= cut]
  c(kbest, min(inset), max(inset))
}
