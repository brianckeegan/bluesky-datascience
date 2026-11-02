# After-Action Report: bluesky-datascience, PRs #4–#23 (2026-06-10 and 2026-11-02)

## 1. Summary

This sprint added the R Markdown series (v1.1), reviewed both series against today's
API (issues #7–#20), and fixed nine of those issues across PRs #21, #22 and #23. The
work that dominated time, failures and rework was **R**. It took 89 edits to `.Rmd`
files against 23 to notebooks, and 33 full-document knits, 11 of which failed. The
cause is in the harness, not in the R code as such. The definition gave R **no fast,
deterministic way to execute its own code**:
- R helpers live inline in each document, so the only test is a full knit;
- the knit hits the live network;
- the environment isn't pinned, so missing packages surface one knit at a time.

The June phase compounded this, because the R series was accepted on a check that
skipped every API chunk. The highest-leverage revisions:
1. **(P0-1)** Analyze from shared, committed data in R as well as Python, and keep live
   collection as a thin, optional layer. This is the pattern Parts 05 and 08 already use.
2. **(P0-2)** Move R helpers out of the documents into sourced files with fixture tests.
3. **(P0-3)** Replay recorded API responses in the mock instead of forwarding to the
   live AppView.
4. **(P1-1)** Pin and script the R environment.

## 2. Scope reviewed

- **Window:** `5561afb..origin/main` (PRs #4, #5, #6, #21, #22, #23). Work happened in
  two bursts: 2026-06-10 (CONTRIBUTING, the R series, v1.1, docs) and 2026-11-02 (the
  review, then the fixes).
- **Git evidence:** 25 commits (19 non-merge), +35,459/−24,758 lines, 16 files touched
  three or more times, 0 reverts, 3 fixup follow-ups.
- **Session evidence:** one long Claude Code session (4 compactions). It contained:
  - 18 user prompts;
  - 3 tagged "corrections" (one real one, "Try again" after a failed PR push; the other
    two were sub-agent notifications);
  - 0 interrupts, 0 rejected tool uses;
  - 18 tool errors in 3 repeated patterns.
- **Timing:** I timed tool calls from the transcript. Foreground wall time on R knits
  was 45 minutes across 33 calls. That excludes background runs, among them three
  15-minute full mock runs and one 7-minute run.
- **Not available:** `gh` isn't authenticated in this container, so the collector
  gathered no PR, CI or review-comment data. I took CI outcomes from the GitHub MCP
  calls in the transcript instead. There were no human review comments.
- **Earlier AAR:** none (first AAR).
- **Rigor level:** `standard`. This is a public teaching repo with a single maintainer;
  it has no protected data or production users.
- **Intent baseline:** `AGENTS.md` as it stood at each phase. There is no CLAUDE.md,
  no project skills, and no `.claude/settings.json`.

## 3. What the agent was supposed to do (Q1)

- **Mirror every analysis in both implementations:** "If you change the analyses in
  one implementation, mirror the change in the other."
- **Python:** notebooks are committed with outputs and must run against the public
  AppView "without errors and without deprecation warnings".
- **R, June version of AGENTS.md:** documents are committed as source. Verification
  meant knitting "without credentials (a knit plus a syntax check of every chunk)",
  with an acknowledgement that this "does not test their API code — that needs a
  credentialed knit before release".
- **R layout:** "R helper functions are defined inline in each document rather than in
  separate module files; only the credential helper is shared."
- **Prose:** "Never hard-code a number from one run into narration."
- **Shared data:** Part 05 already set the pattern of analyzing a committed archive by
  default, with live re-collection opt-in.

## 4. What actually happened (Q2)

- **June 10, R series built (PR #5):** 5,488 lines of R in one commit. It was verified
  prose-only, as AGENTS.md specified, which meant no API chunk ever executed. The
  November review then found (#8) wrong bskyr column names, repost and reply filters
  that silently did nothing, and several chunks that would crash with credentials.
- **November 2, #8 and #11 (PR #22):**
  - About 95 minutes from request to PR, most of it R. The mock-API harness itself
    (5,997 lines of R, fixtures and tests) had to be built first, because nothing else
    could execute R API code.
  - Mock knits then turned up bugs one document and one failure at a time. Each
    discovery cost a knit of one to fifteen minutes:
    - `"crimson"`;
    - a tibble column hiding its data frame (Part 07);
    - `bind_rows()` on a named list;
    - a starter-pack column that doesn't exist;
    - join counts arriving as text;
    - an invalid handle returning HTTP 400 (Part 06);
    - igraph's `crossing()` masking tidyr's in a shared session (Part 09).
  - Environment problems were found the same way, by failure:
    - igraph 1.6 vs 2.x, plus `libglpk40`;
    - a C locale producing mojibake;
    - bskyr 0.4 vs 0.5;
    - httr2 1.0 vs 1.3;
    - `reshape2` missing in CI, which caused the PR's only red CI run.
  - Bskyr's cleaning speed (about 15 minutes for 10,000 posts) looked like a hang.
  - Two parallel knits deleted each other's `data/` folders.
- **November 2, #17 and #10 (PR #23):**
  - About 30 minutes from request to PR, for a larger scope: three issues' worth of
    work in seven parts. Three sub-agents ran in parallel on disjoint file sets, with
    the main session committing.
  - CI was green on the first run.
  - One sub-agent tuned the Part 08 keyword baseline after reading the gold labels,
    raising κ from 0.597 to 0.770. It disclosed this, and I surfaced it to the
    maintainer.
- **Repeated tool errors:**
  - `create_pull_request` failed four times with a 401 until the head was given as
    `owner:branch`.
  - Edit failed four times on files that hadn't been read, or had changed since.
  - One of my notebook-editing scripts wrote invalid nbformat (`outputs` on markdown
    cells), which crashed `check_notebook_outputs.py`.
- **Process friction:** because the session could push to only one branch, the next
    PR's work had to wait, uncommitted, until the previous PR merged. The
    stop-hook "uncommitted changes" message fired 10 or more times during that wait.

## 5. Gap analysis (Q3)

### 5.1 R had no fast, deterministic way to execute its own code (highest cost)
**Observation:** R took 89 `.Rmd` edits and 33 knit invocations (11 failed), versus 23
notebook edits and 13 executions for Python.
- Every R bug was found by a full-document knit that stops at its first error, so bugs
  in one document surfaced serially. Part 09 needed four separate knit-fix rounds for
  four independent bugs.
- The knit also hits the live network, so failures were sometimes not the code's
  (Part 09 failed once in a full run and passed alone). Two real bugs only showed up
  against live data: Part 06's `handle.invalid` and Part 07's empty `list_rbind()`.

**Root cause: contradictory and missing.** AGENTS.md requires R and Python to mirror
each other, but gives them opposite architectures.
- Python keeps logic in importable `.py` modules. Those modules can be exercised
  directly, and their notebooks re-execute in seconds to minutes.
- R is told to define helpers "inline in each document". Its code can only be tested
  as an all-or-nothing knit against live data.

Nothing in the definition supplies R's missing fast loop: no fixtures, no recorded
responses, no unit tests.

**Why it cost so much:** the time per bug was set by the knit, not by the fix. Most of
the fixes were one line (`tidyr::crossing`, `#DC143C`, `n_image_posts`).

### 5.2 The June acceptance check couldn't detect the bugs it was meant to catch
**Observation:** the R series shipped in v1.1 verified "without credentials". Its own
AGENTS.md wording said that mode "does not test their API code". Five months later,
#8 found filters that did nothing and chunks that would crash.

**Root cause: ambiguous / weak.** The definition named the limitation but treated a
credentialed knit as a release-time chore, and gave no way to do one without the
maintainer's credentials. "Verified" therefore came to mean "parses and renders prose".

**Fixed this sprint:** PR #22 added the mock knit and made it a required check. Without
5.1's changes, though, the mock knit inherits the same slow, live, serial loop.

### 5.3 The R environment isn't pinned or reproducible
**Observation:** five environment mismatches were found by failure: igraph, glpk,
locale, httr2 and reshape2. One reached CI as the PR's only red run.
- Python has `requirements.txt` with exact pins.
- R has an `install.packages()` list that names packages but no versions. Some
  dependencies were missing from it (reshape2 until #22's fix) or implicit (httr2,
  curl, withr).

**Root cause: missing.** Issue #20 planned a `renv.lock`, but no `renv.lock` exists.

### 5.4 Duplicated logic drifts, and parity was asserted rather than checked
**Observation:** #10 and #17 were largely drift between the two languages:
- Part 08: different keyword lists gave different κ in R and Python;
- Part 02: different counting rules;
- Part 04: different caps and depths;
- Part 07: different reply filters and image handling.

Where the sprint replaced duplication with **one shared input plus a parity
assertion**, drift became impossible and checkable. That happened in Part 05 (the
shared archive with a coefficient check) and Part 08 (`codebook.json`, with a parity
chunk that stops the knit).

**Root cause: contradictory.** "Mirror the change in the other" asks for hand-mirroring
but provides no mechanism. The two documents that took the shared-data approach are the
two with no drift left.

### 5.5 Evaluation hygiene isn't stated
**Observation:** a sub-agent wrote the Part 08 keyword baseline after reading the gold
posts, which inflated κ. It disclosed this, and the PR flagged it.

**Root cause: missing**, but this is a single occurrence, so it doesn't get a heavy
rule (§6 P2-2). In a validation lesson, though, the cost of getting it wrong is high.

### 5.6 Smaller repeated frictions
- **PR head format (4 errors):** the GitHub MCP tool needs `owner:branch` here. This is
  specific to the environment, not a repo-definition gap. (P2)
- **Generated notebooks aren't validated:** `check_notebook_outputs.py` crashed on an
  invalid notebook instead of reporting it. (P1, tool config)
- **One designated branch serialized the PRs**, and the stop hook repeatedly nagged
  about deliberately uncommitted work. This is a session configuration, not a repo
  definition. (Noted, no repo action.)

## 6. Recommended revisions (Q4)

### [P0-1] R analyzes the shared, committed data; live collection is a thin optional layer
- **Target:** `AGENTS.md` → "Notebook conventions" (new bullet) and "Executing notebooks".
- **Root cause:** contradictory (5.1, 5.4).
- **Medium:** definition text. This needs judgment about which chunks are collection
  and which are analysis.
- **Evidence:** the documents that already work this way (Part 05, and Part 08's
  validation) run fully without credentials and are deterministic. Neither Part 05
  nor Part 08 failed a knit in the main session; Part 09 failed 4 times (one of them a
  collision between parallel runs) and Part 06 failed 3 times. Every other
  R knit failure this sprint came from live data or live collection code.
- **Change:** add to `AGENTS.md` under "Notebook conventions":
  > - **One dataset, two analyses.** Each part's analysis runs on the Python part's
  >   committed `data/` files. R documents read them by relative path, as Part 05 reads
  >   `actions.csv.gz`, and R's collection chunks show how to gather the same data with
  >   bskyr, writing to R's own `data/` only when the reader opts in. Prefer a shared
  >   input file over two hand-maintained copies for anything both implementations must
  >   agree on: parameters, codebooks, account panels (see Part 08's `codebook.json`).
  >   Add a parity chunk that stops the knit if R's results disagree with Python's saved
  >   ones (Parts 05 and 08). This keeps the R analysis runnable without credentials,
  >   makes R vs Python differences a test failure instead of a review finding, and
  >   keeps the live-API code small enough to check with the mock.
- **Why it works:** most of R's slow loop came from the analysis depending on live
  collection. Pointing analysis at fixed data makes it fast, offline and comparable to
  Python. The live part shrinks to a few chunks that the mock (P0-3) covers.
- **Owner:** maintainer review. This changes how the series is authored, and it is the
  #18 decision "shared prose and inputs between implementations". The edit to
  AGENTS.md takes minutes; converting each document is about one sub-agent task per
  part.
- **Status:** Proposed

### [P0-2] Move R helpers into sourced files with fixture-based tests
- **Target:** `AGENTS.md` → "Repository layout"; new `RMarkdown/Part NN …/<topic>.R`
  files; `RMarkdown/tests/testthat/`.
- **Root cause:** contradictory (5.1). The current text asks R to do the opposite of
  Python.
- **Medium:** definition text, plus a code convention.
- **Evidence:** every helper bug this sprint was found by a full knit, not a test:
  `iter_images()` crashing on video posts, `query_labels()` no-labels handling,
  `count_engaged` double counting, `fetch_posts()` handle failures. Only
  `bsky_client.R`'s helpers were testable, and its 18 tests ran in 11 seconds under
  both bskyr versions.
- **Change:** in `AGENTS.md`, replace
  > Most R helper functions are defined inline in each document rather than in
  > separate module files.

  with
  > R helpers that parse API responses or compute a measurement live in a
  > `<topic>.R` file next to the document (the counterpart of the Python part's
  > `<topic>.py`) and are `source()`d by it, so they can be tested without knitting.
  > Each gets a `testthat` test on a saved, redacted response in
  > `RMarkdown/tests/fixtures/`. Keep in the document only code that a reader needs
  > to see in order to follow the lesson. You can show a helper's source in the
  > rendered page with a chunk using `code = readLines("topic.R")`, so readers
  > lose nothing.
- **Why it works:** a helper bug costs a 1-second test instead of a 1–15-minute knit,
  and bugs in different helpers are reported together instead of one per knit.
- **Owner:** maintainer review.
- **Status:** Proposed

### [P0-3] Replay recorded API responses in the mock instead of forwarding live
- **Target:** `RMarkdown/tests/mock_api.R`, `scripts/check_rmarkdown.R`, the CI workflow.
- **Root cause:** missing (5.1).
- **Medium:** tool config.
- **Evidence:** two full mock runs disagreed with a single-document run on the same
  code (Part 09). One API failure was a live-data accident (Part 06). A full mock run
  took about 15 minutes, mostly network.
- **Change:**
  - Add a `--record` mode to `check_rmarkdown.R --mock-api`. It saves each forwarded
    response to `RMarkdown/tests/cassettes/<part>/<hash>.json`, redacted with the same
    script that built `fixtures/`.
  - The default mode replays recordings and fails on an unrecorded request.
  - Weekly CI runs `--record` against the live API. That is the API-drift check, kept
    separate from the code check.
  - Pull-request CI runs replay only.
  - Alternatively, use `httptest2` (a CRAN package that does this for httr2) instead
    of hand-rolling it.
- **Why it works:** it separates "did my code break?" (fast, deterministic, every edit)
  from "did the API change?" (slow, live, weekly). This sprint mixed the two in every
  knit.
- **Owner:** maintainer review (an infrastructure change), then auto-applyable.
- **Status:** Proposed

### [P1-1] Pin and script the R environment
- **Target:** new `renv.lock` (or `RMarkdown/DESCRIPTION` listing every dependency);
  `AGENTS.md` → "Setup"; the CI workflow.
- **Root cause:** missing (5.3).
- **Medium:** tool config.
- **Evidence:** five environment mismatches were found by failure, one of them in CI
  (`reshape2`). The igraph upgrade needed a system library.
- **Change:**
  - Snapshot with `renv::snapshot()`. CI uses `r-lib/actions/setup-renv`.
  - AGENTS.md: "Install R dependencies with `renv::restore()`. When you add a
    package to a document, add it to the lockfile in the same commit; CI installs only
    what the lockfile lists, so a package you have locally but didn't record will fail
    CI."
  - Optionally add a `SessionStart` hook that runs `Rscript -e 'renv::restore()'` in
    cloud sessions. Untested; test it before enabling.
- **Owner:** maintainer review.
- **Status:** Proposed

### [P1-2] Validate notebook structure in the output check
- **Target:** `scripts/check_notebook_outputs.py`.
- **Root cause:** missing (5.6).
- **Medium:** tool config.
- **Evidence:** an editing script produced markdown cells with `outputs`, and the
  check crashed with a TypeError instead of naming the problem.
- **Change:** at the top of `problems(path)`:
  ```python
  nb = nbformat.read(path, as_version=4)
  nbformat.validate(nb)   # raises with the offending cell
  ```
  Report a `ValidationError` as a failure for that notebook.
- **Owner:** auto-applyable.
- **Status:** Proposed

### [P1-3] Plan cross-part work as parallel, file-disjoint sub-tasks from the start
- **Target:** `AGENTS.md` → new short "Working on many parts at once" note.
- **Root cause:** missing. This was an emergent good habit worth codifying (§7).
- **Evidence:**
  - PR #22 was done serially: about 95 minutes for two issues in six R documents, with
    full-series knits run between fixes.
  - PR #23 used three parallel sub-agents on disjoint parts: about 30 minutes for
    three issues in seven parts, green on the first CI run.
  - The one collision, parallel knits deleting each other's `data/`, was fixed in
    `check_rmarkdown.R` (58eb372).
- **Change:**
  > When a change touches several parts, split it by part: each part (Python + R) is
  > independent and can be worked and verified on its own. Give each worker its own
  > files and its own `RENDER_DIR`, verify with
  > `check_rmarkdown.R --mock-api "Part NN"` for just that part, and run the full
  > series check once at the end. Committing from one place avoids index conflicts.
- **Owner:** maintainer review.
- **Status:** Proposed

### [P2-1] Name the R knit's shared-session hazard
- **Target:** `AGENTS.md` → "API style (R)".
- **Root cause:** novel (5.1). igraph masking tidyr's `crossing()` only appears when
  parts run in one session.
- **Change:** "Qualify functions that attached packages mask (`tidyr::crossing`,
  `igraph::union` vs base `union`). Students often run several parts in one R session,
  and the full check renders them in a single session to catch this."
- **Owner:** auto-applyable.
- **Status:** Proposed

### [P2-2] One line of evaluation hygiene for annotation baselines
- **Target:** `AGENTS.md` → "Notebook conventions".
- **Root cause:** missing (5.5). A single occurrence, so the rule stays light.
- **Change:** "When a part evaluates an instrument against gold labels (Part 08),
  write the instrument's rules before reading the gold set, or say in the prose that
  it was tuned on it. A baseline tuned on its evaluation set overstates its accuracy."
- **Owner:** maintainer review (it overlaps the open question on PR #23).
- **Status:** Proposed

### [P2-3] Record the GitHub tool's head-branch format for this environment
- **Target:** session or user memory, not the repo (it is environment-specific).
- **Root cause:** novel (5.6), 4 errors.
- **Change:** "In this environment, `create_pull_request` needs `head` as
  `brianckeegan:<branch>`; a bare branch name returns 401."
- **Owner:** auto-applyable.
- **Status:** Proposed

## 7. Strengths to sustain

- **Building a way to execute code before trusting it.** The mock-API harness and the
  redacted fixture tests found about ten real R bugs that the prose-only check had
  passed for five months. AGENTS.md now requires the mock knit for any R API change.
  Keep that rule; P0-3 makes it faster, not optional.
- **Parity as a test.** Part 05's coefficient check and Part 08's label parity chunk
  turn "R matches Python" into something a knit enforces. P0-1 generalizes this.
- **Verify before the PR, then watch CI to green.** Each PR listed the exact checks
  run. The only red CI run came from an environment difference (P1-1 targets it), and
  it was fixed within one event.
- **Honest disclosure of methodological shortcuts.** The Part 08 baseline tuning was
  surfaced rather than buried, and handed to the maintainer as a decision.
- **Docs updated in the same PR as the code.** AGENTS.md, CONTRIBUTING and README
  changed alongside every behavioural change, so the definition this AAR reviews was
  accurate.
- **Parallel, file-disjoint sub-agents** (PR #23), which P1-3 codifies.

## 8. Revision actions — tracking table

| ID | Priority | Target | Medium | Change | Owner | Status | Check next time |
|---|---|---|---|---|---|---|---|
| P0-1 | P0 | AGENTS.md conventions + each Rmd | definition text | R analysis reads Python's committed data; shared inputs + parity chunks | maintainer | Proposed | R knit failures per R-touching PR (this sprint: 11 failed of 33 knits); R docs with a parity chunk: 2/10 → 10/10 |
| P0-2 | P0 | AGENTS.md layout; `RMarkdown/Part NN/<topic>.R`; testthat | definition text + convention | Helpers in sourced files with fixture tests | maintainer | Proposed | Helper bugs found by knit vs by test (this sprint: ~8 vs 0) |
| P0-3 | P0 | mock_api.R, check_rmarkdown.R, CI | tool config | Record and replay responses; live recording weekly only | maintainer | Proposed | Full mock-run time (~15 min → target <3 min); runs that differ between full and single-part (1 → 0) |
| P1-1 | P1 | renv.lock, AGENTS.md setup, CI | tool config | Pin R dependencies; restore in CI and sessions | maintainer | Proposed | CI failures from missing or mismatched R packages (1 → 0); env issues found by failure (5 → 0) |
| P1-2 | P1 | check_notebook_outputs.py | tool config | nbformat.validate before checking outputs | auto | Proposed | Check crashes on malformed notebooks (1 → 0) |
| P1-3 | P1 | AGENTS.md | definition text | Split cross-part work into parallel, file-disjoint tasks | maintainer | Proposed | Request-to-PR time for multi-part issues (95 min serial vs 30 min parallel) |
| P2-1 | P2 | AGENTS.md API style (R) | definition text | Qualify masked functions | auto | Proposed | Masking failures in full runs (1 → 0) |
| P2-2 | P2 | AGENTS.md conventions | definition text | Write instruments before reading gold, or disclose | maintainer | Proposed | Undisclosed tuning on gold sets (0; keep 0) |
| P2-3 | P2 | session/user memory | memory | GitHub head-branch format | auto | Proposed | create_pull_request 401s (4 → 0) |
