"""Rewrite links to the retired docs.bsky.app site (issue #12).

docs.bsky.app now redirects: guides and blog posts moved to the same paths on
bsky.network, and the per-endpoint API pages all land on the front page of
https://endpoints.bsky.app, losing the endpoint. This script rewrites every
link in the notebooks, R Markdown documents, and Markdown/Python/R sources:

* docs.bsky.app/docs/api/<slug>   -> an endpoints.bsky.app deep link for the
  endpoint, built from its NSID and checked against the published OpenAPI spec
* docs.bsky.app/docs/... and /blog/... -> the same path on bsky.network
* bare docs.bsky.app (always used as "the API reference") -> endpoints.bsky.app

Usage (from the repository root):
    python scripts/rewrite_doc_links.py           # rewrite in place
    python scripts/rewrite_doc_links.py --check   # exit 1 if any link remains
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_URL = "https://endpoints.bsky.app/openapi.bluesky-app.json"
ENDPOINTS = "https://endpoints.bsky.app"

# Guide pages that did not survive the move under the same path
MOVED = {
    "docs/advanced-guides/custom-feeds": "docs/starter-templates/custom-feeds",
}
# API "pages" that were indexes rather than endpoints
INDEXES = {"at-protocol-xrpc-api", "category/http-reference"}

LINK = re.compile(r"https?://docs\.bsky\.app(/[A-Za-z0-9_\-/#.]*)?")


def load_nsids():
    with urllib.request.urlopen(SPEC_URL, timeout=30) as response:
        spec = json.load(response)
    nsids = {}
    for path, methods in spec["paths"].items():
        nsid = path.removeprefix("/xrpc/")
        nsids[nsid.lower()] = (nsid, next(iter(methods)).upper())
    return nsids


def slug_to_nsid(slug):
    """app-bsky-feed-get-author-feed -> app.bsky.feed.getAuthorFeed"""
    parts = slug.split("-")
    namespace, method = parts[:3], parts[3:]
    return ".".join(namespace) + "." + method[0] + "".join(p.title() for p in method[1:])


def deep_link(nsid, method):
    """Deep-link rule verified in issue #12: tag is the namespace without dots."""
    tag = "".join(nsid.split(".")[:-1])
    return f"{ENDPOINTS}/#bluesky-app/tag/{tag}/{method}/xrpc/{nsid}"


def rewrite_url(match, nsids):
    path = (match.group(1) or "").rstrip(".")
    trailing = (match.group(1) or "")[len(path):]
    if path in ("", "/"):
        return ENDPOINTS + trailing
    path = path.lstrip("/").rstrip("/")
    if path.startswith("docs/api/") or path.startswith("docs/category/"):
        slug = path.removeprefix("docs/api/").removeprefix("docs/")
        if slug in INDEXES:
            return ENDPOINTS + trailing
        guess = slug_to_nsid(slug)
        if guess.lower() not in nsids:
            raise SystemExit(f"No endpoint in the API spec matches {slug!r} (guessed {guess})")
        return deep_link(*nsids[guess.lower()]) + trailing
    base, _, anchor = path.partition("#")
    base = MOVED.get(base, base)
    return f"https://bsky.network/{base}" + (f"#{anchor}" if anchor else "") + trailing


def rewrite_text(text, nsids):
    text = LINK.sub(lambda m: rewrite_url(m, nsids), text)
    # Link text that names the old site
    return text.replace("[docs.bsky.app]", "[endpoints.bsky.app]")


def source_files():
    patterns = ["**/*.ipynb", "**/*.Rmd", "**/*.md", "**/*.py", "**/*.R"]
    skip = {".git", ".venv", ".ipynb_checkpoints"}
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if skip.isdisjoint(path.parts) and path.resolve() != Path(__file__).resolve():
                yield path


def rewrite_notebook(path, nsids):
    nb = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for cell in nb["cells"]:
        old = "".join(cell["source"])
        new = rewrite_text(old, nsids)
        if new != old:
            cell["source"] = new.splitlines(keepends=True)
            changed = True
    if changed:
        path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def main(argv):
    if "--check" in argv:
        left = [str(p.relative_to(ROOT)) for p in source_files()
                if LINK.search(p.read_text(encoding="utf-8", errors="ignore"))]
        for p in left:
            print(f"docs.bsky.app link remains: {p}")
        return 1 if left else 0
    nsids = load_nsids()
    for path in sorted(source_files()):
        if path.suffix == ".ipynb":
            changed = rewrite_notebook(path, nsids)
        else:
            old = path.read_text(encoding="utf-8")
            new = rewrite_text(old, nsids)
            changed = new != old
            if changed:
                path.write_text(new, encoding="utf-8")
        if changed:
            print(f"rewrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
