"""Reusable data-collection helpers for the bluesky-datascience tutorials.

This module is developed step-by-step in "Part 01 - Collecting Data at
Scale.ipynb". It provides three building blocks that every later notebook in
the series relies on:

* :func:`fetch_all_pages` — a generic cursor loop that exhaustively paginates
  any list-returning endpoint (author feeds, follows, followers, likes, ...).
* :func:`call_with_backoff` — an exponential-backoff wrapper that retries
  politely when the server answers HTTP 429 ("RateLimitExceeded").
* :func:`get_rate_limit_status` — reads the ``RateLimit-*`` response headers
  that PDS hosts (e.g. ``https://bsky.social``) attach to every response.
"""

import random
import time
from datetime import datetime, timezone

import requests
from atproto_client.exceptions import RequestException


def fetch_all_pages(
    method,
    params,
    items_attr,
    max_pages=100,
    delay=0.1,
    progress_every=10,
):
    """Exhaustively paginate a cursor-based ATProto endpoint.

    Parameters
    ----------
    method : callable
        A bound SDK method that accepts keyword arguments and returns a
        response with a ``cursor`` attribute, e.g. ``client.get_author_feed``,
        ``client.get_follows``, or ``client.get_followers``.
    params : dict
        Keyword arguments passed to ``method`` on every call, e.g.
        ``{"actor": "nytimes.com", "limit": 100}``. Do not include
        ``cursor``; this function manages it.
    items_attr : str
        Name of the response attribute holding the list of items
        (``"feed"`` for author feeds, ``"follows"`` / ``"followers"`` for
        the graph endpoints).
    max_pages : int
        Safety cap on the number of requests. Always set one: some accounts
        have millions of followers, and an unbounded loop is how collection
        scripts melt down (and annoy server operators).
    delay : float
        Seconds to sleep between requests. The default 0.1 s keeps us far
        below the documented per-IP rate limit while staying fast.
    progress_every : int
        Print a progress line every N pages (0 disables printing).

    Returns
    -------
    list
        All items concatenated across pages, in API order.
    """
    items = []
    cursor = None
    pages = 0

    while pages < max_pages:
        page_params = dict(params)
        if cursor is not None:
            page_params["cursor"] = cursor

        response = call_with_backoff(method, **page_params)
        items.extend(getattr(response, items_attr))
        pages += 1

        if progress_every and pages % progress_every == 0:
            print(f"  page {pages:>3}: {len(items):,} items so far")

        cursor = response.cursor
        if cursor is None:  # the API signals "no more pages" with a null cursor
            break

        time.sleep(delay)  # politeness: never hammer the server back-to-back

    if pages == max_pages and cursor is not None:
        print(f"  stopped at max_pages={max_pages} with more pages remaining")
    if progress_every:
        print(f"Done: {len(items):,} items across {pages} page(s)")
    return items


def is_rate_limit_error(exc):
    """Return True if an SDK exception represents an HTTP 429 rate limit."""
    response = getattr(exc, "response", None)
    if response is None:
        return False
    if getattr(response, "status_code", None) == 429:
        return True
    content = getattr(response, "content", None)
    return getattr(content, "error", None) == "RateLimitExceeded"


def call_with_backoff(method, *args, max_retries=5, base_delay=1.0, **kwargs):
    """Call ``method``, retrying with exponential backoff on rate limits.

    On HTTP 429 / ``RateLimitExceeded`` the wait doubles on every attempt
    (1 s, 2 s, 4 s, 8 s, 16 s by default) with a little random "jitter" so
    that many parallel clients do not all retry at the same instant. Any
    other error is re-raised immediately — backoff only helps with
    *transient* failures, and retrying a typo'd handle forever helps no one.
    """
    for attempt in range(max_retries + 1):
        try:
            return method(*args, **kwargs)
        except RequestException as exc:
            if not is_rate_limit_error(exc) or attempt == max_retries:
                raise
            wait = base_delay * (2**attempt) + random.uniform(0, 1)
            print(
                f"  rate limited (attempt {attempt + 1}/{max_retries}); "
                f"sleeping {wait:.1f}s before retrying"
            )
            time.sleep(wait)


def get_rate_limit_status(url="https://bsky.social/xrpc/com.atproto.server.describeServer"):
    """Read the ``RateLimit-*`` headers from a PDS endpoint.

    Returns a dict with the limit, how many requests remain in the current
    window, and when the window resets (as an aware UTC datetime). Note that
    the public AppView (``public.api.bsky.app``) does not send these headers;
    they come from PDS hosts such as ``bsky.social``.
    """
    response = requests.get(url, timeout=30)
    headers = response.headers
    status = {
        "limit": int(headers["RateLimit-Limit"]),
        "remaining": int(headers["RateLimit-Remaining"]),
        "reset": datetime.fromtimestamp(int(headers["RateLimit-Reset"]), tz=timezone.utc),
        "policy": headers.get("RateLimit-Policy"),
    }
    return status
