"""Helpers for collecting and analyzing reply cascades on Bluesky.

Used by "Part 04 - Threads Engagement and Diffusion.ipynb". The workflow is:

1. ``lenient_query`` — call a read endpoint and parse the response without
   crashing when Bluesky ships record types newer than the installed SDK.
2. ``fetch_author_posts`` — paginate an account's feed into tidy per-post
   engagement rows.
3. ``thread_to_graph`` — recursively parse the nested thread view returned by
   ``app.bsky.feed.getPostThread`` into a NetworkX ``DiGraph`` of reply edges.
4. ``fetch_thread_graph`` — repeatedly re-query truncated branches of a large
   thread to recover as much of the cascade as a request budget allows.
5. Cascade metrics — ``cascade_summary``, ``depth_profile``, and
   ``structural_virality`` (Goel et al. 2016).
6. ``radial_tree_positions`` — a graphviz-free layered layout for drawing
   reply trees with Matplotlib.
7. ``fetch_likes``, ``fetch_reposters``, ``fetch_quotes`` — paginated, capped
   collection of who engaged with a post.
8. ``plot_ccdf`` — the log-log complementary CDF plot used to inspect
   heavy-tailed engagement distributions.

All collection functions are polite to the API: they sleep between paginated
requests and cap how many requests they make.
"""

import time

import networkx as nx
import numpy as np
import pandas as pd
from atproto_client import models
from atproto_client.models.utils import get_or_create

SLEEP = 0.1  # polite pause between consecutive API calls, in seconds
PAGE_SIZE = 100  # the maximum records per page for the feed/likes endpoints

# The nested thread view distinguishes three kinds of nodes by their $type.
THREAD_VIEW_POST = "app.bsky.feed.defs#threadViewPost"
NOT_FOUND_POST = "app.bsky.feed.defs#notFoundPost"
BLOCKED_POST = "app.bsky.feed.defs#blockedPost"

# Request/response models for the endpoints this notebook reads, keyed by
# their XRPC lexicon name (NSID).
LEXICONS = {
    "app.bsky.feed.getAuthorFeed": (
        models.AppBskyFeedGetAuthorFeed.Params,
        models.AppBskyFeedGetAuthorFeed.Response,
    ),
    "app.bsky.feed.getPostThread": (
        models.AppBskyFeedGetPostThread.Params,
        models.AppBskyFeedGetPostThread.Response,
    ),
    "app.bsky.feed.getLikes": (
        models.AppBskyFeedGetLikes.Params,
        models.AppBskyFeedGetLikes.Response,
    ),
    "app.bsky.feed.getRepostedBy": (
        models.AppBskyFeedGetRepostedBy.Params,
        models.AppBskyFeedGetRepostedBy.Response,
    ),
    "app.bsky.feed.getQuotes": (
        models.AppBskyFeedGetQuotes.Params,
        models.AppBskyFeedGetQuotes.Response,
    ),
}


def lenient_query(client, nsid, **params):
    """Call a read endpoint and parse the response leniently.

    The atproto SDK normally validates every response against the lexicon
    models bundled with the installed version. Bluesky ships new record types
    (new embed views, for example) faster than SDK releases, so strict
    validation can raise a ``ModelError`` on perfectly good data. This helper
    requests the raw JSON with ``client.invoke_query`` and parses it with
    ``strict=False``: when the response matches the SDK's models you get the
    usual typed object, and when it contains something newer you get a
    ``DotDict`` that supports the same snake_case dot access
    (``post.reply_count``, ``thread.replies``, ...).
    """
    params_model, response_model = LEXICONS[nsid]
    response = client.invoke_query(
        nsid, params=params_model(**params), output_encoding="application/json"
    )
    return get_or_create(response.content, response_model, strict=False)


def _get(node, attribute, default=None):
    """``getattr`` that tolerates both typed models and DotDict responses."""
    try:
        value = getattr(node, attribute)
    except (AttributeError, KeyError):
        return default
    return default if value is None else value


