"""Helpers for connecting to Bluesky in the bluesky-datascience tutorials.

Every notebook in this collection starts by calling ``get_client()``. If you
have saved your credentials in an ``atproto.json`` file (see Part 00), you get
an authenticated client that can use every endpoint, including search and
write operations. If not, you get a read-only client pointed at Bluesky's
public AppView, which supports most of the endpoints these tutorials use.
"""

import json
from pathlib import Path

from atproto import Client

PUBLIC_APPVIEW = "https://public.api.bsky.app"

CREDENTIAL_LOCATIONS = [
    Path("atproto.json"),
    Path("../atproto.json"),
    Path("../../atproto.json"),
    Path.home() / "atproto.json",
]


def get_client(credentials_path=None):
    """Return an atproto Client, authenticated if credentials are available.

    Looks for an ``atproto.json`` file shaped like
    ``{"handle": "...", "password": "..."}`` in the repository (or at
    ``credentials_path`` if given) and logs in with it. Otherwise returns an
    unauthenticated client for the public AppView, which can read public data
    but cannot search, post, or like.
    """
    candidates = [Path(credentials_path)] if credentials_path else CREDENTIAL_LOCATIONS
    for candidate in candidates:
        if candidate.exists():
            credentials = json.loads(candidate.read_text())
            client = Client()
            client.login(credentials["handle"], credentials["password"])
            print(f"Authenticated as {credentials['handle']}")
            return client
    print(
        "No atproto.json found: using the unauthenticated public AppView.\n"
        "Read endpoints work; search and write endpoints require logging in."
    )
    return Client(base_url=PUBLIC_APPVIEW)


def is_authenticated(client):
    """Return True if ``client`` has an active session (login succeeded)."""
    return getattr(client, "me", None) is not None
