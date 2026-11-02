# Tests for the feed helpers in RMarkdown/bsky_client.R (issue #8).
#
# Each test runs bskyr's real bs_get_author_feed() on a saved API response
# (see helper-fixtures.R) and checks the helpers against answers computed
# directly from the same raw JSON. Run from the repository root with:
#   Rscript -e 'testthat::test_dir("RMarkdown/tests/testthat")'

sys.source("../../bsky_client.R", envir = environment(), toplevel.env = environment()) |>
  suppressMessages() |>
  tryCatch(error = function(e) NULL)   # only the helper definitions are needed here

raw <- raw_feed()$feed
truth <- list(
  repost = vapply(raw, function(i) identical(i$reason$`$type`, "app.bsky.feed.defs#reasonRepost"), logical(1)),
  reply = vapply(raw, function(i) !is.null(i$post$record$reply), logical(1)),
  parent_did = vapply(raw, function(i) {
    p <- i$reply$parent
    if (is.null(p)) NA_character_
    else p$author$did %||% sub("^at://([^/]+)/.*$", "\\1", p$uri)
  }, character(1)),
  text = vapply(raw, function(i) i$post$record$text %||% NA_character_, character(1)),
  created_at = vapply(raw, function(i) i$post$record$createdAt %||% NA_character_, character(1))
)
feed <- fixture_feed_tibble()

test_that("the fixture covers the cases the helpers must handle", {
  expect_equal(nrow(feed), length(raw))
  expect_identical(feed$uri, vapply(raw, function(i) i$post$uri, character(1)))
  expect_gt(sum(truth$repost), 0)
  expect_gt(sum(truth$reply), 0)
  deleted <- vapply(raw, function(i) endsWith(i$reply$parent$`$type` %||% "", "#notFoundPost"), logical(1))
  expect_gt(sum(deleted), 0)   # replies whose parent post was deleted
})

test_that("is_repost() finds exactly the reposts", {
  expect_identical(is_repost(feed), truth$repost)
})

test_that("is_reply() finds every reply, including replies to deleted posts", {
  expect_identical(is_reply(feed), truth$reply)
})

test_that("reply_parent_did() recovers the parent author, even when the parent is gone", {
  expect_identical(reply_parent_did(feed), truth$parent_did)
})

test_that("post_text() and post_created_at() read the author's record", {
  expect_identical(post_text(feed), truth$text)
  expect_identical(post_created_at(feed), truth$created_at)
})

test_that("a pinned post is not a repost", {
  pinned <- raw_feed()
  plain <- which(!truth$repost)[1]
  pinned$feed[[plain]]$reason <- list(`$type` = "app.bsky.feed.defs#reasonPin")
  expect_false(is_repost(fixture_feed_tibble(pinned))[plain])
})

test_that("a page with no reposts or replies gives all FALSE, not an error", {
  plain <- raw_feed()
  plain$feed <- plain$feed[!truth$repost & !truth$reply]
  f <- fixture_feed_tibble(plain)
  expect_false(any(is_repost(f)))
  expect_false(any(is_reply(f)))
})

test_that("the helpers fail loudly if bskyr renames its columns", {
  renamed <- feed
  names(renamed)[names(renamed) == "reason_$type"] <- "reason_kind"
  expect_error(is_repost(renamed), "doesn't recognize")
  no_parent <- feed[, !names(feed) %in% c("reply_parent", "reply_parent_uri")]
  expect_error(is_reply(no_parent), "doesn't recognize")
})

test_that("bsky_standardize() maps bskyr 0.4.x names to 0.5.0 names", {
  old <- tibble::tibble(list_itemcount = 1, joined_alltimecount = 2, joined_weekcount = 3, name = "x")
  new <- bsky_standardize(old)
  expect_named(new, c("list_item_count", "joined_all_time_count", "joined_week_count", "name"))
  expect_identical(bsky_standardize(new), new)   # already-correct names are left alone
})

test_that("the mock API refuses any write request", {
  req <- httr2::request("https://bsky.social/xrpc/com.atproto.repo.createRecord") |>
    httr2::req_body_json(list(collection = "app.bsky.feed.post"))
  expect_error(httr2::with_mocked_responses(bsky_mock, httr2::req_perform(req)),
               "refusing a write request")
})
