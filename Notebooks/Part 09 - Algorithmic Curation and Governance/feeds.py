"""Helpers for auditing Bluesky's public curation and moderation infrastructure.

This module is developed step-by-step in "Part 09 - Algorithmic Curation and
Governance.ipynb". It provides four families of building blocks:

* **Raw XRPC collection** — :func:`xrpc_get`, :func:`fetch_feed_posts`, and
  :func:`fetch_list_feed_posts` call the public AppView's HTTP endpoints
  directly with ``requests`` and return plain JSON dictionaries. We bypass the
  SDK's typed models here because feed responses can contain brand-new embed
  types (lexicons evolve faster than SDK releases), and a strict model
  validator that crashes on one unfamiliar post would cost us the whole page.
* **Flattening** — :func:`posts_to_dataframe` turns nested feed items into a
  tidy, deliberately *slim* DataFrame (no post text: a composition audit does
  not need it, and data minimization is good research hygiene).
* **Composition metrics** — :func:`feed_composition` and
  :func:`author_jaccard` compute the audit measures compared across feeds:
  author concentration (top-10 share, HHI, Gini), recency, engagement,
  language mix, media share, and audience overlap.
* **Labels** — :func:`query_labels` queries a labeler service's
  ``com.atproto.label.queryLabels`` endpoint in polite batches, degrading
  gracefully if the service is unreachable.
"""

import time

import numpy as np
import pandas as pd
import requests

PUBLIC_APPVIEW = "https://public.api.bsky.app"
BSKY_MOD_SERVICE = "https://mod.bsky.app"

# DIDs used throughout Part 09
BSKY_APP_DID = "did:plc:z72i7hdynmk6r22z27h6tvur"  # the official bsky.app account
BSKY_MOD_DID = "did:plc:ar7c4by46qjdydhdevvrndac"  # the Bluesky Moderation Service labeler


