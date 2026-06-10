"""Minimal reply-bot building blocks for the bluesky-datascience tutorials.

This module is developed step-by-step in "Part 10 - Real-Time Streams and
Bots.ipynb". It implements a complete, deliberately boring bot design:

1. :func:`check_notifications` — poll the authenticated account's
   notifications (mentions, replies, likes, follows, ...).
2. :func:`filter_mentions` — keep only ``mention`` notifications.
3. :func:`build_reply` — a *pure function* mapping mention text to reply
   text (or ``None`` to stay silent). All of the bot's "intelligence" lives
   here, which makes it trivially testable without any network access.
4. :func:`reply_refs` — construct the ``ReplyRef`` (root + parent strong
   references) that threads a reply correctly under the mention.
5. :func:`run_bot_once` — one polling cycle tying it all together, with
   deduplication (never answer the same notification twice) and rate
   limiting (a cap per cycle and a pause between sends).

Everything that *writes* to the network requires an authenticated client and
is opt-in: ``run_bot_once`` defaults to ``dry_run=True``, which prints what
it would send instead of sending it.
"""

import json
import time
from pathlib import Path

from atproto import models

# A reply-bot should answer a mention once, not every time it polls. We
# persist the URIs of already-answered notifications to a small JSON file so
# deduplication survives restarts.
ANSWERED_PATH = Path("data/answered_notifications.json")

# Rate limiting: stay far below the PDS write limits (see the notebook's
# section on Bluesky's points system) and avoid flooding anyone's thread.
MAX_REPLIES_PER_RUN = 5
SECONDS_BETWEEN_REPLIES = 5.0

# Disclosure: every reply ends with this so nobody mistakes the bot for a
# human. Put the same statement in the bot account's display name or bio.
DISCLOSURE = "\n\n[I am an automated account: bot run by @brianckeegan.com]"


def check_notifications(client, limit=50):
    """Return the latest notifications for the authenticated account.

    Uses ``app.bsky.notification.listNotifications``, which only works with
    an authenticated client — notifications are private to the account.
    Each notification has a ``reason`` (``mention``, ``reply``, ``like``,
    ``follow``, ``repost``, ``quote``), the ``uri``/``cid`` of the triggering
    record, and the record itself.
    """
    response = client.app.bsky.notification.list_notifications(
        params={"limit": limit}
    )
    return response.notifications


def filter_mentions(notifications):
    """Keep only the notifications where someone @-mentioned the account."""
    return [n for n in notifications if n.reason == "mention"]


def build_reply(text):
    """Map the text of a mention to the text of a reply (or ``None``).

    This toy bot answers a single command: if the mention contains the word
    "ping", it replies "pong" with a timestamp. Anything else is ignored —
    a bot that replies to everything is indistinguishable from spam. Swap
    this function out to change what the bot does; because it is pure
    (text in, text out, no network), you can unit-test it exhaustively.
    """
    if "ping" in text.lower():
        stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        return f"pong! ({stamp})" + DISCLOSURE
    return None  # stay silent: not every mention deserves a reply


def reply_refs(notification):
    """Build the ReplyRef that threads a reply under ``notification``.

    A Bluesky reply carries two strong references (URI + CID): ``parent``
    is the post being answered, and ``root`` is the first post of the whole
    thread. If the mention is itself a reply, we reuse *its* root so our
    reply lands in the same thread; if the mention is a top-level post, it
    is its own root.
    """
    parent = models.ComAtprotoRepoStrongRef.Main(
        uri=notification.uri, cid=notification.cid
    )
    mention_reply = getattr(notification.record, "reply", None)
    if mention_reply is not None:
        root = models.ComAtprotoRepoStrongRef.Main(
            uri=mention_reply.root.uri, cid=mention_reply.root.cid
        )
    else:
        root = parent
    return models.AppBskyFeedPost.ReplyRef(root=root, parent=parent)


def load_answered(path=ANSWERED_PATH):
    """Load the set of already-answered notification URIs."""
    path = Path(path)
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()


def save_answered(answered, path=ANSWERED_PATH):
    """Persist the set of already-answered notification URIs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(answered)))


def run_bot_once(client, dry_run=True, answered_path=ANSWERED_PATH):
    """Run one polling cycle: fetch mentions, reply to new ones, log them.

    With ``dry_run=True`` (the default) the bot prints what it *would* post
    instead of posting. Set ``dry_run=False`` only on a clearly-disclosed
    bot account. Returns the number of replies sent (or simulated).

    Schedule this function — with cron, GitHub Actions, or a ``while`` loop
    that sleeps — rather than streaming, unless you truly need second-level
    latency. Polling once a minute is gentle and plenty for most bots.
    """
    answered = load_answered(answered_path)
    mentions = filter_mentions(check_notifications(client))
    print(f"{len(mentions)} mention(s) in the latest notifications")

    replies = 0
    for mention in mentions:
        if mention.uri in answered:
            continue  # dedupe: we already handled this one
        if replies >= MAX_REPLIES_PER_RUN:
            print("Reply cap reached for this cycle; the rest can wait.")
            break

        reply_text = build_reply(mention.record.text)
        if reply_text is None:
            answered.add(mention.uri)  # considered, declined: don't revisit
            continue

        if dry_run:
            print(f"[dry run] would reply to {mention.uri}:\n{reply_text}\n")
        else:
            client.send_post(text=reply_text, reply_to=reply_refs(mention))
            time.sleep(SECONDS_BETWEEN_REPLIES)  # rate limit between writes
        answered.add(mention.uri)
        replies += 1

    if not dry_run:
        save_answered(answered, answered_path)
    return replies
