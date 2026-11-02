# Offline fixtures for the R helper tests.
#
# fixtures/author_feed_bsky_app.json is one real page of bsky.app's author
# feed (40 items: reposts, replies, and replies whose parent was deleted).
# Every account other than bsky.app and nytimes.com is redacted: handles,
# names and post text replaced, DIDs swapped for consistent fake ones,
# embeds removed. Regenerate it only if the API's response shape changes.

source("../mock_api.R")   # .add_viewer(), .json_response(), %||%

fixture_path <- function(name) file.path("..", "fixtures", name)
raw_feed <- function() {
  text <- paste(readLines(fixture_path("author_feed_bsky_app.json"), warn = FALSE, encoding = "UTF-8"),
                collapse = "\n")
  Encoding(text) <- "UTF-8"
  jsonlite::fromJSON(text, simplifyVector = FALSE)
}

# A mock that answers from the fixture instead of the network: login gets a
# fake session, getAuthorFeed gets the saved page (optionally modified), and
# anything else is an error, so a test can never reach the real API.
fixture_mock <- function(feed_json = raw_feed()) {
  function(req) {
    method <- sub("^.*/xrpc/([^?]+).*$", "\\1", req$url)
    if (method == "com.atproto.server.createSession") {
      return(.json_response(req$url, list(did = "did:plc:z72i7hdynmk6r22z27h6tvur",
                                          handle = "bsky.app", accessJwt = "test", refreshJwt = "test")))
    }
    if (method == "app.bsky.feed.getAuthorFeed") {
      return(.json_response(req$url, .add_viewer(feed_json)))
    }
    stop("fixture_mock: no fixture for ", method, call. = FALSE)
  }
}

# Run code against the fixture with bskyr's helpers loaded. bsky_client.R is
# sourced inside the mock so its login attempt never touches the network.
with_fixture <- function(code, feed_json = raw_feed()) {
  withr::with_envvar(
    c(BLUESKY_APP_USER = "bsky.app", BLUESKY_APP_PASS = "mock-mock-mock-mock",
      R_USER_CONFIG_DIR = file.path(tempdir(), "bskyr-test-config")),
    httr2::with_mocked_responses(fixture_mock(feed_json), {
      suppressMessages(sys.source("../../bsky_client.R", envir = environment()))
      force(code)
    })
  )
}

fixture_feed_tibble <- function(feed_json = raw_feed()) {
  with_fixture(bskyr::bs_get_author_feed("bsky.app", limit = 40, auth = list(accessJwt = "test")),
               feed_json = feed_json)
}
