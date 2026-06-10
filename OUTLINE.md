# Notebook Outline

This document outlines the ten tutorials (Parts 01–10) that build on [Part 00 - Introduction](Notebooks/Part%2000%20-%20Introduction.ipynb). Each part pairs a set of Bluesky/ATProto API endpoints with a data science method and a computational social science research design, so that readers learn *how* to retrieve the data and *why* a researcher would want it.

The series exists in two parallel implementations that perform the same analyses: **Python Jupyter notebooks** under `Notebooks/Part NN - Title/` and **R Markdown documents** under `RMarkdown/Part NN - Title/`. This outline describes the shared intellectual design; [AGENTS.md](AGENTS.md) documents the per-implementation layout, conventions, and execution instructions.

**Conventions used throughout.** Both implementations read credentials from a local, gitignored `atproto.json` file. The Python notebooks use the [ATProto SDK](https://atproto.blue/)'s dot-notation methods (*e.g.*, `client.get_author_feed(...)`) and fall back to the unauthenticated public AppView when no credentials are present; analysis uses Pandas, NumPy, Matplotlib, and NetworkX. The R documents use [bskyr](https://christophertkenny.com/bskyr/) (which authenticates every call, so unauthenticated knits skip API chunks) with the tidyverse, igraph, tidytext, and topicmodels filling the corresponding roles. Endpoints are referenced both by their SDK method name and their underlying XRPC lexicon name (*e.g.*, `get_follows` / `app.bsky.graph.getFollows`). The "New dependencies" notes below list Python packages; the R equivalents are installed once up front (see the [README](README.md)). The standing case-study accounts are `bsky.app` (the official platform account) and `nytimes.com` (a large institutional account), with collections bounded to documented samples wherever counts are enormous.

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
* `get_follows`, `get_followers` / `app.bsky.graph.getFollows`, `app.bsky.graph.getFollowers` — retrieving complete follow lists, and deliberately *bounded* samples of follower lists that run to the millions
* `get_profiles` / `app.bsky.actor.getProfiles` — batching up to 25 profile lookups per request
* Inspecting `RateLimit-*` response headers and handling `429` errors

**Methods.** Writing reusable collection loops with cursors and stopping conditions; exponential backoff and polite sleeping; flattening the SDK's nested Pydantic models into tidy Pandas DataFrames; persisting archives to CSV and Parquet.

**Research design.** Defining a sampling frame before collecting; data-management plans; ethical considerations for social media scraping (user expectations, minimization, deletion and de-identification, terms of service, IRB perspectives on public data).

**New dependencies.** `pyarrow` (Parquet support).

---

## Part 02 — Searching and Snowballing: Building a Post Archive

**Motivation.** Most projects begin with a topic or a community, not an account chosen in advance. This notebook builds a deduplicated, reusable post archive two ways: keyword/hashtag search where it is available, and — because search requires authentication and indexes only what the operator chooses — snowball sampling along the mention and reply ties embedded in posts, a design that needs nothing but public endpoints.

**Endpoints.**
* `app.bsky.feed.search_posts` / `app.bsky.feed.searchPosts` — keyword and hashtag search with `since`/`until`, `lang`, `author`, and `sort` parameters
* Post record internals: `facets` (mentions, links, hashtags), `embed` views, `langs`
* `get_posts` / `app.bsky.feed.getPosts` — re-hydrating archived posts by URI

**Methods.** Paginated keyword search with date/language filters; reading post records and their facets; an account-based snowball — collect a seed account's posts, identify the accounts it @-mentions or replies to most, crawl them, and repeat for a second wave under a hard account cap; deduplicating by URI; saturation diagnostics (how many new posts, accounts, and hashtags does each wave add?); storing the archive on disk with full provenance metadata for reuse in later notebooks; re-hydrating archived URIs to measure attrition.

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

**New dependencies.** None beyond Part 02 — community detection uses NetworkX's built-in Louvain implementation (`nx.community.louvain_communities`, NetworkX ≥ 3.0); the R edition uses igraph's `cluster_louvain()`.

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
* `get_author_feed` / `app.bsky.feed.getAuthorFeed` — complete posting histories for a treated and a comparison account, plus `get_profiles` covariates for a matching pool
* `app.bsky.feed.search_posts` / `app.bsky.feed.searchPosts` — keyword volumes within `since`/`until` windows around an event

**Methods.** Datetime parsing and timezone handling in Pandas; resampling to hourly/daily/weekly counts; rolling averages; diurnal and weekly rhythms. Then causal designs: interrupted time series around an event; difference-in-differences comparing treated accounts or hashtags to a comparison group; matching accounts on profile covariates (followers, account age, prior activity) to build the comparison group.

**Research design.** Natural experiments and quasi-experimental causal inference with observational platform data; parallel-trends diagnostics; threats to validity (selection, anticipation, concurrent shocks) and why correlation-only claims fail.

**New dependencies.** `statsmodels` (regression for ITS and DiD).

---

## Part 06 — Natural Language Processing of Post Content

**Motivation.** What are people actually saying? This notebook turns collections of posts into quantitative measures of content.

**Endpoints.** Builds a fresh panel corpus with `get_author_feed` / `app.bsky.feed.getAuthorFeed` (a seed account plus the accounts it mentions most, reusing Part 02's snowball logic in miniature); `get_posts` / `app.bsky.feed.getPosts` re-hydrates text by URI when working from a saved archive.

**Methods.** Tokenization, stopword removal, and normalization for short social text (handles, hashtags, links); word and n-gram frequencies; sentiment analysis with VADER; topic modeling with LDA; a brief pointer to transformer sentence embeddings as the modern alternative.

**Research design.** Dictionary-based versus unsupervised content analysis; validating automated measures against human judgment; common failure modes (sarcasm, multilinguality, domain drift) and the "validate, validate, validate" principle.

**New dependencies.** `vaderSentiment` (social-media sentiment lexicon) and `scikit-learn` (document-term matrices and LDA); the R edition uses tidytext's bundled Bing lexicon and the topicmodels package.

---

## Part 07 — Analyzing Visual Content: Images, Alt Text, and Link Cards

**Motivation.** A large share of social media communication is visual, yet most tutorials stop at text. Bluesky's image embeds, alt-text culture, and link cards make visual and accessibility questions directly measurable.

**Endpoints.**
* `embed` views on post records: `app.bsky.embed.images`, `app.bsky.embed.video`, `app.bsky.embed.external` (link cards), `app.bsky.embed.record` and `recordWithMedia` (quotes)
* `get_author_feed` requested as **raw JSON** rather than typed SDK models — the platform ships new embed types faster than SDKs model them, and strict parsing crashes on them
* Thumbnail URLs served by the image CDN (`com.atproto.sync.getBlob` is the raw-protocol route to full-size blobs)

**Methods.** Classifying embeds robustly from raw records; EDA of media use across a panel of accounts — how often do posts include images, video, or link cards, what aspect ratios, and who provides alt text at what length?; mapping link-card domains as an outlink/self-promotion measure; building a small, documented thumbnail corpus with a manifest; encoding images with a pretrained model (CLIP embeddings) for clustering and zero-shot classification of image content.

**Research design.** Visual framing analysis; multimodal content analysis (does the image agree with the text?); alt-text provision as a measurable accessibility and norms question.

**New dependencies.** `Pillow`, `sentence-transformers` or `open_clip` (CLIP embeddings).

---

## Part 08 — LLMs as Research Assistants: Classification and Annotation at Scale

**Motivation.** Hand-coding thousands of posts is the bottleneck of classic content analysis. Large language models can label stance, topic, or toxicity at scale — but only if we validate them like any other instrument.

**Endpoints.** Reuses post archives from Parts 02–06; no new Bluesky endpoints. Adds an LLM API (*e.g.*, Anthropic's Claude API) as a second data-processing service.

**Methods.** Writing a labeling prompt with a codebook; requesting structured (JSON) outputs; batching posts and handling API costs and rate limits; comparing LLM labels to a hand-coded gold sample with agreement metrics (percent agreement, Cohen's kappa); error analysis of disagreements; few-shot examples versus zero-shot prompting.

**Research design.** LLM-assisted content analysis and the "LLMs as annotators" debate; codebook development; when LLM labels are (and are not) defensible as research measures; documentation and reproducibility concerns with closed models.

**New dependencies.** `anthropic` (or another LLM provider's SDK), optional — the annotation loop is guarded behind an API key and a transparent keyword baseline always runs; the R edition calls the HTTP API directly with httr2.

---

## Part 09 — Algorithmic Curation and Governance: Custom Feeds, Lists, Labelers, and Starter Packs

**Motivation.** Bluesky's most distinctive feature is that curation and moderation are unbundled from the platform: anyone can publish a feed algorithm, a moderation labeler, a list, or a starter pack. That turns "the algorithm" from a black box into a public, queryable object of study.

**Endpoints.**
* `get_feed` / `app.bsky.feed.getFeed` — the contents of any published custom feed
* `app.bsky.feed.get_feed_generators`, `get_suggested_feeds` / `app.bsky.feed.getFeedGenerators`, `app.bsky.feed.getSuggestedFeeds` — feed metadata and discovery
* `get_list`, `get_lists` / `app.bsky.graph.getList`, `app.bsky.graph.getLists` — curation and moderation lists
* `app.bsky.graph.get_starter_packs` / `app.bsky.graph.getStarterPacks` — onboarding bundles of accounts and feeds
* `com.atproto.label.query_labels` / `com.atproto.label.queryLabels` — moderation labels applied by labeler services

**Methods.** Sampling posts from several custom feeds and comparing their composition (author concentration, engagement, recency, media share) against a no-algorithm baseline built from a public list feed (the personalized Following timeline is only observable to a logged-in account); measuring audience overlap between feeds with Jaccard similarity; describing list and starter-pack membership; querying labeler services and tabulating label prevalence.

**Research design.** Algorithm audit designs adapted to a platform where algorithms are inspectable; platform governance and "stackable moderation" as a research site; starter packs as a natural experiment in network formation.

**New dependencies.** None beyond earlier parts.

---

## Part 10 — Real-Time Streams and Bots: Drinking from the Firehose

**Motivation.** Everything so far queried the past. ATProto also broadcasts every public event on the network in real time, which enables live monitoring — and, combined with the write endpoints from Part 00, bots.

**Endpoints.**
* [Jetstream](https://docs.bsky.app/blog/jetstream) — a friendly JSON websocket of network events, filterable by collection (`app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.graph.follow`)
* `com.atproto.sync.subscribeRepos` via the SDK's `FirehoseSubscribeReposClient` — the raw, complete firehose
* Write endpoints from Part 00: `send_post`, `like`, and threaded replies via `ReplyRef`; `get_notifications` / `app.bsky.notification.listNotifications` for detecting mentions (write actions are shown but never executed by the committed notebooks)

**Methods.** Connecting to a websocket stream and filtering events; live counts of posts, likes, and follows per minute; capturing a keyword's real-time volume during an event. Then a minimal bot: poll or stream for a trigger (a hashtag or a mention), construct a reply, and post on a schedule with appropriate rate limiting.

**Research design.** Real-time event monitoring versus retrospective search (what deletion and survivorship effects does each have?); population-level sampling from the firehose; bot ethics — disclosure, consent, platform norms, and Bluesky's bot conventions.

**New dependencies.** `websockets` (Jetstream).

---

## Ethics

Public availability is not blanket consent. Most Bluesky users have not read the protocol documentation and may not realize that their posts, likes, follows, and even blocks are globally readable; research consistently finds that social media users are surprised and sometimes upset to learn their posts are used in research (Fiesler & Proferes 2018). The notebooks therefore treat ethics as a design decision made *before* collection, not a disclaimer added afterward. Recurring principles:

* **Minimization and purpose limitation.** Collect only the fields a research question requires; prefer aggregate and derived measures over raw archives when sharing results.
* **Third parties.** Network data (Parts 03–04) necessarily exposes people other than the seed account; reply trees and like lists include users who never opted into anything.
* **De-identification and quoting.** Verbatim posts are trivially re-identifiable via search. Paraphrase or aggregate when reporting, especially for sensitive topics (Zimmer 2010).
* **Deletion and withdrawal.** Users delete posts and accounts; archives should record collection dates and honor deletions when re-publishing or sharing data.
* **Data-type-specific risks.** Images may contain faces and locations (Part 07); sending posts to an LLM API transmits user content to another company's servers (Part 08); bots interact with humans who have not consented to study participation and should disclose that they are automated (Part 10).
* **Institutional review.** "Public data" does not automatically mean exempt; the notebooks point readers to their IRB and to the AoIR Internet Research Ethics guidelines (franzke et al. 2020) for contextual judgment.

## Limitations

The notebooks are explicit about what Bluesky data can and cannot support:

* **Representativeness.** Bluesky's user base skews toward early adopters and several waves of Twitter migrants; prevalence estimates do not generalize to "the public," just as Twitter users were never representative of national populations (Mislove et al. 2011; Wojcik & Hughes 2019).
* **The model-organism problem.** Findings from one heavily studied platform reflect its affordances and norms as much as human behavior in general (Tufekci 2014); single-platform designs should be framed accordingly.
* **Behavioral traces, not attitudes.** Posts and likes measure expression and attention under platform incentives, not beliefs; absence of posting is not absence of opinion.
* **No private or exposure data.** The protocol exposes public actions only — no DMs, and no impression or view counts — so engagement metrics condition on visible reactions, not on who saw a post.
* **A platform in flux.** Lexicons, endpoints, rate limits, and moderation infrastructure are actively evolving; code that works today may need adjustment, which is why each notebook saves raw responses and records collection parameters (reproducibility over re-collection).
* **Search and index completeness.** `searchPosts` queries an index, not the full network history; deletions, blocks, and opt-outs create survivorship bias relative to firehose-based collection (an issue with direct parallels in Twitter's Streaming vs. Decahose APIs — Morstatter et al. 2013).
* **Identity instability.** Handles can change while DIDs persist; longitudinal designs should key on DIDs. Spam and automated accounts contaminate samples here as on every platform.

## Related work from Twitter scholarship

For fifteen years Twitter was computational social science's model organism (Tufekci 2014), and most of the research designs in these notebooks were first developed there. Each notebook situates its design in that literature — both to give credit and to let readers test whether Twitter-era findings replicate on a structurally different, decentralized platform. Key anchors by part:

* **Part 01 (collection, ethics):** Ruths & Pfeffer (2014) on the pitfalls of social media samples; Freelon (2018) on computational research in the "post-API age" — a cautionary tale that motivates studying open protocols; Fiesler & Proferes (2018) on participant perceptions of Twitter research ethics.
* **Part 02 (topical corpora):** Bruns & Burgess (2011) on hashtag publics and ad hoc issue communities; Tufekci (2014) on hashtag sampling bias.
* **Part 03 (follow networks):** Kwak, Lee, Park, & Moon (2010), "What is Twitter, a social network or a news media?"; Conover et al. (2011) on political polarization in retweet vs. mention networks.
* **Part 04 (diffusion):** boyd, Golder, & Lotan (2010) on retweeting as conversational practice; Bakshy, Hofman, Mason, & Watts (2011) on identifying influencers; Goel, Anderson, Hofman, & Watts (2016) on structural virality; Vosoughi, Roy, & Aral (2018) on the spread of true and false news.
* **Part 05 (time series, causal inference):** Golder & Macy (2011) on diurnal and seasonal mood rhythms; Dodds et al. (2011) on the hedonometer; González-Bailón, Borge-Holthoefer, Rivero, & Moreno (2011) on protest recruitment dynamics.
* **Part 06 (NLP):** O'Connor et al. (2010), "From tweets to polls"; Hutto & Gilbert (2014), the VADER sentiment lexicon built for microblog text; Grimmer & Stewart (2013) on validating automated text methods.
* **Part 07 (visual content):** Highfield & Leaver (2016) on visual social media methods; Gleason et al. (2019) on how user-provided image descriptions failed to make Twitter accessible — a direct baseline for Bluesky's alt-text norms.
* **Part 08 (LLM annotation):** Gilardi, Alizadeh, & Kubli (2023) on ChatGPT outperforming crowd workers for text annotation (on tweets); Törnberg (2023) on LLMs classifying political Twitter content; Ziems et al. (2024) on whether LLMs can transform computational social science.
* **Part 09 (algorithmic curation):** Huszár et al. (2022) on algorithmic amplification of politics on Twitter — an audit that required internal access, whereas Bluesky's feeds are externally inspectable; Bandy & Diakopoulos (2021) on how algorithmic curation changed media exposure in Twitter timelines.
* **Part 10 (streams, bots):** Morstatter, Pfeffer, Liu, & Carley (2013), "Is the sample good enough?", comparing Twitter's Streaming API to the firehose; Pfeffer, Mayer, & Morstatter (2018) on tampering with Twitter's sample API; Ferrara et al. (2016) on the rise of social bots.

**Possible future parts.** OAuth-based authentication, developing and publishing a custom feed generator, working with PDS repositories and CAR files directly, and agent-based simulation calibrated on Bluesky data.
