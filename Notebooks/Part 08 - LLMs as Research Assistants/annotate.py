"""Helpers for LLM-assisted annotation in Part 08 of the bluesky-datascience tutorials.

This module contains three groups of tools:

1. ``CODEBOOK`` and ``build_prompt`` — the labeling instructions we give to
   human coders and to a large language model (loaded from
   ``data/codebook.json``, shared with the R version), and the prompt
   template that wraps them around a post.
2. ``annotate_posts_llm`` — a batched annotation loop that sends posts to
   Anthropic's Claude API and parses strict-JSON labels back. It degrades
   gracefully (prints instructions and returns ``None``) when the
   ``anthropic`` package or an ``ANTHROPIC_API_KEY`` is unavailable, so the
   notebook always runs end-to-end.
3. ``keyword_label`` — a deliberately simple, fully transparent keyword-rule
   classifier that stands in for the LLM so the validation mechanics in the
   notebook execute for real. Swap in the LLM labels when you have a key.
"""

import json
import re
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. The codebook
# ---------------------------------------------------------------------------
#
# The codebook text and the keyword rules live in data/codebook.json, which
# the R Markdown version of this part reads too. Keeping one file means the
# two implementations apply exactly the same instrument and get the same
# validation numbers.

CODEBOOK_PATH = Path(__file__).with_name("data") / "codebook.json"

with open(CODEBOOK_PATH, encoding="utf-8") as _f:
    _CODEBOOK_DATA = json.load(_f)

CODEBOOK_VERSION = _CODEBOOK_DATA["version"]
LABELS = _CODEBOOK_DATA["labels"]
DEFAULT_LABEL = _CODEBOOK_DATA["default_label"]
CODEBOOK = "\n".join(_CODEBOOK_DATA["codebook"]) + "\n"
KEYWORD_RULES = _CODEBOOK_DATA["keyword_rules"]

# The model the notebook would use: the current small, inexpensive Claude
# model, which is well suited to short classification tasks.
DEFAULT_MODEL = "claude-haiku-5-5"

# Published prices in US dollars per million tokens (input, output), as of
# October 2026. Prices change: verify at https://claude.com/pricing
# before use. (Haiku's price is for prompts under 100K tokens, which every
# annotation prompt here is.)
MODEL_PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


# ---------------------------------------------------------------------------
# 2. LLM annotation (guarded — degrades gracefully without a key)
# ---------------------------------------------------------------------------

def build_prompt(codebook, post_text):
    """Wrap the codebook and a single post into an annotation prompt.

    The prompt asks for strict JSON with a ``label`` (one of LABELS) and a
    ``confidence`` between 0 and 1 so the output is machine-parseable.
    """
    return (
        "You are a careful content-analysis research assistant. Apply the "
        "codebook below to the post and respond with ONLY a JSON object — "
        "no preamble, no markdown fences.\n\n"
        "<codebook>\n"
        f"{codebook}\n"
        "</codebook>\n\n"
        "<post>\n"
        f"{post_text}\n"
        "</post>\n\n"
        "Respond with exactly this JSON shape:\n"
        '{"label": "politics" | "science_tech" | "other", '
        '"confidence": <number between 0 and 1>}'
    )


def parse_label_response(raw_text):
    """Parse a model response into ``{"label": ..., "confidence": ...}``.

    Handles the common failure modes: markdown code fences, extra prose
    around the JSON, missing keys, and labels outside the codebook. Returns a
    dict with ``label=None`` when the response is unusable, so a batch run
    never crashes on one bad response.
    """
    text = raw_text.strip()
    # Strip markdown fences if the model added them anyway.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    # Fall back to the first {...} block if there is surrounding prose.
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        text = match.group(0) if match else text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"label": None, "confidence": None, "error": "invalid JSON"}
    label = data.get("label")
    if label not in LABELS:
        return {"label": None, "confidence": None, "error": f"invalid label: {label!r}"}
    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        confidence = None
    return {"label": label, "confidence": confidence, "error": None}


