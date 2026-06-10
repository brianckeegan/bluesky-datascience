# Notebook Outline

This document outlines ten planned notebooks that build on [Part 00 - Introduction](Notebooks/Part%2000%20-%20Introduction.ipynb). Each notebook pairs a set of Bluesky/ATProto API endpoints with a data science method and a computational social science research design, so that readers learn *how* to retrieve the data and *why* a researcher would want it.

**Conventions used throughout.** Like Part 00, the notebooks authenticate with the [ATProto SDK](https://atproto.blue/) using credentials stored in a local `atproto.json` file, access endpoints through the `Client` object's dot-notation methods (*e.g.*, `client.get_author_feed(...)`), and analyze results with Pandas, NumPy, Matplotlib, and NetworkX. Endpoints are referenced both by their SDK method name and their underlying XRPC lexicon name (*e.g.*, `get_follows` / `app.bsky.graph.getFollows`). Notebooks that need additional libraries list them under "New dependencies."

## Sequencing

* **Parts 01–02** develop core data-collection skills: pagination, rate limits, ethics, search, and archive construction.
* **Parts 03–06** each pair a data domain with a method family: networks, cascades, time series and causal inference, and text.
* **Parts 07–08** extend the toolkit to multimodal data and LLM-era methods.
* **Parts 09–10** cover affordances distinctive to Bluesky and ATProto: stackable moderation, custom feeds, the firehose, and bots.

---

## Part 01 — Collecting Data at Scale: Pagination, Rate Limits, and Research Ethics

**Motivation.** Part 00 retrieved a handful of records at a time. Real research questions require thousands of posts or follows, which means traversing cursors, respecting rate limits, and thinking about the ethics of collecting other people's (public) data before you start.

**Endpoints.**
* `get_author_feed` / `app.bsky.feed.getAuthorFeed` — paginating through an account's full posting history with the `cursor` parameter
* `get_follows`, `get_followers` / `app.bsky.graph.getFollows`, `app.bsky.graph.getFollowers` — exhaustively retrieving large follow lists
* `get_profiles` / `app.bsky.actor.getProfiles` — batching up to 25 profile lookups per request
* Inspecting `RateLimit-*` response headers and handling `429` errors

**Methods.** Writing reusable collection loops with cursors and stopping conditions; exponential backoff and polite sleeping; flattening the SDK's nested Pydantic models into tidy Pandas DataFrames; persisting archives to CSV and Parquet.

**Research design.** Defining a sampling frame before collecting; data-management plans; ethical considerations for social media scraping (user expectations, minimization, deletion and de-identification, terms of service, IRB perspectives on public data).

**New dependencies.** `pyarrow` (Parquet support).

---

## Part 02 — Searching and Snowballing: Building a Post Archive

**Motivation.** Most projects begin with a topic, not an account. This notebook starts from seed keywords and hashtags and "snowballs" outward to build a deduplicated, reusable archive of posts about a topic.

**Endpoints.**
* `app.bsky.feed.search_posts` / `app.bsky.feed.searchPosts` — keyword and hashtag search with `since`/`until`, `lang`, `author`, and `sort` parameters
* Post record internals: `facets` (mentions, links, hashtags), `embed` views, `langs`
* `get_posts` / `app.bsky.feed.getPosts` — re-hydrating archived posts by URI

**Methods.** Seed search → extract co-occurring hashtags, mentioned accounts, and linked threads from facets → expand the query set and repeat; deduplicating by URI/CID; saturation diagnostics (how many new posts does each snowball wave add?); storing the archive on disk for reuse in later notebooks.

**Research design.** Snowball sampling for topical corpora and its biases; constructing a defensible sampling frame for content analysis; documenting query decisions so the archive is reproducible.

**New dependencies.** None beyond Part 01.

---

## Part 03 — Social Network Analysis of Follow Relationships

**Motivation.** Bluesky's follow graph is fully public, making it an unusually open playground for social network analysis compared to other platforms.

**Endpoints.**
* `get_follows`, `get_followers` / `app.bsky.graph.getFollows`, `app.bsky.graph.getFollowers`
* `get_known_followers` / `app.bsky.graph.getKnownFollowers` — followers of an account that you also follow
* `get_profiles` / `app.bsky.actor.getProfiles` — node attributes (follower counts, descriptions, creation dates)

**Methods.** Building a directed ego network in NetworkX; a one- or two-wave snowball crawl of the graph; degree distributions; centrality measures (degree, betweenness, PageRank); community detection (Louvain); network visualization with attribute-based styling.

**Research design.** Ego-network research designs; homophily and triadic closure; the boundary specification problem — who counts as "in" the network when the graph is effectively infinite?

**New dependencies.** `python-louvain` (community detection).

---

## Part 04 — Threads, Engagement, and Information Diffusion

**Motivation.** How does content spread? Replies, likes, reposts, and quote posts leave a complete public trace of each cascade on Bluesky.

**Endpoints.**
* `get_post_thread` / `app.bsky.feed.getPostThread` — the full reply tree beneath a post
* `get_likes` / `app.bsky.feed.getLikes` — who liked a post and when
* `get_reposted_by` / `app.bsky.feed.getRepostedBy` — who amplified a post
* `get_quotes` / `app.bsky.feed.getQuotes` — quote posts referencing a post

**Methods.** Recursively traversing nested thread views into a tree structure; cascade metrics (size, depth, breadth, structural virality); plotting heavy-tailed engagement distributions on log-log axes; timing analysis of when engagement arrives.

**Research design.** Information diffusion and virality studies; broadcast versus viral spread; selecting cascades without conditioning on success (avoiding "sampling on the dependent variable").

**New dependencies.** None beyond Part 03.

---

## Part 05 — Time Series and Causal Inference: Event Studies on Bluesky

**Motivation.** Posting activity is a behavioral trace over time. When something happens in the world — a platform migration, a news event, a policy change — we can ask whether behavior *changed because of it*, which requires causal thinking, not just plotting.

**Endpoints.**
* `get_author_feed` / `app.bsky.feed.getAuthorFeed` — full posting histories for a panel of accounts
* `app.bsky.feed.search_posts` / `app.bsky.feed.searchPosts` — keyword volumes within `since`/`until` windows around an event

**Methods.** Datetime parsing and timezone handling in Pandas; resampling to hourly/daily/weekly counts; rolling averages; diurnal and weekly rhythms. Then causal designs: interrupted time series around an event; difference-in-differences comparing treated accounts or hashtags to a comparison group; matching accounts on profile covariates (followers, account age, prior activity) to build the comparison group.

**Research design.** Natural experiments and quasi-experimental causal inference with observational platform data; parallel-trends diagnostics; threats to validity (selection, anticipation, concurrent shocks) and why correlation-only claims fail.

**New dependencies.** `statsmodels` (regression for ITS and DiD).

---

## Part 06 — Natural Language Processing of Post Content

**Motivation.** What are people actually saying? This notebook turns the archives built in Parts 02 and 05 into quantitative measures of content.

**Endpoints.** Primarily reuses saved archives; `get_posts` / `app.bsky.feed.getPosts` to re-hydrate text by URI when needed.

**Methods.** Tokenization, stopword removal, and normalization for short social text (handles, hashtags, links); word and n-gram frequencies; sentiment analysis with VADER; topic modeling with LDA; a brief pointer to transformer sentence embeddings as the modern alternative.

**Research design.** Dictionary-based versus unsupervised content analysis; validating automated measures against human judgment; common failure modes (sarcasm, multilinguality, domain drift) and the "validate, validate, validate" principle.

**New dependencies.** `nltk` or `spaCy`, `vaderSentiment`, `scikit-learn` (LDA).

---

## Part 07 — Analyzing Visual Content: Images, Alt Text, and Link Cards

**Motivation.** A large share of social media communication is visual, yet most tutorials stop at text. Bluesky's image embeds, alt-text culture, and link cards make visual and accessibility questions directly measurable.

**Endpoints.**
* `embed` views on post records: `app.bsky.embed.images`, `app.bsky.embed.video`, `app.bsky.embed.external` (link cards)
* Blob CDN URLs and `com.atproto.sync.getBlob` — downloading full-size media
* `get_profile` / `app.bsky.actor.getProfile` — avatars and banners as a profile-image corpus

**Methods.** Building and managing an image corpus on disk (URLs, hashing, deduplication); EDA of media use — how often do posts include images, video, or link cards, and who provides alt text?; encoding images with a pretrained model (CLIP embeddings) for clustering and zero-shot classification of image content.

**Research design.** Visual framing analysis; multimodal content analysis (does the image agree with the text?); alt-text provision as a measurable accessibility and norms question.

**New dependencies.** `Pillow`, `sentence-transformers` or `open_clip` (CLIP embeddings).

---

## Part 08 — LLMs as Research Assistants: Classification and Annotation at Scale

**Motivation.** Hand-coding thousands of posts is the bottleneck of classic content analysis. Large language models can label stance, topic, or toxicity at scale — but only if we validate them like any other instrument.

**Endpoints.** Reuses post archives from Parts 02–06; no new Bluesky endpoints. Adds an LLM API (*e.g.*, Anthropic's Claude API) as a second data-processing service.

**Methods.** Writing a labeling prompt with a codebook; requesting structured (JSON) outputs; batching posts and handling API costs and rate limits; comparing LLM labels to a hand-coded gold sample with agreement metrics (percent agreement, Cohen's kappa); error analysis of disagreements; few-shot examples versus zero-shot prompting.

**Research design.** LLM-assisted content analysis and the "LLMs as annotators" debate; codebook development; when LLM labels are (and are not) defensible as research measures; documentation and reproducibility concerns with closed models.

**New dependencies.** `anthropic` (or another LLM provider's SDK).

---

## Part 09 — Algorithmic Curation and Governance: Custom Feeds, Lists, Labelers, and Starter Packs

**Motivation.** Bluesky's most distinctive feature is that curation and moderation are unbundled from the platform: anyone can publish a feed algorithm, a moderation labeler, a list, or a starter pack. That turns "the algorithm" from a black box into a public, queryable object of study.

**Endpoints.**
* `get_feed` / `app.bsky.feed.getFeed` — the contents of any published custom feed
* `app.bsky.feed.get_feed_generators`, `get_suggested_feeds` / `app.bsky.feed.getFeedGenerators`, `app.bsky.feed.getSuggestedFeeds` — feed metadata and discovery
* `get_list`, `get_lists` / `app.bsky.graph.getList`, `app.bsky.graph.getLists` — curation and moderation lists
* `app.bsky.graph.get_starter_packs` / `app.bsky.graph.getStarterPacks` — onboarding bundles of accounts and feeds
* `com.atproto.label.query_labels` / `com.atproto.label.queryLabels` — moderation labels applied by labeler services

**Methods.** Sampling posts from several custom feeds and comparing their composition (authors, topics, engagement, recency) against the default Following timeline; measuring audience overlap between feeds; describing list and starter-pack membership; tabulating label prevalence.

**Research design.** Algorithm audit designs adapted to a platform where algorithms are inspectable; platform governance and "stackable moderation" as a research site; starter packs as a natural experiment in network formation.

**New dependencies.** None beyond earlier parts.

---

## Part 10 — Real-Time Streams and Bots: Drinking from the Firehose

**Motivation.** Everything so far queried the past. ATProto also broadcasts every public event on the network in real time, which enables live monitoring — and, combined with the write endpoints from Part 00, bots.

**Endpoints.**
* [Jetstream](https://docs.bsky.app/blog/jetstream) — a friendly JSON websocket of network events, filterable by collection (`app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.graph.follow`)
* `com.atproto.sync.subscribeRepos` via the SDK's `FirehoseSubscribeReposClient` — the raw, complete firehose
* Write endpoints from Part 00: `send_post`, `like`, and replies with `reply_to` references; `get_notifications` / `app.bsky.notification.listNotifications` for detecting mentions

**Methods.** Connecting to a websocket stream and filtering events; live counts of posts, likes, and follows per minute; capturing a keyword's real-time volume during an event. Then a minimal bot: poll or stream for a trigger (a hashtag or a mention), construct a reply, and post on a schedule with appropriate rate limiting.

**Research design.** Real-time event monitoring versus retrospective search (what deletion and survivorship effects does each have?); population-level sampling from the firehose; bot ethics — disclosure, consent, platform norms, and Bluesky's bot conventions.

**New dependencies.** `websockets` (Jetstream).

---

## Cross-cutting themes

Three threads run through all ten notebooks and recur in their closing discussion sections:

1. **Ethics.** Public availability is not blanket consent; each notebook flags the specific risks its data type raises (network data exposes third parties, images may contain faces, LLM processing sends data to another company's servers).
2. **Reproducibility.** Archives are saved with collection dates and query parameters; analyses run from saved data so results can be re-checked even as the live network changes.
3. **The decentralization advantage.** Where relevant, notebooks contrast what is possible on an open protocol (full graphs, inspectable feeds, a public firehose) with what closed platforms allow, and what that openness implies for both research and user privacy.

**Possible future parts.** OAuth-based authentication, developing and publishing a custom feed generator, working with PDS repositories and CAR files directly, and agent-based simulation calibrated on Bluesky data.
