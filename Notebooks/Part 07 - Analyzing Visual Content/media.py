"""Helpers for collecting and classifying visual media in Bluesky posts.

Part 07 of the bluesky-datascience tutorials studies images, alt text, and
link cards. Embed lexicons are the fastest-moving part of the AT Protocol --
new types like ``app.bsky.embed.gallery`` appear before SDK releases can model
them -- so these helpers read the public AppView's raw JSON with ``requests``
instead of relying on the SDK's typed models. Every function works without
authentication.
"""

import hashlib
import io
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image

APPVIEW = "https://public.api.bsky.app"

# The embed lexicon families a post (or its view) can carry. ``gallery`` is a
# 2025 addition (multi-image carousels) that older SDKs cannot parse.
EMBED_CLASSES = ("images", "video", "external", "record", "record_with_media", "none")

_session = requests.Session()
_session.headers["User-Agent"] = "bluesky-datascience-part07 (tutorial; polite)"


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def get_author_feed_page(actor, cursor=None, limit=100, filter="posts_no_replies"):
    """Fetch one page of ``app.bsky.feed.getAuthorFeed`` as raw JSON.

    Returns the decoded response dict with ``feed`` (a list of feed items)
    and an optional ``cursor`` for the next page.
    """
    params = {"actor": actor, "limit": limit, "filter": filter}
    if cursor:
        params["cursor"] = cursor
    response = _session.get(
        f"{APPVIEW}/xrpc/app.bsky.feed.getAuthorFeed", params=params, timeout=30
    )
    response.raise_for_status()
    return response.json()


def collect_author_posts(actor, max_posts=150, sleep=0.1, filter="posts_no_replies"):
    """Collect up to ``max_posts`` original posts by ``actor``.

    Paginates with cursors, sleeps ``sleep`` seconds between pages, and skips
    reposts (items with a ``reason``) so that every returned post was actually
    authored by ``actor`` -- essential when we attribute media practices like
    alt-text provision to specific accounts. Returns a list of post dicts.
    """
    posts, cursor = [], None
    while len(posts) < max_posts:
        page = get_author_feed_page(actor, cursor=cursor, filter=filter)
        for item in page.get("feed", []):
            if item.get("reason"):  # a repost of someone else's content
                continue
            posts.append(item["post"])
            if len(posts) >= max_posts:
                break
        cursor = page.get("cursor")
        if not cursor:
            break
        time.sleep(sleep)
    return posts


# ---------------------------------------------------------------------------
# Embed classification
# ---------------------------------------------------------------------------

def _normalize_embed_type(type_string):
    """Map a ``$type`` like ``app.bsky.embed.images#view`` to a short class."""
    if not type_string:
        return "none"
    name = type_string.removeprefix("app.bsky.embed.").split("#")[0]
    if name == "recordWithMedia":
        return "record_with_media"
    if name == "gallery":  # multi-image carousel; semantically an image embed
        return "images"
    if name in EMBED_CLASSES:
        return name
    return "other:" + name  # future lexicons we have not seen yet

def classify_embed(post):
    """Classify a post dict's embed into one of EMBED_CLASSES.

    Prefers the hydrated *view* (``post["embed"]``), which is what clients
    render, and falls back to the author's raw record (``post["record"]
    ["embed"]``) when the AppView did not hydrate a view (e.g. a quoted post
    that was deleted or blocked).
    """
    view = post.get("embed") or {}
    record_embed = (post.get("record") or {}).get("embed") or {}
    type_string = view.get("$type") or record_embed.get("$type")
    return _normalize_embed_type(type_string)


