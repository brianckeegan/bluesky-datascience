"""Check every external link in the tutorials (issue #12).

The docs.bsky.app retirement turned 125 links into quiet redirects that sent
students to the wrong page. This script makes the next migration a failing
check instead. For every http(s) URL in notebook markdown, R Markdown, and the
repository's Markdown files it reports:

* errors: HTTP 4xx/5xx, or no response at all;
* moved: a redirect to a different host (the docs.bsky.app failure mode);
* bad endpoint deep links: an endpoints.bsky.app #fragment naming an NSID that
  is not in the published API spec, which the site would render as its front
  page without complaint.

Redirects within the same host (http -> https, a trailing slash) are fine.

Usage (from the repository root):
    python scripts/check_links.py            # exit 1 on any problem
    python scripts/check_links.py --verbose  # also list every URL checked
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
URL = re.compile(r"https?://[^\s)\]\"'<>`\\]+")
SPEC = "https://endpoints.bsky.app/openapi.bluesky-app.json"
# Hosts that are templates/examples rather than links
# API service hosts (mod.bsky.app, public.api.bsky.app) are endpoints, not pages
SKIP_HOSTS = {"localhost", "127.0.0.1", "example.com", "bsky.social",
              "mod.bsky.app", "public.api.bsky.app"}
# Resolvers whose whole job is to redirect to the publisher
RESOLVERS = {"doi.org", "dx.doi.org", "hdl.handle.net"}
SKIP_PREFIXES = ("https://bsky.app/profile/<", "wss://")
HEADERS = {"User-Agent": "bluesky-datascience-link-check/1.0 (+https://github.com/brianckeegan/bluesky-datascience)"}


def markdown_text(path):
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text(encoding="utf-8"))
        return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")
    if path.suffix == ".Rmd":
        # prose only: drop fenced code chunks
        return re.sub(r"```\{r.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    return path.read_text(encoding="utf-8")


def collect_urls():
    urls = {}
    files = list(ROOT.glob("Notebooks/**/*.ipynb")) + list(ROOT.glob("RMarkdown/**/*.Rmd")) + \
        [p for p in ROOT.glob("*.md")] + list(ROOT.glob("docs/**/*.md"))
    for path in files:
        if ".ipynb_checkpoints" in path.parts:
            continue
        for url in URL.findall(markdown_text(path)):
            url = url.rstrip(".,;:!?*_")
            if url.endswith(")") and url.count("(") < url.count(")"):
                url = url[:-1]
            host = urlsplit(url).hostname or ""
            if host in SKIP_HOSTS or url.startswith(SKIP_PREFIXES) or "{" in url:
                continue
            urls.setdefault(url, set()).add(str(path.relative_to(ROOT)))
    return urls


def fetch(url):
    target = url.split("#")[0]
    for attempt in range(3):
        try:
            req = urllib.request.Request(target, headers=HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, response.geturl()
        except urllib.error.HTTPError as error:
            if error.code in (429, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            return error.code, target
        except Exception as error:  # DNS failure, timeout, TLS
            if attempt < 2:
                time.sleep(2)
                continue
            return f"{type(error).__name__}", target
    return "no response", target


def same_site(a, b):
    ha, hb = urlsplit(a).hostname or "", urlsplit(b).hostname or ""
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return strip(ha) == strip(hb)


def main(argv):
    verbose = "--verbose" in argv
    urls = collect_urls()
    with urllib.request.urlopen(SPEC, timeout=30) as response:
        nsids = {path.removeprefix("/xrpc/") for path in json.load(response)["paths"]}

    problems = []
    for url in urls:
        if url.startswith("https://endpoints.bsky.app/#bluesky-app/"):
            nsid = url.rsplit("/", 1)[-1]
            if nsid not in nsids:
                problems.append(("bad endpoint link", url, "NSID not in the API spec"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(urls, pool.map(fetch, urls)))
    for url, (status, final) in sorted(results.items()):
        if verbose:
            print(status, url)
        if not isinstance(status, int) or status >= 400:
            # Some publishers refuse scripted requests; report but distinguish
            kind = "blocked" if status in (401, 403) else "error"
            problems.append((kind, url, str(status)))
        elif not same_site(url.split("#")[0], final) and urlsplit(url).hostname not in RESOLVERS:
            problems.append(("moved", url, f"redirects to {final}"))

    hard = [p for p in problems if p[0] != "blocked"]
    for kind, url, detail in problems:
        where = ", ".join(sorted(urls.get(url, [])))[:150]
        print(f"[{kind}] {url} ({detail}) in {where}")
    print(f"checked {len(urls)} URLs: {len(hard)} problems, "
          f"{len(problems) - len(hard)} refused automated requests (check by hand)")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
