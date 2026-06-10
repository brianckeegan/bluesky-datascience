"""Helper functions for Part 05 - Time Series and Causal Inference.

These helpers wrap the repetitive parts of the tutorial — paginating an
account's full posting history, tidying it into a time-indexed DataFrame,
and fitting the interrupted time series (ITS) and difference-in-differences
(DiD) regressions — so the notebook can focus on the research design.
"""

import time

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
from atproto import exceptions as atproto_exceptions

PUBLIC_APPVIEW = "https://public.api.bsky.app"
REPOST_TYPE = "app.bsky.feed.defs#reasonRepost"


def _get(mapping, *keys, default=None):
    """Return the first non-None value among ``keys`` in ``mapping``.

    The SDK's ``model_dump()`` uses snake_case keys (``created_at``,
    ``py_type``) while raw XRPC JSON uses camelCase (``createdAt``,
    ``$type``). Checking both lets the rest of the pipeline ignore which
    path produced a page.
    """
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return default


def _fetch_page(client, actor, cursor, page_size):
    """Fetch one page of an author feed as a plain dictionary.

    Tries the SDK first (``client.get_author_feed``). Bluesky's lexicons
    evolve faster than SDK releases, so occasionally a feed contains a
    record type the SDK's validators do not recognize yet and the SDK
    raises a ``ModelError`` for the whole page. When that happens we fall
    back to requesting the same page as raw JSON from the public AppView,
    which involves no client-side validation.
    """
    try:
        response = client.get_author_feed(
            actor=actor, limit=page_size, cursor=cursor
        )
        return response.model_dump()
    except atproto_exceptions.ModelError:
        params = {"actor": actor, "limit": page_size}
        if cursor:
            params["cursor"] = cursor
        raw = requests.get(
            f"{PUBLIC_APPVIEW}/xrpc/app.bsky.feed.getAuthorFeed",
            params=params,
            timeout=30,
        )
        raw.raise_for_status()
        return raw.json()


def fetch_history(client, actor, page_size=100, sleep=0.1, max_pages=120):
    """Paginate through an account's entire author feed.

    Walks ``get_author_feed`` (``app.bsky.feed.getAuthorFeed``) with the
    ``cursor`` parameter until the feed is exhausted or ``max_pages`` is
    reached, sleeping ``sleep`` seconds between requests to be polite.

    Each feed item is flattened into a small dictionary. We keep only the
    fields the analysis needs (data minimization): the post URI, whether the
    action was an original post or a repost, whether it was a reply, the
    timestamp of the action, and engagement counts. For original posts the
    timestamp is the post record's ``created_at``; for reposts it is the
    repost's ``indexed_at``, because the *act of reposting* is the behavior
    we want to place in time (the underlying post may be much older).

    Returns a list of dictionaries, newest actions first.
    """
    records = []
    cursor = None
    pages = 0
    while pages < max_pages:
        page = _fetch_page(client, actor, cursor, page_size)
        for item in page.get("feed", []):
            post = item["post"]
            record = post.get("record", {})
            reason = item.get("reason")
            reason_type = _get(reason, "py_type", "$type")
            is_repost = reason_type == REPOST_TYPE
            records.append(
                {
                    "actor": actor,
                    "uri": post["uri"],
                    "action": "repost" if is_repost else "post",
                    "is_reply": record.get("reply") is not None,
                    "created_at": (
                        _get(reason, "indexed_at", "indexedAt")
                        if is_repost
                        else _get(record, "created_at", "createdAt")
                    ),
                    "like_count": _get(post, "like_count", "likeCount", default=0),
                    "repost_count": _get(post, "repost_count", "repostCount", default=0),
                    "reply_count": _get(post, "reply_count", "replyCount", default=0),
                }
            )
        pages += 1
        cursor = page.get("cursor")
        if cursor is None:
            break
        time.sleep(sleep)
    return records


def history_to_frame(records, tz="UTC"):
    """Turn ``fetch_history`` output into a time-indexed DataFrame.

    Parses the ISO-8601 ``created_at`` strings into a timezone-aware
    ``DatetimeIndex`` (Bluesky timestamps are UTC), optionally converts to a
    local timezone like ``America/Denver``, and sorts oldest-to-newest.
    """
    df = pd.DataFrame(records)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, format="ISO8601")
    if tz != "UTC":
        df["created_at"] = df["created_at"].dt.tz_convert(tz)
    return df.set_index("created_at").sort_index()


