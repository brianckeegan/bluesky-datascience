# Bluesky Data Science
These are notebook tutorials for retrieving and analyzing data from Bluesky/ATProto, available in **two parallel implementations**: Python Jupyter notebooks (in [`Notebooks/`](Notebooks/)) and R Markdown documents (in [`RMarkdown/`](RMarkdown/)) that perform the same analyses with [bskyr](https://christophertkenny.com/bskyr/) and the tidyverse.

Each tutorial after Part 00 pairs a set of Bluesky API endpoints with a data science method and a computational social science research design. See [OUTLINE.md](OUTLINE.md) for the full intellectual outline — motivations, endpoints, methods, research designs, ethics, limitations, and related Twitter scholarship for every part.

## List of notebooks

| Part | Python (Jupyter) | R (R Markdown) | Focus |
|------|------------------|----------------|-------|
| 00 | [Introduction](Notebooks/Part%2000%20-%20Introduction.ipynb) | [Rmd](RMarkdown/Part%2000%20-%20Introduction.Rmd) | setup, authentication, profiles, feeds, follows, posting |
| 01 | [Collecting Data at Scale](Notebooks/Part%2001%20-%20Collecting%20Data%20at%20Scale/) | [Rmd](RMarkdown/Part%2001%20-%20Collecting%20Data%20at%20Scale/) | pagination, rate limits, research ethics |
| 02 | [Searching and Snowballing](Notebooks/Part%2002%20-%20Searching%20and%20Snowballing/) | [Rmd](RMarkdown/Part%2002%20-%20Searching%20and%20Snowballing/) | search, facets, snowball sampling into a post archive |
| 03 | [Social Network Analysis](Notebooks/Part%2003%20-%20Social%20Network%20Analysis/) | [Rmd](RMarkdown/Part%2003%20-%20Social%20Network%20Analysis/) | follow graphs, ego networks, centrality, communities |
| 04 | [Threads, Engagement, and Diffusion](Notebooks/Part%2004%20-%20Threads%20Engagement%20and%20Diffusion/) | [Rmd](RMarkdown/Part%2004%20-%20Threads%20Engagement%20and%20Diffusion/) | reply trees, cascades, engagement distributions |
| 05 | [Time Series and Causal Inference](Notebooks/Part%2005%20-%20Time%20Series%20and%20Causal%20Inference/) | [Rmd](RMarkdown/Part%2005%20-%20Time%20Series%20and%20Causal%20Inference/) | posting rhythms, event studies, ITS, DiD |
| 06 | [Natural Language Processing](Notebooks/Part%2006%20-%20Natural%20Language%20Processing/) | [Rmd](RMarkdown/Part%2006%20-%20Natural%20Language%20Processing/) | tokenization, sentiment, topic models |
| 07 | [Analyzing Visual Content](Notebooks/Part%2007%20-%20Analyzing%20Visual%20Content/) | [Rmd](RMarkdown/Part%2007%20-%20Analyzing%20Visual%20Content/) | image embeds, alt text, image corpora |
| 08 | [LLMs as Research Assistants](Notebooks/Part%2008%20-%20LLMs%20as%20Research%20Assistants/) | [Rmd](RMarkdown/Part%2008%20-%20LLMs%20as%20Research%20Assistants/) | LLM annotation, validation against gold labels |
| 09 | [Algorithmic Curation and Governance](Notebooks/Part%2009%20-%20Algorithmic%20Curation%20and%20Governance/) | [Rmd](RMarkdown/Part%2009%20-%20Algorithmic%20Curation%20and%20Governance/) | custom feeds, lists, starter packs, labelers |
| 10 | [Real-Time Streams and Bots](Notebooks/Part%2010%20-%20Real-Time%20Streams%20and%20Bots/) | [Rmd](RMarkdown/Part%2010%20-%20Real-Time%20Streams%20and%20Bots/) | Jetstream/firehose, real-time monitoring, bot design |

Each Python Part 01–10 directory is self-contained: the notebook (committed with executed outputs), a shared `bsky_client.py` connection helper, part-specific helper modules, and small saved datasets in `data/`. Each R part directory contains the R Markdown source and a shared `bsky_client.R` credential helper; knit the documents locally to execute them (without credentials they knit prose-only).

## Getting started

**Python.** Install the dependencies (a package manager like [Anaconda](https://www.anaconda.com/products/individual) is recommended):

```bash
python3 -m pip install -r requirements.txt
```

**R** (4.3 or later):

```r
install.packages(c("bskyr", "tidyverse", "jsonlite", "igraph",
                   "tidytext", "topicmodels", "rmarkdown",
                   "websocket"))  # websocket only for Part 10
```

Authentication: save your handle and an [app password](https://bsky.app/settings/app-passwords) as `atproto.json` in the repository root (it is gitignored — never commit credentials):

```json
{"handle": "your-handle.bsky.social", "password": "your-app-password"}
```

Both implementations read this same file. For the Python notebooks authentication is optional: without credentials they fall back to Bluesky's public AppView, where read endpoints work and cells that require authentication (search, notifications, posting) skip themselves with an explanation. For the R documents authentication is effectively required to execute the API chunks, because bskyr authenticates every call; without credentials the documents still knit, prose-only.

The main libraries used are:

* Python: [Jupyter Notebook](https://jupyter.org/), [ATProto SDK](https://atproto.blue/), [Pandas](https://pandas.pydata.org/), [Numpy](https://numpy.org/), [Matplotlib](https://matplotlib.org/), [NetworkX](https://networkx.org/), [statsmodels](https://www.statsmodels.org/), [scikit-learn](https://scikit-learn.org/)
* R: [R Markdown](https://rmarkdown.rstudio.com/docs/), [bskyr](https://christophertkenny.com/bskyr/), the [tidyverse](https://www.tidyverse.org/), [igraph](https://r.igraph.org/), [tidytext](https://juliasilge.github.io/tidytext/), [topicmodels](https://cran.r-project.org/package=topicmodels)

## For contributors and coding agents
Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for how to report bugs, propose new notebooks, and submit pull requests, and our [Code of Conduct](CODE_OF_CONDUCT.md) for community expectations. [AGENTS.md](AGENTS.md) documents the project layout, notebook conventions, API environment facts, and how to re-execute notebooks.

## Future directions
* OAuth-based authentication
* Developing and publishing a custom feed generator
* Working with PDS repositories and CAR files directly
* Agent-based simulation calibrated on Bluesky data
