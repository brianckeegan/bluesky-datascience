# AGENTS.md

Guidance for AI coding agents (and human contributors) working on this repository.

## Project

**bluesky-datascience** is a collection of notebook tutorials that teach
social media data science using Bluesky and the AT Protocol. The audience is
researchers, journalists, and students learning API-driven data collection and
analysis. Each part pairs a set of Bluesky API endpoints with a data science
method and a computational social science research design. The full intellectual
outline — motivations, endpoints, methods, research designs, and related Twitter
scholarship for every part — lives in [OUTLINE.md](OUTLINE.md); read it before
editing any notebook.

The series exists in **two parallel implementations** that perform the same
analyses:

- **`Notebooks/`** — Python Jupyter notebooks using the
  [`atproto` SDK](https://atproto.blue), pandas, NetworkX, statsmodels, and
  scikit-learn. Committed **with executed outputs**.
- **`RMarkdown/`** — R Markdown documents using
  [bskyr](https://christophertkenny.com/bskyr/), the tidyverse, igraph,
  tidytext, and topicmodels. Committed as source; users knit them locally.

Each Python part links to its R counterpart and vice versa. If you change the
analyses in one implementation, mirror the change in the other.

The series:

| Part | Directory | Focus |
|------|-----------|-------|
| 00 | `Notebooks/Part 00 - Introduction.ipynb` | Setup, authentication, profiles, feeds, follows, posting |
| 01 | `Notebooks/Part 01 - Collecting Data at Scale/` | Pagination, rate limits, research ethics |
| 02 | `Notebooks/Part 02 - Searching and Snowballing/` | Search, facets, snowball sampling into a post archive |
| 03 | `Notebooks/Part 03 - Social Network Analysis/` | Follow graphs, ego networks, centrality, communities |
| 04 | `Notebooks/Part 04 - Threads Engagement and Diffusion/` | Reply trees, cascades, engagement distributions |
| 05 | `Notebooks/Part 05 - Time Series and Causal Inference/` | Posting rhythms, event studies, ITS, DiD |
| 06 | `Notebooks/Part 06 - Natural Language Processing/` | Tokenization, sentiment, topic models |
| 07 | `Notebooks/Part 07 - Analyzing Visual Content/` | Image embeds, alt text, image corpora |
| 08 | `Notebooks/Part 08 - LLMs as Research Assistants/` | LLM annotation, validation against gold labels |
| 09 | `Notebooks/Part 09 - Algorithmic Curation and Governance/` | Custom feeds, lists, starter packs, labelers |
| 10 | `Notebooks/Part 10 - Real-Time Streams and Bots/` | Jetstream/firehose, monitoring, bot design |

The R counterparts live at `RMarkdown/Part NN - Title/Part NN - Title.Rmd`
(Part 00 sits at `RMarkdown/Part 00 - Introduction.Rmd`).

## Repository layout

Each Python Part 01–10 directory is self-contained:

```
Notebooks/Part NN - Title/
├── Part NN - Title.ipynb   # the tutorial notebook, committed WITH executed outputs
├── bsky_client.py          # shared auth-or-public client helper (identical copy in every part)
├── <topic>.py              # part-specific helper module(s) imported by the notebook
└── data/                   # small saved outputs (CSV/Parquet/PNG), committed
```

The R series mirrors that structure in a parallel tree:

```
RMarkdown/Part NN - Title/
├── Part NN - Title.Rmd     # the tutorial document (output: github_document)
└── bsky_client.R           # shared credential + feed helpers (identical copy in every part)
```

Most R helper functions are defined inline in each document rather than in
separate module files. `bsky_client.R` holds the shared ones: the credential
check, plus small helpers for bskyr's feed tibbles (`is_repost()`,
`is_reply()`, `reply_parent_did()`, `post_text()`, `post_created_at()`) and
`bsky_standardize()`, which renames the columns bskyr 0.4.x misspells
(`list_itemcount`, `joined_alltimecount`, `joined_weekcount`) to the 0.5.0
names. Use these helpers rather than guessing at bskyr's column names: a
filter on a column that doesn't exist (`reason_type` for the real
`` reason_$type ``) silently does nothing. The helpers stop with an error
if bskyr's columns change. Knitting an R part with
credentials writes a `data/` directory next to the document, but unlike the
Python series those outputs are not committed. `bsky_client.py` and
`bsky_client.R` are intentionally duplicated into each directory so every part
can be downloaded and run on its own (Part 00, which sits at the root of
`Notebooks/`, has its own copy there). If you change one, change every copy.

