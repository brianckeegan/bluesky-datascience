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
└── bsky_client.R           # shared credential helper (identical copy in every part)
```

R helper functions are defined inline in each document rather than in separate
module files; only the credential helper is shared. `bsky_client.py` and
`bsky_client.R` are intentionally duplicated into each directory so every part
can be downloaded and run on its own. If you change one, change every copy.

## Setup

Python:

```bash
python3 -m pip install -r requirements.txt
```

R (4.3+):

```r
install.packages(c("bskyr", "tidyverse", "jsonlite", "igraph",
                   "tidytext", "topicmodels", "rmarkdown",
                   "websocket"))  # websocket only for Part 10
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
credentials produces the full prose with API chunks skipped.

## API environment facts

- The public AppView serves most **read** endpoints without authentication:
  profiles, author feeds, follows/followers, threads, likes, reposts, quotes,
  feed generators, lists, starter packs.
- `app.bsky.feed.searchPosts` returns **403 without authentication**. Python
  notebooks teach it inside an `is_authenticated(client)` guard and provide a
  feed-based fallback collection strategy.
- **bskyr (0.4.x) authenticates every call** against `https://bsky.social` —
  it has no public-AppView fallback. This is why the R documents gate all API
  chunks on `bsky_authed` rather than guarding only search.
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
  docs (https://docs.bsky.app, https://atproto.com, https://atproto.blue),
  library documentation (pandas, NetworkX, statsmodels, scikit-learn;
  tidyverse, igraph, tidytext), and accessible readings.
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
- **API style (R):** bskyr functions returning tibbles; rely on bskyr's
  automatic pagination (`limit > 100`); reach into `record` list-columns with
  `purrr::map_chr(record, "field")`; use `clean = FALSE` plus purrr for deeply
  nested responses (threads, feeds, embeds).
- **Be polite to the API:** `time.sleep(0.1)` / `Sys.sleep(0.1)` between
  paginated calls; cap every collection (a few hundred requests per notebook
  at most); keep each Python part's `data/` under roughly 2 MB.
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
  in `data/`.

## Executing notebooks

Python notebooks are committed with outputs. To re-execute one end-to-end:

```bash
cd "Notebooks/Part NN - Title"
jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=1200 "Part NN - Title.ipynb"
```

Execution must complete without errors against the unauthenticated public
AppView (guarded cells printing a "requires authentication" message count as
success). Notebooks hit the live network, so numbers in outputs change between
runs — that is expected. (Part 00 documents the login flow and is executed
with the author's credentials, not in CI.)

R Markdown documents are committed as source. To verify them without
credentials (prose-only knit plus a syntax check of every chunk):

```r
rmarkdown::render("RMarkdown/Part NN - Title/Part NN - Title.Rmd")
parse(knitr::purl("RMarkdown/Part NN - Title/Part NN - Title.Rmd",
                  output = tempfile(), documentation = 0))
```

With credentials available, the same `render()` call executes every chunk
against the live API.
