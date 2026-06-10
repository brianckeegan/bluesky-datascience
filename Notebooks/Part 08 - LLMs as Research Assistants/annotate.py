"""Helpers for LLM-assisted annotation in Part 08 of the bluesky-datascience tutorials.

This module contains three groups of tools:

1. ``CODEBOOK`` and ``build_prompt`` — the labeling instructions we give to
   human coders and to a large language model, and the prompt template that
   wraps them around a post.
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

# ---------------------------------------------------------------------------
# 1. The codebook
# ---------------------------------------------------------------------------

LABELS = ["politics", "science_tech", "other"]

DEFAULT_MODEL = "claude-sonnet-4-6"

CODEBOOK = """\
TASK: Assign each Bluesky post exactly one topic label.

LABELS

politics — The post is primarily about government, elections, political
  parties, politicians, courts, legislation, public policy (national, state,
  or local — including housing and urban policy), war and geopolitics, or
  criticism of political news media and pundits.

science_tech — The post is primarily about science, research, academia,
  higher education, teaching, grants, scholarly publishing, data science,
  AI/LLMs, software, or the technology industry, where the practice or
  culture of science/technology (not a political actor) is the main subject.

other — Everything else: personal life, jokes and memes without a clearly
  political or scientific/technical referent, pop culture, music, food,
  sports, local community chatter, and posts whose topic cannot be
  determined from the text alone.

DECISION RULES

1. Code the post's PRIMARY topic — what the post is mostly about, not every
   topic it touches.
2. If the post criticizes or comments on political actors or government
   policy, code politics even when the domain affected is science or the
   university (e.g., political defunding of research agencies → politics).
3. If the post is about the practice or culture of research, academia, AI,
   or technology without a political actor as the main target, code
   science_tech (e.g., complaints about peer review, jokes about LLM
   prompting → science_tech).
4. Self-promotion of published work (columns, talks, papers) is coded by the
   topic of the work itself.
5. Jokes, memes, and one-liners are coded by their referent; if the referent
   is not clearly political or scientific/technical, code other.
6. If the topic is genuinely undecidable from the text alone (e.g., a quip
   reacting to an image we cannot see), code other.

EDGE-CASE GUIDANCE

- Population/eugenics discourse framed as a political-ideological project →
  politics.
- Platform economics and AI-industry finances (bubbles, valuations) →
  science_tech, unless a politician or policy is the main target.
- Campus free-speech fights involving governments or pundits → politics
  (rule 2); routine academic-life posts (grading, conferences) →
  science_tech.
"""


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
                max_tokens=256,
                messages=[{"role": "user", "content": build_prompt(codebook, text)}],
            )
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


# Published prices per million tokens (June 2026): input, output.
MODEL_PRICES_PER_MTOK = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-8": (5.00, 25.00),
}


def estimate_annotation_cost(texts, codebook=CODEBOOK, model=DEFAULT_MODEL,
                             output_tokens_per_post=30):
    """Back-of-envelope cost estimate for annotating ``texts`` with ``model``.

    Uses the rough heuristic of ~4 characters per token (the official
    ``count_tokens`` endpoint gives exact numbers when you have a key).
    Returns a dict of token and dollar estimates.
    """
    input_price, output_price = MODEL_PRICES_PER_MTOK[model]
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

# Transparent keyword rules. Every keyword is matched as a whole word
# (case-insensitive); the category with the most hits wins, ties and
# zero-hit posts fall through to "other".
KEYWORD_RULES = {
    "politics": [
        "trump", "biden", "democrat", "democrats", "democratic", "republican",
        "republicans", "gop", "congress", "congressional", "senate",
        "senators", "scotus", "court", "courts", "election", "elections",
        "vote", "votes", "voters", "voting", "ballot", "ballots", "policy",
        "politics", "political", "politicians", "president", "governor",
        "amendment", "constitution", "legislation", "legislative", "war",
        "iran", "deport", "deporting", "fascist", "white house", "doj",
        "dnc", "epstein", "gerontocracy", "neoliberal", "progressive",
        "conservative", "left-wing", "right-wing", "far-right", "eugenics",
        "eugenicist", "supremacy", "white supremacist", "free speech",
        "regime", "nominees",
    ],
    "science_tech": [
        "ai", "llm", "llms", "research", "researchers", "science",
        "scientific", "scientist", "scientists", "university",
        "universities", "professor", "professoriate", "academic",
        "academia", "grant", "grants", "data", "wikipedia", "claude",
        "anthropic", "model", "models", "citation", "citations", "scholar",
        "scholars", "scholarship", "journal", "peer review", "tech",
        "techbros", "tech bros", "startup", "software", "code", "coding",
        "matplotlib", "agent", "agents", "mcp", "api", "grades", "teaching",
        "classroom", "conference", "conferences", "protocol", "openalex",
    ],
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
        category: sum(
            len(re.findall(rf"\b{re.escape(kw)}\b", lowered)) for kw in keywords
        )
        for category, keywords in KEYWORD_RULES.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0 or list(scores.values()).count(scores[best]) > 1:
        return "other"
    return best