def xrpc_get(endpoint, params=None, base_url=PUBLIC_APPVIEW, timeout=30):
    """Call a read-only XRPC endpoint directly and return the parsed JSON.

    Parameters
    ----------
    endpoint : str
        The NSID of the lexicon method, e.g. ``"app.bsky.feed.getFeed"``.
    params : dict, optional
        Query-string parameters. List values (like ``uriPatterns``) are
        repeated, which is exactly what XRPC expects.
    base_url : str
        The service host. Defaults to the public AppView; pass a labeler's
        URL (e.g. ``https://mod.bsky.app``) for label queries.

    Raises ``requests.HTTPError`` on non-2xx responses, so callers can decide
    how to handle feeds that refuse unauthenticated requests.
    """
    response = requests.get(f"{base_url}/xrpc/{endpoint}", params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _paginate_feed(endpoint, param_name, uri, target, page_size, delay, max_pages):
    """Shared cursor loop behind fetch_feed_posts / fetch_list_feed_posts."""
    items = []
    cursor = None
    for _ in range(max_pages):
        params = {param_name: uri, "limit": page_size}
        if cursor is not None:
            params["cursor"] = cursor
        page = xrpc_get(endpoint, params)
        items.extend(page.get("feed", []))
        cursor = page.get("cursor")
        if len(items) >= target or not cursor:
            break
        time.sleep(delay)
    return items[: target if len(items) > target else len(items)]


def fetch_feed_posts(feed_uri, target=150, page_size=100, delay=0.1, max_pages=10):
    """Collect ~``target`` posts from a published custom feed.

    Pages through ``app.bsky.feed.getFeed`` with a cursor, sleeping
    ``delay`` seconds between requests, and returns the raw feed items
    (dicts with a ``post`` key and sometimes a ``reason`` key).

    Note that feed generators may return slightly fewer posts per page than
    requested (the AppView drops posts it cannot hydrate), and *personalized*
    feeds (e.g. Popular With Friends) refuse unauthenticated requests
    entirely — expect an HTTPError for those.
    """
    return _paginate_feed("app.bsky.feed.getFeed", "feed", feed_uri, target, page_size, delay, max_pages)


def fetch_list_feed_posts(list_uri, target=150, page_size=100, delay=0.1, max_pages=10):
    """Collect ~``target`` posts from a list feed (``app.bsky.feed.getListFeed``).

    A list feed is pure reverse chronology over the list's members — no
    ranking model at all — which makes it a useful "no algorithm" baseline
    for feed audits.
    """
    return _paginate_feed("app.bsky.feed.getListFeed", "list", list_uri, target, page_size, delay, max_pages)


def _classify_embed(embed):
    """Return (embed_type, has_media) for a post view's embed dict (or None)."""
    if not embed:
        return None, False
    embed_type = embed.get("$type", "").replace("app.bsky.embed.", "").replace("#view", "")
    if embed_type == "recordWithMedia":
        media_type = (embed.get("media") or {}).get("$type", "")
        return embed_type, ("images" in media_type or "video" in media_type)
    return embed_type, embed_type in ("images", "video", "gallery")


def flatten_post(item, feed_name, retrieved_at):
    """Flatten one raw feed item into a slim dict of audit-relevant fields.

    Deliberately excludes the post text: composition metrics (who, when, how
    much engagement, what media) do not require content, and collecting less
    than you need is the data-minimization principle in action.
    """
    post = item["post"]
    record = post.get("record", {})
    langs = record.get("langs") or []
    embed_type, has_media = _classify_embed(post.get("embed"))
    return {
        "feed": feed_name,
        "uri": post["uri"],
        "author_did": post["author"]["did"],
        "author_handle": post["author"].get("handle"),
        "created_at": record.get("createdAt"),
        "indexed_at": post.get("indexedAt"),
        "retrieved_at": retrieved_at,
        "like_count": post.get("likeCount", 0),
        "repost_count": post.get("repostCount", 0),
        "reply_count": post.get("replyCount", 0),
        "quote_count": post.get("quoteCount", 0),
        "lang": langs[0] if langs else None,
        "embed_type": embed_type,
        "has_media": has_media,
        "text_chars": len(record.get("text") or ""),
        "via_repost": item.get("reason") is not None,
    }


def posts_to_dataframe(items, feed_name, retrieved_at):
    """Flatten a list of raw feed items into a tidy, deduplicated DataFrame.

    ``retrieved_at`` should be a timezone-aware ``datetime`` recorded at
    collection time; it is stored on every row so the archive documents its
    own collection date, and so post ages can be recomputed later.
    """
    df = pd.DataFrame([flatten_post(item, feed_name, retrieved_at) for item in items])
    df = df.drop_duplicates(subset="uri").reset_index(drop=True)
    for col in ("created_at", "indexed_at", "retrieved_at"):
        df[col] = pd.to_datetime(df[col], utc=True, format="ISO8601", errors="coerce")
    # Age of the post at the moment we retrieved it. Client-supplied
    # createdAt timestamps are occasionally bogus (future-dated); mask those.
    age = (df["retrieved_at"] - df["created_at"]).dt.total_seconds() / 3600
    df["age_hours"] = age.where(age >= 0)
    return df


def gini(counts):
    """Gini coefficient of a distribution of counts (0 = equal, →1 = concentrated)."""
    values = np.sort(np.asarray(counts, dtype=float))
    n = len(values)
    if n == 0 or values.sum() == 0:
        return np.nan
    cumulative = np.cumsum(values)
    return float((n + 1 - 2 * (cumulative / cumulative[-1]).sum()) / n)


def hhi(counts):
    """Herfindahl–Hirschman index of concentration (1/n = equal, 1 = monopoly)."""
    values = np.asarray(counts, dtype=float)
    total = values.sum()
    if total == 0:
        return np.nan
    shares = values / total
    return float((shares**2).sum())


def top_k_share(counts, k=10):
    """Share of all posts contributed by the k most prolific authors."""
    values = np.sort(np.asarray(counts, dtype=float))[::-1]
    total = values.sum()
    if total == 0:
        return np.nan
    return float(values[:k].sum() / total)


def feed_composition(df, group_col="feed"):
    """Compute the audit comparison table: one row of metrics per feed.

    Expects the DataFrame produced by :func:`posts_to_dataframe` (one row per
    post, with a ``feed`` column distinguishing the samples).
    """
    rows = []
    for feed_name, group in df.groupby(group_col, sort=False):
        author_counts = group["author_did"].value_counts()
        rows.append(
            {
                group_col: feed_name,
                "posts": len(group),
                "unique_authors": group["author_did"].nunique(),
                "top10_author_share": top_k_share(author_counts, k=10),
                "author_hhi": hhi(author_counts),
                "author_gini": gini(author_counts),
                "median_age_hours": group["age_hours"].median(),
                "p90_age_hours": group["age_hours"].quantile(0.9),
                "median_likes": group["like_count"].median(),
                "p90_likes": group["like_count"].quantile(0.9),
                "share_english": (group["lang"] == "en").mean(),
                "n_languages": group["lang"].nunique(),
                "media_share": group["has_media"].mean(),
                "median_text_chars": group["text_chars"].median(),
            }
        )
    return pd.DataFrame(rows).set_index(group_col)


def author_jaccard(df, group_col="feed"):
    """Jaccard overlap of author sets between every pair of feeds.

    Returns a symmetric DataFrame where cell (A, B) is
    ``|authors_A ∩ authors_B| / |authors_A ∪ authors_B|``.
    """
    author_sets = {name: set(group["author_did"]) for name, group in df.groupby(group_col, sort=False)}
    names = list(author_sets)
    matrix = pd.DataFrame(index=names, columns=names, dtype=float)
    for a in names:
        for b in names:
            union = author_sets[a] | author_sets[b]
            matrix.loc[a, b] = len(author_sets[a] & author_sets[b]) / len(union) if union else np.nan
    return matrix


def query_labels(uri_patterns, labeler_url=BSKY_MOD_SERVICE, batch_size=25, delay=0.2, max_requests=30):
    """Query a labeler service for labels on a list of URI patterns.

    Sends ``com.atproto.label.queryLabels`` requests in batches of
    ``batch_size`` patterns (exact ``at://`` URIs, DIDs, or wildcard patterns
    like ``at://did:plc:.../*``), capped at ``max_requests`` requests.

    Returns a list of label dicts. If the labeler is unreachable or errors
    mid-way, prints a warning and returns whatever was collected so far —
    moderation infrastructure is run by third parties and is allowed to be
    down without breaking the rest of the analysis.
    """
    labels = []
    batches = [uri_patterns[i : i + batch_size] for i in range(0, len(uri_patterns), batch_size)]
    for i, batch in enumerate(batches[:max_requests]):
        try:
            page = xrpc_get(
                "com.atproto.label.queryLabels",
                {"uriPatterns": batch, "limit": 250},
                base_url=labeler_url,
            )
        except requests.RequestException as error:
            print(f"Labeler unreachable on batch {i + 1}/{len(batches)} ({error}); returning partial results.")
            break
        labels.extend(page.get("labels", []))
        time.sleep(delay)
    return labels


def labels_to_dataframe(labels):
    """Tabulate raw label dicts into a DataFrame (empty-safe)."""
    columns = ["val", "uri", "src", "cts", "neg"]
    if not labels:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(labels)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    df["neg"] = df["neg"].fillna(False).astype(bool)
    return df[columns]