def annotate_posts_llm(texts, codebook=CODEBOOK, model=DEFAULT_MODEL,
                       sleep_seconds=0.5, verbose=True):
    """Annotate an iterable of post texts with Claude, returning a list of dicts.

    Requires the ``anthropic`` package and an ``ANTHROPIC_API_KEY``
    environment variable. When either is missing this function explains what
    would happen and returns ``None`` instead of raising, so notebooks that
    call it always execute.

    The loop sleeps between requests to stay politely under rate limits and
    catches per-post API errors so one failure doesn't lose the whole batch.
    """
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "No ANTHROPIC_API_KEY found in the environment, so no API calls "
            "were made.\nTo run LLM annotation: create a key at "
            "https://console.anthropic.com/, run\n"
            "`pip install anthropic`, export ANTHROPIC_API_KEY, and re-run "
            "this cell.\nEach post would be sent to the model with the "
            "codebook prompt above and parsed\ninto a label + confidence."
        )
        return None
    try:
        import anthropic
    except ImportError:
        print(
            "The `anthropic` package is not installed. Run `pip install "
            "anthropic` and re-run."
        )
        return None

    client = anthropic.Anthropic()
    results = []
    for i, text in enumerate(texts):
        try:
            response = client.messages.create(
                model=model,
                # Current models think before answering; low effort keeps that
                # short for a simple classification, and 1,024 tokens leaves
                # room for the thinking plus the one-line JSON answer.
                max_tokens=1024,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": build_prompt(codebook, text)}],
            )
            if response.stop_reason == "refusal":
                parsed = {"label": None, "confidence": None, "error": "refused"}
            else:
                raw = next(
                    (block.text for block in response.content if block.type == "text"), ""
                )
                parsed = parse_label_response(raw)
            parsed.update({
                "text": text,
                "model": model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            })
        except anthropic.APIError as exc:  # rate limits, overloads, etc.
            parsed = {"label": None, "confidence": None,
                      "error": f"API error: {exc}", "text": text, "model": model}
        results.append(parsed)
        if verbose and (i + 1) % 10 == 0:
            print(f"Annotated {i + 1}/{len(texts)} posts")
        time.sleep(sleep_seconds)  # be polite to the API's rate limits
    return results


def estimate_annotation_cost(texts, codebook=CODEBOOK, model=DEFAULT_MODEL,
                             output_tokens_per_post=150):
    """Back-of-envelope cost estimate for annotating ``texts`` with ``model``.

    Uses the rough heuristic of ~4 characters per token (the official
    ``count_tokens`` endpoint gives exact numbers when you have a key). The
    output allowance covers the one-line JSON answer plus the model's brief
    thinking at low effort, which is billed as output tokens.
    Returns a dict of token and dollar estimates.
    """
    input_price, output_price = MODEL_PRICES[model]
    overhead_tokens = (len(codebook) + 600) / 4  # codebook + prompt scaffolding
    input_tokens = sum(overhead_tokens + len(t) / 4 for t in texts)
    output_tokens = output_tokens_per_post * len(texts)
    cost = (input_tokens * input_price + output_tokens * output_price) / 1e6
    return {
        "n_posts": len(texts),
        "model": model,
        "est_input_tokens": int(input_tokens),
        "est_output_tokens": int(output_tokens),
        "est_cost_usd": round(cost, 4),
        "est_cost_per_1k_posts_usd": round(cost / len(texts) * 1000, 2),
    }


# ---------------------------------------------------------------------------
# 3. Keyword-rule baseline (always runs — no API needed)
# ---------------------------------------------------------------------------

# KEYWORD_RULES (loaded from data/codebook.json above) are transparent keyword
# lists. Every keyword is matched as a whole word (case-insensitive); the
# category with the most hits wins, and ties and zero-hit posts fall through
# to DEFAULT_LABEL ("other").
_KEYWORD_PATTERNS = {
    category: [re.compile(rf"\b{re.escape(kw)}\b") for kw in keywords]
    for category, keywords in KEYWORD_RULES.items()
}


def keyword_label(text):
    """Label a post with the transparent keyword rules above.

    Returns one of ``LABELS``. This is intentionally simple: it exists so the
    validation workflow in the notebook can run without an API key, and as a
    reminder that *any* automated annotator — dictionary, classifier, or
    LLM — plugs into the same validation mechanics.
    """
    lowered = text.lower()
    scores = {
        category: sum(len(pattern.findall(lowered)) for pattern in patterns)
        for category, patterns in _KEYWORD_PATTERNS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0 or list(scores.values()).count(scores[best]) > 1:
        return DEFAULT_LABEL
    return best


def keyword_hits(text):
    """Return the keywords that matched ``text``, per category.

    The error analysis uses this to show *why* the baseline chose a label:
    no matches at all (it fell through to ``DEFAULT_LABEL``), a tie, or a
    keyword from the wrong category.
    """
    lowered = text.lower()
    return {
        category: [kw for kw, pattern in zip(KEYWORD_RULES[category], patterns)
                   for _ in pattern.findall(lowered)]
        for category, patterns in _KEYWORD_PATTERNS.items()
    }
