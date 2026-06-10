"""Helpers for building a 1.5-degree ego network from Bluesky's follow graph.

Used by "Part 03 - Social Network Analysis.ipynb". The workflow is:

1. ``fetch_follows`` — paginate through an account's follows with cursors.
2. ``sample_alters`` — draw a seeded random sample of the ego's alters.
3. ``build_ego_network`` — crawl each sampled alter's follows and keep only
   the edges that stay inside {ego + sampled alters}, returning a NetworkX
   ``DiGraph``.
4. ``add_profile_attributes`` — decorate every node with profile metadata
   (handle, follower/follows/posts counts) using batched ``get_profiles``
   calls (25 actors per request).

All functions are polite to the API: they sleep between paginated requests
and cap how many pages they retrieve.
"""

import random
import time

import networkx as nx

PAGE_SIZE = 100  # the maximum the API allows per getFollows/getFollowers call
SLEEP = 0.1  # polite pause between consecutive API calls, in seconds
PROFILE_BATCH_SIZE = 25  # the maximum actors per getProfiles call


def fetch_follows(client, actor, max_pages=None, sleep=SLEEP, verbose=False):
    """Return the accounts ``actor`` follows, as a list of (did, handle) dicts.

    Paginates ``client.get_follows`` with cursors, newest follows first, until
    the cursor is exhausted or ``max_pages`` pages have been retrieved. Pass
    ``max_pages=2`` to truncate a crawl at roughly 200 follows per account.
    """
    follows, cursor, pages = [], None, 0
    while True:
        response = client.get_follows(actor=actor, limit=PAGE_SIZE, cursor=cursor)
        follows += [{"did": f.did, "handle": f.handle} for f in response.follows]
        cursor = response.cursor
        pages += 1
        if verbose:
            print(f"  page {pages}: {len(follows)} follows so far")
        if cursor is None or (max_pages is not None and pages >= max_pages):
            return follows
        time.sleep(sleep)


def sample_alters(follows, k=100, seed=42):
    """Draw a reproducible simple random sample of ``k`` alters.

    ``follows`` is the list returned by :func:`fetch_follows`. Seeding the
    random number generator means anyone re-running the notebook with the
    same follow list draws the same sample.
    """
    rng = random.Random(seed)
    if len(follows) <= k:
        return list(follows)
    return rng.sample(follows, k)


def build_ego_network(client, ego_did, alters, max_pages_per_alter=2,
                      sleep=SLEEP, verbose=True):
    """Build a directed 1.5-degree ego network as a NetworkX ``DiGraph``.

    Nodes are the ego plus the sampled ``alters``. Edges run from follower to
    followed. The ego's edges to every sampled alter are added directly (the
    alters were sampled from the ego's follow list), then each alter's first
    ``max_pages_per_alter`` pages of follows are crawled and only edges that
    point back *inside* the node set are kept — this is the "boundary
    specification" decision that turns an effectively infinite graph into a
    finite, analyzable one.

    Because each alter's follow list is truncated at roughly
    ``max_pages_per_alter * 100`` accounts (newest first), some within-network
    edges of prolific followers will be missed; the notebook discusses this
    limitation.
    """
    G = nx.DiGraph()
    G.add_node(ego_did)
    node_set = {ego_did} | {alter["did"] for alter in alters}

    # The ego follows every sampled alter by construction.
    for alter in alters:
        G.add_edge(ego_did, alter["did"])

    # Crawl each alter's follows and keep edges that stay inside the boundary.
    for i, alter in enumerate(alters, start=1):
        try:
            alter_follows = fetch_follows(
                client, alter["did"], max_pages=max_pages_per_alter, sleep=sleep
            )
        except Exception as error:  # deleted, deactivated, or blocked accounts
            if verbose:
                print(f"  ! skipping {alter['handle']}: {error}")
            G.add_node(alter["did"])
            continue
        for followed in alter_follows:
            if followed["did"] in node_set:
                G.add_edge(alter["did"], followed["did"])
        if verbose and i % 20 == 0:
            print(f"Crawled {i}/{len(alters)} alters: "
                  f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        time.sleep(sleep)
    return G


def add_profile_attributes(client, G, sleep=SLEEP):
    """Attach profile metadata to every node in ``G``, in place.

    Uses ``client.get_profiles`` (``app.bsky.actor.getProfiles``), which
    hydrates up to 25 profiles per request, to set ``handle``,
    ``followers_count``, ``follows_count``, and ``posts_count`` on each node.
    Returns the number of profiles retrieved.
    """
    dids = list(G.nodes)
    retrieved = 0
    for start in range(0, len(dids), PROFILE_BATCH_SIZE):
        batch = dids[start:start + PROFILE_BATCH_SIZE]
        response = client.get_profiles(actors=batch)
        for profile in response.profiles:
            G.nodes[profile.did].update(
                handle=profile.handle,
                followers_count=profile.followers_count,
                follows_count=profile.follows_count,
                posts_count=profile.posts_count,
            )
        retrieved += len(response.profiles)
        time.sleep(sleep)
    # Accounts that disappeared between crawl and hydration get placeholders.
    for did in dids:
        G.nodes[did].setdefault("handle", did)
        for attribute in ("followers_count", "follows_count", "posts_count"):
            G.nodes[did].setdefault(attribute, 0)
    return retrieved