def daily_counts(frame, label=None):
    """Resample a time-indexed activity frame to daily action counts."""
    series = frame.resample("D")["uri"].count()
    series.name = label or "actions"
    return series


def weekly_counts(frame, label=None):
    """Resample a time-indexed activity frame to weekly action counts.

    Drops the final (incomplete) week so the most recent observation is not
    artificially low just because the collection happened mid-week.
    """
    series = frame.resample("W")["uri"].count().iloc[:-1]
    series.name = label or "actions"
    return series


def fit_its(weekly, event):
    """Fit an interrupted time series (segmented) regression with OLS.

    The design matrix for weekly counts :math:`y_t` is

        y_t = b0 + b1 * t + b2 * post_t + b3 * (t - t_event) * post_t + e_t

    where ``t`` counts weeks from the start of the series, ``post_t`` is 1
    for weeks on or after ``event``, and the interaction measures the change
    in slope after the event. ``b2`` is the immediate level shift and ``b3``
    the trend change.

    Returns ``(results, design)`` where ``design`` is the DataFrame of
    regressors aligned to the weekly index.
    """
    event = pd.Timestamp(event)
    if event.tz is None and weekly.index.tz is not None:
        event = event.tz_localize(weekly.index.tz)
    t = np.arange(len(weekly))
    post = (weekly.index >= event).astype(int)
    t_event = post.argmax() if post.any() else len(weekly)
    design = pd.DataFrame(
        {
            "t": t,
            "post": post,
            "t_post": (t - t_event) * post,
        },
        index=weekly.index,
    )
    X = sm.add_constant(design)
    results = sm.OLS(weekly.values, X).fit()
    return results, design


def coefficient_table(results, names=None):
    """Tidy a fitted statsmodels result into a coefficient DataFrame."""
    table = pd.DataFrame(
        {
            "coef": results.params,
            "std_err": results.bse,
            "t": results.tvalues,
            "p_value": results.pvalues,
        }
    )
    if names is not None:
        table.index = names
    table.index.name = "term"
    return table


def make_did_panel(weekly_by_account, treated_actor, event):
    """Stack weekly series for several accounts into a tidy DiD panel.

    ``weekly_by_account`` maps actor handle -> weekly count Series. The
    returned long-format DataFrame has one row per (account, week) with
    ``treated`` (is this the treated account?), ``post`` (is the week on or
    after the event?), and their interaction ``treated_post`` — the
    difference-in-differences estimand.
    """
    event = pd.Timestamp(event)
    frames = []
    for actor, series in weekly_by_account.items():
        ev = event
        if ev.tz is None and series.index.tz is not None:
            ev = ev.tz_localize(series.index.tz)
        frames.append(
            pd.DataFrame(
                {
                    "week": series.index,
                    "actions": series.values,
                    "account": actor,
                    "treated": int(actor == treated_actor),
                    "post": (series.index >= ev).astype(int),
                }
            )
        )
    panel = pd.concat(frames, ignore_index=True)
    panel["treated_post"] = panel["treated"] * panel["post"]
    return panel


def fit_did(panel):
    """Fit the canonical 2x2 difference-in-differences regression.

        actions = b0 + b1 * treated + b2 * post + b3 * treated*post + e

    ``b3`` is the DiD estimate: the post-event change for the treated
    account over and above the change for the comparison account.
    """
    X = sm.add_constant(panel[["treated", "post", "treated_post"]])
    return sm.OLS(panel["actions"].values, X).fit()


def get_profile_covariates(client, handles):
    """Retrieve matching covariates for a list of accounts.

    Uses ``get_profiles`` (``app.bsky.actor.getProfiles``, up to 25 handles
    per request) to pull the profile fields a researcher would match
    comparison accounts on: follower and follow counts, total posts, and
    account creation date (from which we derive account age).

    Returns a DataFrame indexed by handle.
    """
    rows = []
    for start in range(0, len(handles), 25):
        batch = handles[start : start + 25]
        response = client.get_profiles(actors=batch)
        for profile in response.profiles:
            rows.append(
                {
                    "handle": profile.handle,
                    "followers": profile.followers_count,
                    "follows": profile.follows_count,
                    "posts": profile.posts_count,
                    "created_at": profile.created_at,
                }
            )
        time.sleep(0.1)
    covariates = pd.DataFrame(rows).set_index("handle")
    covariates["created_at"] = pd.to_datetime(
        covariates["created_at"], utc=True, format="ISO8601"
    )
    covariates["account_age_days"] = (
        pd.Timestamp.now(tz="UTC") - covariates["created_at"]
    ).dt.days
    return covariates
