# R/functions.R against the same fixtures as tests/python/test_lib.py.
# Run from tests/R:  Rscript -e 'testthat::test_dir(".")'

source(file.path("..", "..", "R", "functions.R"))

events <- function() {
  tibble::tribble(
    ~seq, ~teamId, ~personId, ~playerName, ~playerNameI, ~actionType, ~description, ~shotValue,
    1L, 1, 14, "Jordan", "M. Jordan", "Made Shot", "Jordan 2' Layup (2 PTS) (Longley 1 AST)", 2L,
    2L, 1, 10, "Longley", "L. Longley", "Made Shot", "Longley 8' Hook Shot (2 PTS) (F. Wagner 1 AST)", 2L,
    3L, 1, 11, "Wagner", "F. Wagner", "Missed Shot", "MISS Wagner 20' Jump Shot", 0L,
    4L, 1, 12, "Wagner", "M. Wagner", "Rebound", "Wagner REBOUND (Off:0 Def:1)", 0L,
    5L, 1, 13, "Johnson", "A. Johnson", "Missed Shot", "MISS Ar. Johnson 3PT Jump Shot", 0L,
    6L, 1, 14, "Jordan", "M. Jordan", "Made Shot", "Jordan 25' 3PT Jump Shot (5 PTS) (Ar. Johnson 1 AST)", 3L,
    7L, 1, 14, "Jordan", "M. Jordan", "Made Shot", "Jordan 15' Jump Shot (7 PTS)", 2L,
    8L, 1, 14, "Jordan", "M. Jordan", "Made Shot", "Jordan Dunk (9 PTS) (Nobody 1 AST)", 2L,
    9L, 2, 20, "Longley", "X. Longley", "Made Shot", "Longley Layup (2 PTS)", 2L,
    10L, 1, 10, "Longley", "L. Longley", "Made Shot", "Longley 24' 3PT Jump Shot (5 PTS) (Jordan 1 AST)", 0L
  ) |> dplyr::mutate(gameId = "g", .before = 1)
}

test_that("passers resolve in three passes", {
  out <- resolve_passers(events()) |> dplyr::arrange(seq)
  expect_equal(out$seq, c(1L, 2L, 6L, 7L, 8L, 9L, 10L))
  expect_equal(out$passer, c(10, 11, 13, NA, NA, NA, 14))
  expect_equal(out$points, c(2L, 2L, 3L, 2L, 2L, 2L, 3L))
  expect_false(out$resolved[out$seq == 8])
})

test_that("creator table credits passers and drops unresolved", {
  cr <- creator_table(resolve_passers(events()))
  expect_equal(paste(cr$teamId, cr$creator, cr$created),
               c("1 10 2", "1 11 2", "1 13 3", "1 14 5", "2 20 2"))
})

test_that("game concentration", {
  g <- game_concentration(resolve_passers(events())) |> dplyr::arrange(teamId)
  sh <- c(5, 3, 2, 2) / 12
  expect_equal(g$game_top1_share[1], 5 / 12)
  expect_equal(g$game_top2_share[1], 8 / 12)
  expect_equal(g$game_eff_creators[1], 1 / sum(sh^2))
  expect_equal(g$game_eff_creators[2], 1)
})

test_that("concentration", {
  c3 <- concentration(c(50, 30, 20))
  expect_equal(unname(c3), c(0.5, 0.8, 1 / (0.25 + 0.09 + 0.04)))
  expect_equal(unname(concentration(7)["top2_share"]), 1)
})

test_that("mean CI and Welch match t.test", {
  x <- c(1, 2, 3, 4); y <- c(2, 4, 6, 9, 1)
  expect_equal(mean_ci(x), c(2.5, t.test(x)$conf.int[1:2]))
  expect_equal(welch(x, y), c(2.5 - 4.4, t.test(x, y)$conf.int[1:2]))
})

test_that("hinge finds an exact kink", {
  t <- 2000:2011
  y <- 1 + 0.1 * (t - 2000) + ifelse(t > 2006, 0.5 * (t - 2006), 0)
  prof <- hinge_profile(as.numeric(t), y)
  expect_equal(break_set(prof, length(t)), c(2006, 2006, 2006))
  expect_lt(min(prof$sse), 1e-18)
})
