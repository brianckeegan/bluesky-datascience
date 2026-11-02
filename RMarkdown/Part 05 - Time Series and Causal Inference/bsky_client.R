# bsky_client.R — shared connection helper for the Bluesky Data Science
# R Markdown series. This is the R counterpart of the Python series'
# `bsky_client.py`: it looks for credentials, authenticates with bskyr if it
# finds them, and records whether we are authenticated so that documents can
# guard their API chunks.
#
# Credentials are looked up in this order:
#   1. An `atproto.json` file ({"handle": ..., "password": ...}) in this
#      directory, the repository root, or up to two directories above —
#      the same file the Python notebooks use. It is gitignored.
#   2. The BLUESKY_APP_USER / BLUESKY_APP_PASS environment variables (e.g.
#      set in ~/.Renviron), which bskyr reads natively.
#
# After sourcing this file you have:
#   bsky_authed — TRUE if we authenticated, FALSE otherwise
#   bsky_auth   — the bskyr auth object (or NULL)
# and a few helpers for reading bskyr's feed tibbles (see the bottom of the
# file): is_repost(), is_reply(), reply_parent_did(), post_text(),
# post_created_at(), and bsky_standardize().
#
# Every R Markdown document in this series sets
#   knitr::opts_chunk$set(eval = bsky_authed)
# right after sourcing this file, so that knitting without credentials
# produces the full prose with API chunks skipped, and knitting with
# credentials produces the full document.

suppressPackageStartupMessages({
  library(bskyr)
  library(jsonlite)
})

bsky_find_credentials <- function() {
  candidates <- c(
    "atproto.json",
    file.path("..", "atproto.json"),
    file.path("..", "..", "atproto.json"),
    file.path(path.expand("~"), "atproto.json")
  )
  for (path in candidates) {
    if (file.exists(path)) {
      return(normalizePath(path))
    }
  }
  NULL
}

bsky_connect <- function() {
  cred_path <- bsky_find_credentials()
  if (!is.null(cred_path)) {
    creds <- jsonlite::read_json(cred_path)
    Sys.setenv(
      BLUESKY_APP_USER = creds$handle,
      BLUESKY_APP_PASS = creds$password
    )
  }
  if (bs_has_user() && bs_has_pass()) {
    auth <- tryCatch(
      bs_auth(bs_get_user(), bs_get_pass()),
      error = function(e) {
        message("Authentication failed: ", conditionMessage(e))
        NULL
      }
    )
    if (!is.null(auth)) {
      message("Authenticated to Bluesky as ", bs_get_user())
      return(auth)
    }
  }
  message(
    "No Bluesky credentials found. Save an atproto.json next to this file\n",
    "or set BLUESKY_APP_USER / BLUESKY_APP_PASS in ~/.Renviron; without\n",
    "them, chunks that call the API are skipped when this document is knit."
  )
  NULL
}

bsky_auth <- bsky_connect()
bsky_authed <- !is.null(bsky_auth)

# ---------------------------------------------------------------------------
# Helpers for bskyr's feed tibbles
#
# bskyr flattens each feed item into columns, but the columns describing
# reposts and replies are easy to get wrong, and getting them wrong fails
# silently: a filter on a column that doesn't exist removes nothing. These
# helpers were checked against the raw API JSON, and they raise an error if
# bskyr's columns ever change shape, rather than quietly returning FALSE.
# Tested in RMarkdown/tests/testthat/test-helpers.R.
# ---------------------------------------------------------------------------

`%or%` <- function(x, y) if (is.null(x)) y else x

# TRUE for feed items that are reposts of someone else's post. bskyr names the
# column `reason_$type` (the API's `$type` field). Pinned posts also carry a
# `reason` (#reasonPin) and are not reposts.
is_repost <- function(feed) {
  if (!"reason_$type" %in% names(feed)) {
    stray <- grep("^reason_", names(feed), value = TRUE)
    if (length(stray)) {
      stop("bskyr returned repost columns this helper doesn't recognize: ",
           paste(stray, collapse = ", "), call. = FALSE)
    }
    return(rep(FALSE, nrow(feed)))   # no item on these pages had a reason
  }
  type <- feed[["reason_$type"]]
  !is.na(type) & endsWith(type, "#reasonRepost")
}

# TRUE for posts that reply to another post. bskyr keeps the parent post in the
# `reply_parent` list-column, except when the parent has been deleted: then it
# records only `reply_parent_uri` (with `reply_parent_not_found = TRUE`).
is_reply <- function(feed) {
  n <- nrow(feed)
  has_parent <- if ("reply_parent" %in% names(feed)) {
    !vapply(feed$reply_parent, is.null, logical(1))
  } else rep(FALSE, n)
  parent_gone <- if ("reply_parent_uri" %in% names(feed)) {
    !is.na(feed$reply_parent_uri)
  } else rep(FALSE, n)
  if (!any(c("reply_parent", "reply_parent_uri") %in% names(feed))) {
    stray <- setdiff(grep("^reply_", names(feed), value = TRUE), "reply_count")
    if (length(stray)) {
      stop("bskyr returned reply columns this helper doesn't recognize: ",
           paste(stray, collapse = ", "), call. = FALSE)
    }
  }
  has_parent | parent_gone
}

# The DID of the account each post replies to (NA for non-replies). When the
# parent was deleted, the DID is read from the parent's AT-URI
# (at://<did>/app.bsky.feed.post/<rkey>).
reply_parent_did <- function(feed) {
  out <- rep(NA_character_, nrow(feed))
  if ("reply_parent" %in% names(feed)) {
    out <- vapply(feed$reply_parent,
                  function(p) as.character(p$author$did %or% NA_character_),
                  character(1))
  }
  if ("reply_parent_uri" %in% names(feed)) {
    gone <- is.na(out) & !is.na(feed$reply_parent_uri)
    out[gone] <- sub("^at://([^/]+)/.*$", "\\1", feed$reply_parent_uri[gone])
  }
  out
}

# The text and creation time the author's app wrote, from the `record`
# list-column. (`indexed_at` is when Bluesky's servers processed the post.)
post_text <- function(feed) {
  vapply(feed$record, function(r) as.character(r[["text"]] %or% NA_character_), character(1))
}
post_created_at <- function(feed) {
  vapply(feed$record, function(r) as.character(r[["created_at"]] %or% NA_character_), character(1))
}

# bskyr 0.4.x turned only the *first* camelCase boundary into an underscore
# (`listItemCount` became `list_itemcount`); bskyr 0.5.0 fixes this
# (`list_item_count`). The documents use the corrected names; this renames
# the old ones so the code works with either version.
bsky_standardize <- function(df) {
  renames <- c(list_itemcount = "list_item_count",
               joined_alltimecount = "joined_all_time_count",
               joined_weekcount = "joined_week_count")
  hit <- intersect(names(renames), names(df))
  names(df)[match(hit, names(df))] <- unname(renames[hit])
  df
}