Supporting the notebooks:

```
tests/test_bot.py                   # safety tests for Part 10's bot (no network needed)
RMarkdown/tests/testthat/           # offline tests of the bsky_client.R helpers
RMarkdown/tests/fixtures/           # a saved, redacted API response the tests run on
RMarkdown/tests/mock_api.R          # mock API that lets R API chunks run without credentials
scripts/check_notebook_outputs.py   # fails on error outputs or deprecation warnings
scripts/check_rmarkdown.R           # renders and syntax-checks every Rmd (optionally via the mock)
.github/workflows/notebooks.yml     # weekly + on-PR run of all of the above
```

## Setup

Python 3.11, in a virtual environment (never the system Python — a distro's
own packages, such as Debian's Pillow, can shadow pip's and break imports):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # requirements.txt + pytest
```

`requirements.txt` pins the exact versions the committed outputs were produced
with. Upgrade deliberately: change a pin, re-execute the affected notebooks,
and commit the pins and outputs together. `atproto` is pre-1.0, and its
maintainers say compatibility between versions isn't guaranteed.

R (4.3+), with igraph 2.0 or later and bskyr 0.4.0 or later (CRAN 0.4.0 and
the 0.5.0 development version on GitHub are both tested):

```r
install.packages(c("bskyr", "tidyverse", "jsonlite", "igraph",
                   "tidytext", "topicmodels", "reshape2", "rmarkdown",
                   "digest", "websocket"))  # reshape2: tidying LDA in Part 06;
                                            # websocket only for Part 10
install.packages(c("httr2", "later",         # called directly in Parts 08-10
                   "patchwork"))              # multi-panel figures
install.packages(c("sandwich", "lmtest"))   # optional: HAC errors in Part 05
install.packages(c("testthat", "withr"))    # for the R tests and mock-API check
```

Authentication is optional for the Python series and **required for the R
series** (see below). Save credentials as `atproto.json` in the repository
root (it is gitignored):

```json
{"handle": "your-handle.bsky.social", "password": "your-app-password"}
```

Every Python notebook begins with `client = get_client()` from
`bsky_client.py`: with credentials it returns an authenticated client; without
them it falls back to the unauthenticated public AppView
(`https://public.api.bsky.app`), and cells that require authentication skip
themselves gracefully.

Every R document begins by sourcing `bsky_client.R`, which reads the same
`atproto.json` (or bskyr's `BLUESKY_APP_USER`/`BLUESKY_APP_PASS` environment
variables) and sets `bsky_authed`; the document then sets
`knitr::opts_chunk$set(eval = bsky_authed)` so that knitting without
credentials produces the full prose with API chunks skipped. Two parts gate
differently, because they don't depend on bskyr for their analysis:
**Part 05** analyzes the shared archive (`Notebooks/Part 05 …/data/actions.csv.gz`)
and runs fully without credentials, gating only its live-API chunks on
`bsky_authed`; **Part 10** gates its Jetstream chunks on having the websocket
package, since Jetstream needs no authentication.

## API environment facts

- The public AppView serves most **read** endpoints without authentication:
  profiles, author feeds, follows/followers, threads, likes, reposts, quotes,
  feed generators, lists, starter packs.
