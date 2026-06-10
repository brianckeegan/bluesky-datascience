"""Helpers for Part 02 — facet extraction and snowball collection on Bluesky.

The functions here do two jobs for the tutorial notebook:

1. **Facet extraction.** Bluesky posts store their "rich text" — mentions,
   hashtags, and links — in a ``facets`` list on the post record rather than
   parsing them out of the text. ``extract_mentions``, ``extract_tags``, and
   ``extract_links`` pull those features out of a hydrated post view.

2. **Snowball collection.** ``fetch_author_posts`` pages politely through an
   account's feed, ``count_engaged_accounts`` ranks the accounts a set of
   posts mentions or replies to (the "edges" we snowball along), and
   ``post_to_row`` flattens a post into a tidy dictionary for a DataFrame.

All functions take the hydrated ``PostView`` objects returned by endpoints
like ``get_author_feed``, ``get_posts``, and ``searchPosts``.
"""

import time
from collections import Counter

# The py_type identifiers for the three rich-text facet features
# defined by the app.bsky.richtext.facet lexicon.
FACET_MENTION = "app.bsky.richtext.facet#mention"
FACET_TAG = "app.bsky.richtext.facet#tag"
FACET_LINK = "app.bsky.richtext.facet#link"


def iter_facet_features(post):
    """Yield every facet feature in a post's record (nothing if no facets)."""
    record = getattr(post, "record", None)
    for facet in getattr(record, "facets", None) or []:
        yield from facet.features


def extract_mentions(post):
    """Return the DIDs of accounts @-mentioned in a post's text, in order."""
    return [f.did for f in iter_facet_features(post) if f.py_type == FACET_MENTION]


def extract_tags(post):
    """Return the hashtags in a post's text, lowercased, in order."""
    return [f.tag.lower() for f in iter_facet_features(post) if f.py_type == FACET_TAG]


def extract_links(post):
    """Return the external link URLs in a post's text, in order."""
    return [f.uri for f in iter_facet_features(post) if f.py_type == FACET_LINK]


def extract_reply_parent(post):
    """Return the DID of the account a post replies to, or None.

    Reply references are AT-URIs like ``at://did:plc:.../app.bsky.feed.post/...``;
    the authority segment between ``at://`` and the first ``/`` is the DID of
    the account that authored the parent post.
    """
    reply = getattr(post.record, "reply", None)
    if reply is None:
        return None
    return reply.parent.uri.removeprefix("at://").split("/")[0]


def fetch_author_posts(client, actor, max_posts=100, max_pages=10, pause=0.1):
    """Collect up to ``max_posts`` original posts from an account's feed.

    Pages through ``get_author_feed`` with the cursor, sleeping ``pause``
    seconds between requests. Reposts (feed items with a ``reason``) are
    skipped because their text belongs to a different author; replies are
    kept. ``max_pages`` bounds the number of requests even when an account
    reposts so heavily that original posts are rare.
    """
    posts, cursor = [], None
    for _ in range(max_pages):
        response = client.get_author_feed(actor=actor, limit=100, cursor=cursor)
        for item in response.feed:
            if item.reason is None:  # skip reposts of other accounts' posts
                posts.append(item.post)
        cursor = response.cursor
        if cursor is None or len(posts) >= max_posts:
            break
        time.sleep(pause)
    return posts[:max_posts]


def count_engaged_accounts(posts, exclude=()):
    """Count the accounts a set of posts engages via mentions and replies.

    Returns a ``Counter`` mapping DIDs to the number of posts that either
    @-mention that account or reply to one of its posts. Each post counts an
    account at most once. DIDs in ``exclude`` (e.g. accounts already crawled)
    are skipped. On Bluesky, replying does not insert an @-mention into the
    text the way Twitter conventions did, so counting reply parents alongside
    mentions captures conversational ties that facets alone would miss.
    """
    counts = Counter()
    excluded = set(exclude)
    for post in posts:
        engaged = set(extract_mentions(post))
        parent = extract_reply_parent(post)
        if parent is not None:
            engaged.add(parent)
        engaged.discard(post.author.did)  # ignore self-mentions/self-threads
        for did in engaged - excluded:
            counts[did] += 1
    return counts


def post_to_row(post, wave=None):
    """Flatten a hydrated PostView into a dict for a tidy DataFrame row."""
    record = post.record
    return {
        "uri": post.uri,
        "cid": post.cid,
        "author_did": post.author.did,
        "author_handle": post.author.handle,
        "created_at": record.created_at,
        "text": record.text,
        "langs": list(record.langs or []),
        "is_reply": record.reply is not None,
        "like_count": post.like_count,
        "repost_count": post.repost_count,
        "reply_count": post.reply_count,
        "hashtags": extract_tags(post),
        "mentions": extract_mentions(post),
        "links": extract_links(post),
        "wave": wave,
    }