def iter_images(post):
    """Yield one dict per image in a post's embed view.

    Handles ``images#view``, ``gallery#view``, and the media half of
    ``recordWithMedia#view``. Each dict has ``thumb``, ``fullsize``, ``alt``,
    ``width``, and ``height`` (None when the embed lacks an aspectRatio).
    """
    view = post.get("embed") or {}
    view_type = view.get("$type", "")
    if view_type.startswith("app.bsky.embed.recordWithMedia"):
        view = view.get("media") or {}
        view_type = view.get("$type", "")

    if view_type.startswith("app.bsky.embed.images"):
        items, thumb_key = view.get("images", []), "thumb"
    elif view_type.startswith("app.bsky.embed.gallery"):
        items, thumb_key = view.get("items", []), "thumbnail"
    else:
        return

    for item in items:
        ratio = item.get("aspectRatio") or {}
        yield {
            "thumb": item.get(thumb_key),
            "fullsize": item.get("fullsize"),
            "alt": item.get("alt", ""),
            "width": ratio.get("width"),
            "height": ratio.get("height"),
        }


def external_info(post):
    """Return the link card (uri, domain, title, description) or None."""
    view = post.get("embed") or {}
    if view.get("$type", "").startswith("app.bsky.embed.recordWithMedia"):
        view = view.get("media") or {}
    if not view.get("$type", "").startswith("app.bsky.embed.external"):
        return None
    card = view.get("external") or {}
    uri = card.get("uri", "")
    return {
        "uri": uri,
        "domain": urlparse(uri).netloc.lower().removeprefix("www."),
        "title": card.get("title", ""),
        "description": card.get("description", ""),
    }


def post_row(post):
    """Flatten one post dict into a tidy row for a DataFrame."""
    images = list(iter_images(post))
    alts = [img["alt"].strip() for img in images]
    card = external_info(post)
    record = post.get("record") or {}
    return {
        "uri": post.get("uri"),
        "author": (post.get("author") or {}).get("handle"),
        "created_at": record.get("createdAt"),
        "text_length": len(record.get("text") or ""),
        "embed_class": classify_embed(post),
        "n_images": len(images),
        "n_images_with_alt": sum(1 for alt in alts if alt),
        "alt_text": " | ".join(alt for alt in alts if alt),
        "external_domain": card["domain"] if card else None,
        "external_uri": card["uri"] if card else None,
        "like_count": post.get("likeCount", 0),
        "repost_count": post.get("repostCount", 0),
    }


# ---------------------------------------------------------------------------
# Image corpus
# ---------------------------------------------------------------------------

def download_thumbnails(posts, out_dir, max_images=12, max_per_post=2, max_px=256, sleep=0.5):
    """Download up to ``max_images`` thumbnails into ``out_dir``.

    Fetches each image's *thumbnail* rendition (never the full-size blob),
    resizes it to at most ``max_px`` on a side, and saves it as JPEG under a
    content-hash filename -- identical images dedupe automatically. Takes at
    most ``max_per_post`` images from any single post so one large carousel
    cannot dominate a small corpus, and sleeps ``sleep`` seconds between
    downloads to be polite to the CDN. Returns a manifest: one dict per saved
    image with the post URI, alt text, dimensions, and file path.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest, seen_hashes = [], set()
    for post in posts:
        saved_from_post = 0
        for img in iter_images(post):
            if len(manifest) >= max_images:
                return manifest
            if saved_from_post >= max_per_post:
                break
            if not img["thumb"]:
                continue
            try:
                response = _session.get(img["thumb"], timeout=30)
                response.raise_for_status()
            except requests.RequestException as error:
                print(f"Skipping {img['thumb'][:60]}...: {error}")
                continue
            digest = hashlib.sha256(response.content).hexdigest()[:16]
            if digest in seen_hashes:  # already saved this exact image
                continue
            seen_hashes.add(digest)
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            image.thumbnail((max_px, max_px))
            file_path = out_dir / f"{digest}.jpg"
            image.save(file_path, "JPEG", quality=80)
            manifest.append({
                "post_uri": post.get("uri"),
                "author": (post.get("author") or {}).get("handle"),
                "alt_text": img["alt"],
                "orig_width": img["width"],
                "orig_height": img["height"],
                "saved_width": image.width,
                "saved_height": image.height,
                "file": str(file_path),
            })
            saved_from_post += 1
            time.sleep(sleep)
    return manifest
