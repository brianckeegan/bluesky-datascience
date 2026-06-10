# Contributing to Bluesky Data Science

First off, thank you for taking the time to contribute! 🎉

**bluesky-datascience** is a collection of Jupyter notebook tutorials that teach
social-media data science using Bluesky and the AT Protocol. Its audience is
researchers, journalists, and students. That mission shapes what makes a good
contribution: clarity, pedagogy, reproducibility, and responsible use of public
data matter as much as working code.

All types of contributions are encouraged and valued — from fixing a typo, to
reporting a broken API call, to suggesting a new tutorial, to writing a whole
notebook. This guide explains how to do each effectively. Following it helps the
maintainer address your contribution and makes the process smoother for everyone.

> And if you like the project but don't have time to contribute, that's fine too.
> You can ⭐ the repo, cite it in your work, mention it in a talk, or tell other
> people about it.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Before You Start](#before-you-start)
- [Asking Questions](#asking-questions)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting a New Notebook or Enhancement](#suggesting-a-new-notebook-or-enhancement)
- [Contributing Code and Notebooks](#contributing-code-and-notebooks)
- [Style Guide](#style-guide)
- [Commit Messages and Pull Requests](#commit-messages-and-pull-requests)
- [Research-Ethics Expectations](#research-ethics-expectations)
- [License and Legal Notice](#license-and-legal-notice)

## Code of Conduct

This project and everyone participating in it is governed by our
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to
uphold it. Please report unacceptable behavior to **accounts@brianckeegan.com**.

## Before You Start

The single most useful document for any contributor — human or AI — is
[`AGENTS.md`](AGENTS.md). It describes the repository layout, notebook
conventions, the API environment (including quirks like `searchPosts` requiring
authentication), and exactly how to re-execute a notebook. Please read it before
opening a pull request. The intellectual plan for the whole series lives in
[`OUTLINE.md`](OUTLINE.md).

## Asking Questions

Before asking a question, please:

1. Read the relevant notebook and its markdown narration in full — the
   tutorials are written to be self-explanatory.
2. Check [`AGENTS.md`](AGENTS.md) and the official Bluesky/ATProto docs
   ([docs.bsky.app](https://docs.bsky.app), [atproto.com](https://atproto.com),
   [atproto.blue](https://atproto.blue)).
3. Search existing [issues](https://github.com/brianckeegan/bluesky-datascience/issues)
   to see if your question has already been answered.

If you still need help, open an issue with a clear title, describe what you are
trying to do, and provide context: your operating system, Python version,
`atproto` SDK version, and the full error message or unexpected output.

## Reporting Bugs

Because the notebooks hit the **live** Bluesky network, outputs change between
runs and some failures are transient (rate limits, network blips, API changes on
Bluesky's side). Please help us tell a real bug from a passing cloud.

**Before submitting**, please:

- Make sure you are on the latest version of the repository (`git pull`) and have
  installed the pinned dependencies with `python3 -m pip install -r requirements.txt`.
- Re-run the failing cell once or twice to rule out a transient network/API
  issue.
- Determine whether the problem is reproducible and try to isolate it to a
  minimal example.
- Search existing [issues](https://github.com/brianckeegan/bluesky-datascience/issues)
  for an already-filed report.

**When you submit a bug report**, open an issue and include:

- A clear, descriptive title.
- The notebook and section/cell where it occurs.
- Step-by-step reproduction instructions.
- What you expected to happen and what actually happened (with the **full**
  traceback, not a screenshot of one line).
- Your environment: OS, Python version, key package versions
  (`atproto`, `pandas`, `networkx`, …), and whether you ran authenticated or
  against the public AppView.

> ⚠️ **Security and credentials:** Never include the contents of your
> `atproto.json`, an app password, or any access token in an issue, comment, or
> commit. If you discover a security vulnerability, do **not** open a public
> issue — email **accounts@brianckeegan.com** privately instead.

## Suggesting a New Notebook or Enhancement

New tutorials and improvements are very welcome. Before suggesting one:

- Check that it isn't already planned in [`OUTLINE.md`](OUTLINE.md) or proposed
  in an existing issue.
- Consider whether it fits the series: a good part pairs a set of Bluesky/ATProto
  endpoints with a data-science method and a computational-social-science
  research design, and is useful to a broad audience of learners rather than a
  narrow niche.

Open an issue describing:

- A clear title and a step-by-step description of the proposed content.
- Which API endpoints and which method(s) it would teach.
- The research design or question it illustrates.
- Why it would benefit the project's audience, and any readings it would cite.

Opening an issue to discuss a new notebook **before** you write it is strongly
encouraged — it saves you from investing hours in something that may need a
different scope.

## Contributing Code and Notebooks

1. **Fork** the repository and create a branch from `main` with a descriptive
   name (e.g. `fix-part03-centrality` or `add-part11-embeddings`).
2. **Install dependencies** and set up an optional `atproto.json` as described in
   the [README](README.md) and [`AGENTS.md`](AGENTS.md).
3. **Make your changes**, following the [Style Guide](#style-guide) below.
4. **Re-execute** any notebook you touched, end to end, so its committed outputs
   are current:
   ```bash
   cd "Notebooks/Part NN - Title"
   jupyter nbconvert --to notebook --execute --inplace \
     --ExecutePreprocessor.timeout=600 "Part NN - Title.ipynb"
   ```
   Execution must complete without errors against the **unauthenticated** public
   AppView (guarded cells that print a "requires authentication" message count as
   success).
5. **Open a pull request** against `main`, ready for review.

## Style Guide

These conventions keep the series coherent; [`AGENTS.md`](AGENTS.md) is the
authoritative reference.

- **Voice and structure:** textbook-style narration aimed at undergraduates.
  Every code cell is preceded by markdown explaining what is about to happen and
  why; important results are followed by plain-language interpretation. Keep the
  canonical structure: H1 title → motivating intro → "Learning objectives" →
  numbered sections → "Ethics and limitations" → "Exercises" →
  "Research project ideas" → "References".
- **API style:** use the `atproto` SDK with dot-notation methods and cursor-based
  pagination, as in Part 00. Be polite to the API: `time.sleep(0.1)` between
  paginated calls, cap collections at a few hundred requests, and keep each
  part's `data/` under roughly 2 MB.
- **Helper modules:** put reusable logic in a part-specific `<topic>.py` module
  next to the notebook. `bsky_client.py` is intentionally duplicated into every
  part directory — if you change it, change every copy.
- **Guard privileged cells:** anything needing authentication (search,
  notifications) runs inside `if is_authenticated(client):` with an informative
  `else`. **Never call write endpoints** (`send_post`, `like`, `follow`) in cells
  that execute — show that code only inside guards or as non-executed examples.
- **Reproducibility:** record collection dates and parameters next to saved
  archives; downstream analysis cells should be runnable from the saved files in
  `data/`.

## Commit Messages and Pull Requests

- Write commit messages in the imperative mood ("Add Part 11 on embeddings",
  not "Added" or "Adds"). Keep the subject line under ~72 characters and explain
  the *why* in the body when it isn't obvious.
- Keep each pull request focused on a single concern; smaller PRs are reviewed
  faster.
- In the PR description, summarize what changed and why, link any related issue,
  and confirm that you re-executed any notebooks you modified.
- Do not commit credentials or large data files. `atproto.json` is gitignored;
  keep it that way.

## Research-Ethics Expectations

This project teaches the collection and analysis of real, public social-media
data, so we hold contributions to a high ethical standard:

- Use `bsky.app` (the official account) and `brianckeegan.com` (the author) as
  example accounts. Don't single out private individuals.
- Prefer aggregates and paraphrase over quoting strangers verbatim, and avoid
  de-anonymizing or re-identifying people.
- Honor data minimization: collect only what a tutorial needs, and store hashed
  or aggregated data where the raw form isn't necessary (see Part 10).
- Respect the spirit of each notebook's "Ethics and limitations" section and the
  [Code of Conduct](CODE_OF_CONDUCT.md).

## License and Legal Notice

When you contribute, you affirm that you authored 100% of the content you submit,
that you have the necessary rights to it, and that your contribution may be
provided under the project's license. Please ensure any third-party data, code,
or images you include are appropriately licensed and attributed.

---

Thank you again for contributing! Questions about contributing itself can go to
**accounts@brianckeegan.com**.
