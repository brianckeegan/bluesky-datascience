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
