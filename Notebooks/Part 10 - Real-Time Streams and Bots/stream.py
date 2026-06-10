"""Jetstream collection helpers for the bluesky-datascience tutorials.

This module is developed step-by-step in "Part 10 - Real-Time Streams and
Bots.ipynb". It provides small building blocks for collecting a bounded
sample of live network events from Bluesky's Jetstream service:

* :func:`build_jetstream_url` — compose a Jetstream subscribe URL with
  ``wantedCollections`` and ``wantedDids`` filters.
* :func:`collect_events` — an ``async`` function that connects to the
  websocket, collects events for a fixed duration (with a hard cap on the
  number of events), and returns them as a list of plain dictionaries.
* :func:`post_features` — extract a minimal, content-free set of features
  from a post event (pseudonymous author, timestamp, language, is-reply,
  has-embed) for the data-minimization examples.
* :func:`hash_did` — pseudonymize a DID with a truncated SHA-256 digest.

Every collection is bounded twice (by time *and* by a maximum event count)
so a notebook cell can never accidentally drink from the firehose forever.
"""

import asyncio
import hashlib
import json
import time

import websockets

# Jetstream is operated by Bluesky and mirrors the relay firehose as
# friendly JSON. Several public instances exist; this one is geographically
# close to the main relay. See https://docs.bsky.app/blog/jetstream and
# https://github.com/bluesky-social/jetstream for the full list.
JETSTREAM_URL = "wss://jetstream2.us-east.bsky.network/subscribe"

# The three record collections this tutorial monitors.
DEFAULT_COLLECTIONS = (
    "app.bsky.feed.post",
    "app.bsky.feed.like",
    "app.bsky.graph.follow",
)


def build_jetstream_url(
    wanted_collections=(),
    wanted_dids=(),
    base_url=JETSTREAM_URL,
):
    """Compose a Jetstream subscribe URL with optional server-side filters.

    Jetstream filters on the server, so asking only for the collections you
    need saves bandwidth for you *and* for the operator. ``wantedCollections``
    accepts NSIDs like ``app.bsky.feed.post`` (and trailing wildcards like
    ``app.bsky.graph.*``); ``wantedDids`` restricts the stream to specific
    accounts (up to 10,000 DIDs). With no filters you receive every event on
    the network.
    """
    params = [f"wantedCollections={c}" for c in wanted_collections]
    params += [f"wantedDids={d}" for d in wanted_dids]
    if params:
        return base_url + "?" + "&".join(params)
    return base_url


async def collect_events(
    duration_seconds=60,
    wanted_collections=DEFAULT_COLLECTIONS,
    max_events=20_000,
    base_url=JETSTREAM_URL,
    progress_every=15,
):
    """Collect Jetstream events for a fixed window and return them as dicts.

    Parameters
    ----------
    duration_seconds : float
        How long to stay connected. Collection always stops when this much
        wall-clock time has elapsed, even if the stream is quiet.
    wanted_collections : iterable of str
        Collection NSIDs to subscribe to (server-side filter). Pass an empty
        tuple to receive *all* commit events.
    max_events : int
        Hard cap on the number of events to keep. The Bluesky network can
        produce hundreds of events per second, so an unbounded collector is
        how you fill a laptop's memory by accident.
    base_url : str
        The Jetstream instance to connect to.
    progress_every : float
        Print a progress line every N seconds (0 disables printing).

    Returns
    -------
    list of dict
        Parsed JSON events, in arrival order. Each has ``did``, ``time_us``,
        ``kind``, and (for ``kind == "commit"``) a ``commit`` object with
        ``operation``, ``collection``, ``rkey``, and usually ``record``.
    """
    url = build_jetstream_url(wanted_collections, base_url=base_url)
    events = []
    start = time.monotonic()
    next_report = progress_every

    async with websockets.connect(url, max_size=None) as websocket:
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= duration_seconds or len(events) >= max_events:
                break
            try:
                # Never wait longer than the time we have left.
                remaining = duration_seconds - elapsed
                message = await asyncio.wait_for(
                    websocket.recv(), timeout=min(remaining, 5.0)
                )
            except asyncio.TimeoutError:
                continue  # quiet moment on the stream; check the clock again
            events.append(json.loads(message))

            if progress_every and elapsed >= next_report:
                rate = len(events) / elapsed
                print(
                    f"  {elapsed:5.1f}s: {len(events):>6,} events "
                    f"({rate:,.0f}/s)"
                )
                next_report += progress_every

    elapsed = time.monotonic() - start
    if progress_every:
        print(
            f"Done: {len(events):,} events in {elapsed:.1f}s "
            f"({len(events) / elapsed:,.0f} events/second)"
        )
    return events


def hash_did(did, length=12):
    """Pseudonymize a DID with a truncated SHA-256 digest.

    The same DID always maps to the same digest (so you can still count
    distinct authors in a saved sample), but the digest cannot be reversed
    into the DID. Note this is pseudonymization, not anonymization: anyone
    with a candidate DID can hash it and check for a match, so treat hashed
    identifiers as sensitive when the behavior they index is sensitive.
    """
    return hashlib.sha256(did.encode("utf-8")).hexdigest()[:length]


def post_features(event):
    """Extract minimal, content-free features from a Jetstream post event.

    Returns a dict with a pseudonymous author hash, the event timestamp,
    declared language, whether the post is a reply, and whether/what kind of
    media or link is embedded — and deliberately *not* the post text. Returns
    ``None`` for events that are not newly created posts.
    """
    commit = event.get("commit", {})
    if (
        event.get("kind") != "commit"
        or commit.get("operation") != "create"
        or commit.get("collection") != "app.bsky.feed.post"
    ):
        return None
    record = commit.get("record", {})
    langs = record.get("langs") or []
    embed_type = (record.get("embed") or {}).get("$type")
    has_image = embed_type in (
        "app.bsky.embed.images",
        "app.bsky.embed.video",
    ) or (
        embed_type == "app.bsky.embed.recordWithMedia"
        and "images" in str(record["embed"].get("media", {}).get("$type", ""))
    )
    return {
        "author_hash": hash_did(event["did"]),
        "timestamp_us": event["time_us"],
        "lang": langs[0] if langs else None,
        "is_reply": record.get("reply") is not None,
        "has_embed": embed_type is not None,
        "embed_type": embed_type,
        "has_image": has_image,
    }