# ---------------------------------------------------------------------------
# Per-post engagement rows from an author feed
# ---------------------------------------------------------------------------

def feed_item_to_row(item):
    """Flatten one author-feed item into a dict of engagement counts."""
    post = item.post
    return {
        "uri": post.uri,
        "author_handle": post.author.handle,
        "created_at": _get(post.record, "created_at"),
        "text": _get(post.record, "text", ""),
        "is_repost": _get(item, "reason") is not None,
        "is_reply": _get(post.record, "reply") is not None,
        "reply_count": _get(post, "reply_count", 0),
        "like_count": _get(post, "like_count", 0),
        "repost_count": _get(post, "repost_count", 0),
        "quote_count": _get(post, "quote_count", 0),
    }


def fetch_author_posts(client, actor, max_posts=100, sleep=SLEEP):
    """Return up to ``max_posts`` recent feed items for ``actor`` as rows.

    Paginates ``app.bsky.feed.getAuthorFeed`` with cursors (newest first) and
    flattens every item with :func:`feed_item_to_row`. The rows include
    reposts and replies, flagged with ``is_repost``/``is_reply`` so the
    notebook can filter down to original posts.
    """
    rows, cursor = [], None
    while len(rows) < max_posts:
        limit = min(PAGE_SIZE, max_posts - len(rows))
        response = lenient_query(
            client, "app.bsky.feed.getAuthorFeed",
            actor=actor, limit=limit, cursor=cursor,
        )
        rows += [feed_item_to_row(item) for item in response.feed]
        cursor = response.cursor
        if cursor is None or not response.feed:
            break
        time.sleep(sleep)
    return rows


# ---------------------------------------------------------------------------
# Reply trees
# ---------------------------------------------------------------------------

def thread_to_graph(thread, graph=None, parent=None, depth=0):
    """Recursively parse a thread view into a directed reply tree.

    ``thread`` is the ``.thread`` attribute of a ``getPostThread`` response:
    a ``threadViewPost`` whose ``.replies`` list nests further thread views.
    Returns a NetworkX ``DiGraph`` whose nodes are post URIs with attributes
    ``handle``, ``did``, ``created_at``, ``like_count``, ``reply_count``, and
    ``depth`` (0 for the root). Edges point from each post to its replies —
    the direction the conversation grows.

    Deleted (``notFoundPost``) and blocked (``blockedPost``) nodes cannot be
    traversed; they are skipped and tallied in ``graph.graph['not_found']``
    and ``graph.graph['blocked']``. Nodes whose ``reply_count`` is positive
    but whose replies were not returned (the server truncates both the depth
    and the breadth of thread views) are marked ``truncated=True`` so
    :func:`fetch_thread_graph` can re-query them.
    """
    if graph is None:
        graph = nx.DiGraph(not_found=0, blocked=0)

    node_type = _get(thread, "py_type", "")
    if node_type == NOT_FOUND_POST:
        graph.graph["not_found"] += 1
        return graph
    if node_type == BLOCKED_POST:
        graph.graph["blocked"] += 1
        return graph
    if node_type != THREAD_VIEW_POST:  # an unknown node type — skip it
        return graph

    post = thread.post
    uri = post.uri
    if uri in graph:  # re-queried during expansion: keep the original depth
        depth = graph.nodes[uri]["depth"]
    replies = _get(thread, "replies", [])
    graph.add_node(
        uri,
        handle=post.author.handle,
        did=post.author.did,
        created_at=_get(post.record, "created_at"),
        like_count=_get(post, "like_count", 0),
        reply_count=_get(post, "reply_count", 0),
        depth=depth,
        truncated=_get(post, "reply_count", 0) > 0 and len(replies) == 0,
    )
    if parent is not None:
        graph.add_edge(parent, uri)
    for reply in replies:
        thread_to_graph(reply, graph=graph, parent=uri, depth=depth + 1)
    return graph


