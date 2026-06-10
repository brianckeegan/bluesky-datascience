# AGENTS.md

Guidance for AI coding agents (and human contributors) working on this repository.

## Project

**bluesky-datascience** is a collection of Jupyter notebook tutorials that teach
social media data science using Bluesky and the AT Protocol. The audience is
researchers, journalists, and students learning API-driven data collection and
analysis. Each notebook pairs a set of Bluesky API endpoints with a data science
method and a computational social science research design. The full intellectual
outline — motivations, endpoints, methods, research designs, and related Twitter
scholarship for every part — lives in [OUTLINE.md](OUTLINE.md); read it before
editing any notebook.

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

## Repository layout

Each Part 01–10 directory is self-contained:

```
Notebooks/Part NN - Title/
├── Part NN - Title.ipynb   # the tutorial notebook, committed WITH executed outputs
├── bsky_client.py          # shared auth-or-public client helper (identical copy in every part)
├── <topic>.py              # part-specific helper module(s) imported by the notebook
└── data/                   # small saved outputs (CSV/Parquet/PNG), committed
```

`bsky_client.py` is intentionally duplicated into each directory so every part can
be downloaded and run on its own. If you change it, change every copy.

## Setup

```bash
python3 -m pip install -r requirements.txt
```

Authentication is optional but recommended. Save credentials as `atproto.json`
in the repository root (it is gitignored):

```json
{"handle": "your-handle.bsky.social", "password": "your-app-password"}
```

Every notebook begins with `client = get_client()` from `bsky_client.py`: with
credentials it returns an authenticated client; without them it falls back to the
unauthenticated public AppView (`https://public.api.bsky.app`), and cells that
require authentication skip themselves gracefully.

## API environment facts

- The public AppView serves most **read** endpoints without authentication:
  profiles, author feeds, follows/followers, threads, likes, reposts, quotes,
  feed generators, lists, starter packs.
- `app.bsky.feed.searchPosts` returns **403 without authentication**. Notebooks
  teach it inside an `is_authenticated(client)` guard and provide a feed-based
  fallback collection strategy.
- `RateLimit-*` response headers are returned by PDS hosts (e.g.
  `https://bsky.social/xrpc/...`), not by the public AppView.
- Jetstream is reachable at `wss://jetstream2.us-east.bsky.network/subscribe`.

## Notebook conventions

- **Structure:** H1 title; a short motivating introduction; a "Learning
  objectives" list; numbered sections with explanatory markdown between code
  cells (match the instructional voice of Part 00); a closing "Ethics and
  limitations" note; a "References" section citing the related Twitter
  scholarship listed for that part in OUTLINE.md.
- **API style:** the atproto SDK with dot-notation methods —
  `client.get_author_feed(...)` or `client.app.bsky.feed.get_author_feed({...})` —
  and cursor-based pagination, as in Part 00.
- **Be polite to the API:** `time.sleep(0.1)` between paginated calls; cap every
  collection (a few hundred requests per notebook at most); keep each part's
  `data/` under roughly 2 MB.
- **Guard privileged cells:** anything that needs authentication (search,
  notifications) runs inside `if is_authenticated(client):` with an informative
  `else`. **Never call write endpoints** (`send_post`, `like`, `follow`) in cells
  that execute; show that code only inside guards or as non-executed examples.
- **Ethics defaults:** use `bsky.app` (the official account) and
  `brianckeegan.com` (the author) as example accounts; don't single out private
  individuals; prefer aggregates and paraphrase over quoting strangers verbatim.
- **Reproducibility:** record collection dates and parameters next to saved
  archives; downstream analysis cells should be runnable from the saved files in
  `data/`.

## Executing notebooks

Notebooks are committed with outputs. To re-execute one end-to-end:

```bash
cd "Notebooks/Part NN - Title"
jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=600 "Part NN - Title.ipynb"
```

Execution must complete without errors against the unauthenticated public
AppView (guarded cells printing a "requires authentication" message count as
success). Notebooks hit the live network, so numbers in outputs change between
runs — that is expected.
