# A mock Bluesky API for testing the R Markdown documents without credentials.
#
# bskyr authenticates every request, so without an account a normal knit skips
# every API chunk and tests none of the code that calls bskyr (see issue #8).
# This mock lets those chunks run for real, against live public data:
#
#   * `com.atproto.server.createSession` (login) returns a fake session, so
#     bs_auth() succeeds without a real account.
#   * Read requests for `app.bsky.*` methods on bsky.social are forwarded,
#     without the fake token, to the public AppView (https://public.api.bsky.app),
#     which serves the same data unauthenticated. The public responses omit the
#     `viewer` objects (the logged-in user's relationship to each post and
#     account) that authenticated ones always carry, and bskyr's cleaners drop
#     rows without them, so neutral `viewer` objects are added back.
#   * A few reads exist only for logged-in users (search, your timeline). They
#     are answered with real public posts in the same response shape: enough to
#     test the code that handles the response, not the content of a real search.
#   * Any other request (other hosts such as mod.bsky.app, PDS methods such as
#     describeServer) is passed through unchanged, so documents see the real
#     behavior of those services.
#   * Any WRITE (a POST other than login) stops with an error. A document that
#     tries to post, like, or follow fails the check: proof that none does.
#
# This file is test infrastructure, not tutorial code. Use it through
# scripts/check_rmarkdown.R --mock-api, or in tests:
#
#   source("RMarkdown/tests/mock_api.R")
#   with_bsky_mock(bskyr::bs_get_author_feed("bsky.app", limit = 10))

PUBLIC_APPVIEW <- "https://public.api.bsky.app"

if (!exists("%||%")) `%||%` <- function(x, y) if (is.null(x)) y else x  # base R < 4.4

# Reads that need a logged-in user, answered with public posts of the same shape
.mock_authonly <- c("app.bsky.feed.searchPosts", "app.bsky.feed.getTimeline")

.add_viewer <- function(x) {
  if (!is.list(x)) return(x)
  if (!is.null(names(x))) {
    if (all(c("uri", "cid", "author", "record") %in% names(x)) && is.null(x$viewer)) {
      x$viewer <- list(threadMuted = FALSE, embeddingDisabled = FALSE)
    }
    if (all(c("did", "handle") %in% names(x)) && is.null(x$viewer)) {
      x$viewer <- list(muted = FALSE, blockedBy = FALSE)
    }
  }
  out <- lapply(x, .add_viewer)
  attributes(out) <- attributes(x)
  out
}

.json_response <- function(url, data, status = 200L) {
  httr2::response(
    status_code = status, url = url,
    headers = list(`Content-Type` = "application/json"),
    body = charToRaw(jsonlite::toJSON(data, auto_unbox = TRUE, null = "null"))
  )
}

.fetch <- function(url) {
  r <- curl::curl_fetch_memory(url)
  list(status = r$status_code, headers = curl::parse_headers_list(r$headers),
       body = r$content)
}

# API responses are UTF-8. rawToChar() returns an *unmarked* string, which in a
# non-UTF-8 locale (e.g. LC_ALL=C) gets re-encoded on the way back out, turning
# "’" into mojibake. Mark it first, so the mock is byte-faithful in any locale.
.parse_body <- function(raw) {
  text <- rawToChar(raw)
  Encoding(text) <- "UTF-8"
  jsonlite::fromJSON(text, simplifyVector = FALSE)
}

.query_param <- function(url, name) {
  q <- httr2::url_parse(url)$query
  if (is.null(q) || is.null(q[[name]])) NULL else q[[name]]
}

.synthesize <- function(method, url) {
  limit <- as.integer(.query_param(url, "limit") %||% "25")
  feed_url <- paste0(PUBLIC_APPVIEW, "/xrpc/app.bsky.feed.getAuthorFeed?actor=bsky.app&limit=",
                     min(max(limit, 1L), 100L))
  feed <- .parse_body(.fetch(feed_url)$body)
  if (method == "app.bsky.feed.searchPosts") {
    posts <- lapply(feed$feed, `[[`, "post")
    return(.add_viewer(list(posts = posts, hitsTotal = length(posts))))
  }
  .add_viewer(list(feed = feed$feed))   # getTimeline: one page, no cursor
}

bsky_mock <- function(req) {
  url <- req$url
  method_name <- sub("^.*/xrpc/([^?]+).*$", "\\1", url)
  is_write <- !is.null(req$body) || identical(toupper(req$method %||% "GET"), "POST")

  if (method_name == "com.atproto.server.createSession") {
    return(.json_response(url, list(
      did = "did:plc:z72i7hdynmk6r22z27h6tvur", handle = "bsky.app",
      accessJwt = "mock-access-token", refreshJwt = "mock-refresh-token",
      active = TRUE
    )))
  }
  if (is_write) {
    stop("Mock API: refusing a write request (", method_name, "). ",
         "Documents must never execute write endpoints; put them in eval=FALSE chunks.",
         call. = FALSE)
  }
  on_pds <- startsWith(url, "https://bsky.social/xrpc/app.bsky.")
  if (on_pds && method_name %in% .mock_authonly) {
    return(.json_response(url, .synthesize(method_name, url)))
  }
  target <- if (on_pds) sub("^https://bsky.social", PUBLIC_APPVIEW, url) else url
  r <- .fetch(target)
  if (on_pds && r$status == 200L) {
    data <- .add_viewer(.parse_body(r$body))
    return(.json_response(url, data))
  }
  httr2::response(status_code = r$status, url = target, headers = r$headers, body = r$body)
}

# Run `code` with the mock active, dummy credentials set, and bskyr's on-disk
# token cache redirected to a temporary directory, so a fake token can never be
# picked up by a later, real session.
with_bsky_mock <- function(code) {
  withr::with_envvar(
    c(BLUESKY_APP_USER = "bsky.app",
      BLUESKY_APP_PASS = "mock-mock-mock-mock",
      R_USER_CONFIG_DIR = file.path(tempdir(), "bskyr-mock-config")),
    httr2::with_mocked_responses(bsky_mock, code)
  )
}