def fetch_thread_graph(client, uri, depth=6, max_requests=40, sleep=SLEEP,
                       verbose=True):
    """Collect as much of a reply tree as ``max_requests`` queries allow.

    A single ``getPostThread`` call truncates deep and busy threads, so this
    function works like a breadth-first crawler: parse the root response with
    :func:`thread_to_graph`, then repeatedly re-query nodes that were marked
    ``truncated`` (they report replies the server did not return) until the
    frontier is empty or the request budget is spent.

    The result is still a *sample* of very large cascades — the server also
    caps how many replies it returns per node, and that breadth truncation
    cannot be recovered by re-querying — so the notebook reports coverage
    alongside every metric.
    """
    graph = None
    queried = set()
    frontier = [uri]
    requests_made = 0
    while frontier and requests_made < max_requests:
        node_uri = frontier.pop(0)
        if node_uri in queried:
            continue
        queried.add(node_uri)
        response = lenient_query(
            client, "app.bsky.feed.getPostThread", uri=node_uri, depth=depth
        )
        requests_made += 1
        graph = thread_to_graph(response.thread, graph=graph)
        frontier += [
            node for node, data in graph.nodes(data=True)
            if data.get("truncated") and node not in queried
        ]
        if verbose and requests_made % 10 == 0:
            print(f"  {requests_made} requests: {graph.number_of_nodes()} posts, "
                  f"{len(frontier)} truncated branches left")
        time.sleep(sleep)
    graph.graph["requests_made"] = requests_made
    graph.graph["frontier_remaining"] = len(set(frontier) - queried)
    return graph


# ---------------------------------------------------------------------------
# Cascade metrics
# ---------------------------------------------------------------------------

def depth_profile(graph):
    """Number of posts at each depth of the tree, as a ``pd.Series``."""
    depths = [data["depth"] for _, data in graph.nodes(data=True)]
    return pd.Series(depths).value_counts().sort_index().rename("posts")


def structural_virality(graph):
    """Mean pairwise distance between all nodes of the (undirected) tree.

    Goel, Anderson, Hofman, & Watts (2016) call this *structural virality*:
    it is low for star-shaped "broadcast" cascades, where everyone responds
    directly to the source, and high for long, branching "viral" chains.
    A single-node cascade has no pairs, so it returns ``nan``.
    """
    if graph.number_of_nodes() < 2:
        return float("nan")
    return nx.average_shortest_path_length(graph.to_undirected(as_view=True))


def cascade_summary(graph):
    """Size, depth, breadth, and structural virality of a reply tree."""
    profile = depth_profile(graph)
    non_root_depths = [d for d in profile.index.repeat(profile.values) if d > 0]
    return {
        "size": graph.number_of_nodes(),
        "max_depth": int(profile.index.max()),
        "mean_depth": (sum(non_root_depths) / len(non_root_depths)
                       if non_root_depths else 0.0),
        "max_breadth": int(profile.max()),
        "structural_virality": structural_virality(graph),
        "unique_authors": len({d["did"] for _, d in graph.nodes(data=True)}),
        "deleted_or_blocked": graph.graph.get("not_found", 0)
                              + graph.graph.get("blocked", 0),
    }


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def radial_tree_positions(graph, root):
    """Layout a tree radially: radius = depth, angle = position in the tree.

    A graphviz-free alternative to ``dot``/``twopi`` layouts. Leaves are
    spaced evenly around the circle in depth-first order and every internal
    node sits at the mean angle of its children, so subtrees occupy
    contiguous wedges. Returns ``{node: (x, y)}`` for ``nx.draw``.
    """
    import math

    angles = {}
    next_leaf = [0]
    leaf_count = sum(1 for n in graph if graph.out_degree(n) == 0) or 1

    def assign(node):
        children = list(graph.successors(node))
        if not children:
            angles[node] = 2 * math.pi * next_leaf[0] / leaf_count
            next_leaf[0] += 1
        else:
            for child in children:
                assign(child)
            angles[node] = sum(angles[c] for c in children) / len(children)

    assign(root)
    return {
        node: (data["depth"] * math.cos(angles[node]),
               data["depth"] * math.sin(angles[node]))
        for node, data in graph.nodes(data=True)
    }


