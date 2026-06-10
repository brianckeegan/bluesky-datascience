# Bluesky Data Science
These are Jupyter Notebook tutorials for retrieving and analyzing data from Bluesky/ATProto.

Each tutorial after Part 00 pairs a set of Bluesky API endpoints with a data science method and a computational social science research design. See [OUTLINE.md](OUTLINE.md) for the full intellectual outline — motivations, endpoints, methods, research designs, ethics, limitations, and related Twitter scholarship for every part.

## List of notebooks
* [Part 00 - Introduction](Notebooks/Part%2000%20-%20Introduction.ipynb) — setup, authentication, profiles, feeds, follows, posting
* [Part 01 - Collecting Data at Scale](Notebooks/Part%2001%20-%20Collecting%20Data%20at%20Scale/) — pagination, rate limits, research ethics
* [Part 02 - Searching and Snowballing](Notebooks/Part%2002%20-%20Searching%20and%20Snowballing/) — search, facets, snowball sampling into a post archive
* [Part 03 - Social Network Analysis](Notebooks/Part%2003%20-%20Social%20Network%20Analysis/) — follow graphs, ego networks, centrality, communities
* [Part 04 - Threads Engagement and Diffusion](Notebooks/Part%2004%20-%20Threads%20Engagement%20and%20Diffusion/) — reply trees, cascades, engagement distributions
* [Part 05 - Time Series and Causal Inference](Notebooks/Part%2005%20-%20Time%20Series%20and%20Causal%20Inference/) — posting rhythms, event studies, interrupted time series, difference-in-differences
* [Part 06 - Natural Language Processing](Notebooks/Part%2006%20-%20Natural%20Language%20Processing/) — tokenization, sentiment, topic models
* [Part 07 - Analyzing Visual Content](Notebooks/Part%2007%20-%20Analyzing%20Visual%20Content/) — image embeds, alt text, image corpora
* [Part 08 - LLMs as Research Assistants](Notebooks/Part%2008%20-%20LLMs%20as%20Research%20Assistants/) — LLM annotation, validation against gold labels
* [Part 09 - Algorithmic Curation and Governance](Notebooks/Part%2009%20-%20Algorithmic%20Curation%20and%20Governance/) — custom feeds, lists, starter packs, labelers
* [Part 10 - Real-Time Streams and Bots](Notebooks/Part%2010%20-%20Real-Time%20Streams%20and%20Bots/) — Jetstream/firehose, real-time monitoring, bot design

Each Part 01–10 directory is self-contained: the notebook (committed with executed outputs), a shared `bsky_client.py` connection helper, part-specific helper modules, and small saved datasets in `data/`.

## Getting started
Install the dependencies (a package manager like [Anaconda](https://www.anaconda.com/products/individual) is recommended):

```bash
python3 -m pip install -r requirements.txt
```

Authentication is optional but recommended: save your handle and an [app password](https://bsky.app/settings/app-passwords) as `atproto.json` in the repository root (it is gitignored — never commit credentials):

```json
{"handle": "your-handle.bsky.social", "password": "your-app-password"}
```

Without credentials, the notebooks fall back to Bluesky's public AppView: read endpoints work, while cells that require authentication (search, notifications, posting) skip themselves with an explanation.

The main libraries used are:

* [Jupyter Notebook](https://jupyter.org/)
* [Python 3](https://www.python.org/)
* [ATProto SDK](https://atproto.blue/)
* [Pandas](https://pandas.pydata.org/), [Numpy](https://numpy.org/), [Matplotlib](https://matplotlib.org/)
* [NetworkX](https://networkx.org/), [statsmodels](https://www.statsmodels.org/), [scikit-learn](https://scikit-learn.org/)

## For contributors and coding agents
[AGENTS.md](AGENTS.md) documents the project layout, notebook conventions, API environment facts, and how to re-execute notebooks.

## Future directions
* OAuth-based authentication
* Developing and publishing a custom feed generator
* Working with PDS repositories and CAR files directly
* Agent-based simulation calibrated on Bluesky data