- `app.bsky.feed.searchPosts` returns **403 without authentication**. Python
  notebooks teach it inside an `is_authenticated(client)` guard and provide a
  feed-based fallback collection strategy.
- **bskyr authenticates every call** (0.4.x and 0.5.0) against
  `https://bsky.social` — it has no public-AppView fallback. This is why the R
  documents gate all API chunks on `bsky_authed` rather than guarding only
  search.
- bskyr's default cleaning is slow on large pulls (tens of milliseconds per
  post), so documents that collect thousands of posts use `clean = FALSE` and
  flatten the raw items themselves, as Part 01 does.
- `com.atproto.label.queryLabels` on `https://mod.bsky.app` rejects wildcard
  patterns (`at://did/*`) with HTTP 400 since 2026. Query bare DIDs (account
  labels) and exact post URIs instead, and treat a refused request as an
  error, never as "no labels" (Part 09).
- `RateLimit-*` response headers are returned by PDS hosts (e.g.
  `https://bsky.social/xrpc/...`), not by the public AppView.
- Jetstream is reachable at `wss://jetstream2.us-east.bsky.network/subscribe`
  and requires no authentication.

## Notebook conventions

These apply to both implementations unless noted.

- **Audience and voice:** a textbook-style narrative aimed at undergraduate
  students. Narrate extensively: every code cell/chunk is preceded by markdown
  that explains what is about to happen and why, and important results are
  followed by interpretation in plain language. Define terms on first use,
  anticipate confusion, and link generously to resources — official API/lexicon
  docs, library documentation (pandas, NetworkX, statsmodels, scikit-learn;
  tidyverse, igraph, tidytext), and accessible readings. Link the specific page,
  not a homepage, on a call's first use in a document:
  - endpoints: `https://endpoints.bsky.app/#bluesky-app/tag/<namespace without
    dots>/GET/xrpc/<NSID>`, e.g. `…/tag/appbskyfeed/GET/xrpc/app.bsky.feed.getAuthorFeed`
    (the hyphenated form doesn't work; `com.atproto.sync.subscribeRepos` isn't in
    this reference, so link https://atproto.com/specs/event-stream);
  - concepts: https://atproto.com/specs/… (DID, NSID, Lexicon, XRPC, AT-URI);
  - Python calls: the atproto.blue page for the namespace or model;
  - R calls: `https://christophertkenny.com/bskyr/reference/<function>.html`.

  Don't link docs.bsky.app: it is retired, and its guides live on bsky.network.
- **Structure:** H1 title; a motivating introduction; a "Learning objectives"
  list; numbered sections with explanatory markdown between code cells; a
  closing "Ethics and limitations" note; an "Exercises" section (4–6 tasks
  extending the notebook, ordered from small modifications to mini-analyses);
  a "Research project ideas" section (2–3 research designs a student could
  pursue with this part's methods); a "References" section citing the related
  Twitter scholarship listed for that part in OUTLINE.md, plus links to
  relevant documentation.
- **API style (Python):** the atproto SDK with dot-notation methods —
  `client.get_author_feed(...)` or `client.app.bsky.feed.get_author_feed({...})` —
  and cursor-based pagination, as in Part 00.
- **API style (R):** bskyr functions returning tibbles; reach into `record`
  list-columns with `purrr::map_chr(record, "field")`; use `clean = FALSE` plus
  purrr for deeply nested responses (threads, feeds, embeds). bskyr pages
  automatically when `limit > 100`, but it does not pause between pages, so use
  it only for small, capped pulls (a few pages). For larger collections write a
  cursor loop (bskyr returns the cursor in `attr(x, "cursor")`, as Part 02 does)
  with `Sys.sleep()` between pages.
- **Be polite to the API:** `time.sleep(0.1)` / `Sys.sleep(0.1)` between
  paginated calls you control; cap every collection (a few hundred requests per
  notebook at most); keep each Python part's `data/` under roughly 2 MB. Record
  in each collection's metadata whether it stopped at its cap (`truncated`).
- **Guard privileged cells (Python):** anything that needs authentication
  (search, notifications) runs inside `if is_authenticated(client):` with an
  informative `else`. **Never call write endpoints** (`send_post`, `like`,
  `follow`) in cells that execute; show that code only inside guards or as
  non-executed examples. In R, write actions are always `eval=FALSE` chunks.
- **Ethics defaults:** use `bsky.app` (the official platform account) and
  `nytimes.com` (a large institutional account) as the standing case-study
  accounts; don't single out private individuals; prefer aggregates and
  paraphrase over quoting strangers verbatim. Where an account's counts are
  enormous (e.g. `nytimes.com`'s ~1.3M followers), collect documented bounded
  samples — never attempt exhaustive collection.
- **Reproducibility:** record collection dates and parameters next to saved
  archives; downstream analysis cells should be runnable from the saved files
  in `data/`. When an analysis depends on reaching a fixed date in the past
  (an event study), analyze a committed archive by default and make live
  re-collection opt-in, as Part 05 does with `PART05_REFRESH=1`. An author
  feed is returned newest first, so a page budget that reaches a past date
  today will stop short of it once the account has kept posting.
- **Bots:** `run_bot_once` defaults to `dry_run=True` and refuses to post
  unless `BOT_OPERATOR` names the responsible human. Keep `tests/test_bot.py`
  passing when changing `bot.py`.

## Executing notebooks

Python notebooks are committed with outputs. To re-execute one end-to-end:

```bash
cd "Notebooks/Part NN - Title"
jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=1200 "Part NN - Title.ipynb"
```

Execution must complete without errors **and without deprecation warnings**
against the unauthenticated public AppView (guarded cells printing a
"requires authentication" message count as success). Every notebook,
including Part 00, must pass this. Check the outputs with:

```bash
python scripts/check_notebook_outputs.py "Notebooks/Part NN - Title/Part NN - Title.ipynb"
```

Two prose checks run on every pull request, without network access:

```bash
python scripts/check_stale_prose.py      # prose about the retired case-study account, or "in our run, 25..."
python scripts/rewrite_doc_links.py --check   # links to the retired docs.bsky.app
```

`python scripts/check_links.py` checks every external link (errors, moves to
another site, endpoint deep links naming an NSID the API doesn't have); it
needs the network, so CI runs it weekly rather than on each pull request.

Notebooks hit the live network, so numbers in outputs change between runs —
that is expected (except in Part 05, which analyzes its committed archive).
Never hard-code a number from one run into narration: print it from a
variable, or describe it qualitatively.

R Markdown documents are committed as source. Three checks, all run from the
repository root and none needing credentials:

```bash
Rscript -e 'testthat::test_dir("RMarkdown/tests/testthat")'   # helper tests, offline
Rscript scripts/check_rmarkdown.R                              # knit as a student without credentials
Rscript scripts/check_rmarkdown.R --mock-api                   # knit with the API chunks executing
```

Without credentials most R documents knit prose-only, which **does not test
their API code**. The `--mock-api` mode does: `RMarkdown/tests/mock_api.R`
answers bskyr's login with a fake session, forwards its reads to the public
AppView (synthesizing the two auth-only endpoints, search and timeline, from
an author feed, so only their shape is realistic), and fails the check on any
write request. Name documents to check only some, e.g.
`Rscript scripts/check_rmarkdown.R --mock-api "Part 02"`, and set
`RENDER_DIR` to keep the rendered output. Any change to an R document's API
code must pass the mock knit. With real credentials, the same `render()` call
executes every chunk against the live API.

The `.github/workflows/notebooks.yml` workflow runs the bot tests, every
Python notebook, the output check, the R helper tests (against CRAN and
development bskyr), and both R knits weekly and on pull requests that touch
the notebooks.