# ---------------------------------------------------------------------------
# Who engaged: likes, reposts, quotes
# ---------------------------------------------------------------------------

def fetch_likes(client, uri, max_pages=35, sleep=SLEEP):
    """Return the likes on a post (newest first), capped at ``max_pages``.

    Each row records who liked (``did``, ``handle``) and when: ``created_at``
    is when the liker's client created the like record and ``indexed_at`` is
    when the AppView saw it.
    """
    rows, cursor, pages = [], None, 0
    while pages < max_pages:
        response = lenient_query(
            client, "app.bsky.feed.getLikes", uri=uri, limit=PAGE_SIZE, cursor=cursor
        )
        rows += [
            {
                "did": like.actor.did,
                "handle": like.actor.handle,
                "created_at": like.created_at,
                "indexed_at": like.indexed_at,
            }
            for like in response.likes
        ]
        cursor = response.cursor
        pages += 1
        if cursor is None or not response.likes:
            break
        time.sleep(sleep)
    return rows


def fetch_reposters(client, uri, max_pages=5, sleep=SLEEP):
    """Return who reposted a post, capped at ``max_pages``.

    ``getRepostedBy`` returns profile views only — unlike likes, repost
    timestamps are not exposed by this endpoint.
    """
    rows, cursor, pages = [], None, 0
    while pages < max_pages:
        response = lenient_query(
            client, "app.bsky.feed.getRepostedBy",
            uri=uri, limit=PAGE_SIZE, cursor=cursor,
        )
        rows += [
            {"did": profile.did, "handle": profile.handle}
            for profile in response.reposted_by
        ]
        cursor = response.cursor
        pages += 1
        if cursor is None or not response.reposted_by:
            break
        time.sleep(sleep)
    return rows


def fetch_quotes(client, uri, max_pages=2, sleep=SLEEP):
    """Return quote posts referencing a post, capped at ``max_pages``."""
    rows, cursor, pages = [], None, 0
    while pages < max_pages:
        response = lenient_query(
            client, "app.bsky.feed.getQuotes", uri=uri, limit=50, cursor=cursor
        )
        rows += [
            {
                "uri": post.uri,
                "did": post.author.did,
                "handle": post.author.handle,
                "created_at": _get(post.record, "created_at"),
                "like_count": _get(post, "like_count", 0),
                "repost_count": _get(post, "repost_count", 0),
                "reply_count": _get(post, "reply_count", 0),
            }
            for post in response.posts
        ]
        cursor = response.cursor
        pages += 1
        if cursor is None or not response.posts:
            break
        time.sleep(sleep)
    return rows


# ---------------------------------------------------------------------------
# Heavy-tailed distributions
# ---------------------------------------------------------------------------

def plot_ccdf(values, ax, label=None, **plot_kwargs):
    """Plot the complementary CDF of ``values`` on log-log axes.

    The CCDF shows, for each engagement level *x*, the fraction of posts that
    received *at least* x; on log-log axes a heavy-tailed distribution falls
    along a slowly decaying (roughly straight) line, while a thin-tailed one
    plunges. Zeros are dropped because log(0) is undefined — the text should
    report how many posts had no engagement at all.
    """
    series = pd.Series(values)
    positive = series[series > 0].sort_values().to_numpy()
    n = len(series)
    # P(count >= x_i) for the i-th smallest positive value: everything from
    # position i to the end of the sorted array is at least x_i.
    ccdf = (len(positive) - np.arange(len(positive))) / n
    ax.loglog(positive, ccdf, marker=".", linestyle="none",
              label=label, **plot_kwargs)
    ax.set_xlabel("Engagement count $x$")
    ax.set_ylabel(r"P(count $\geq x$)")
    return ax
