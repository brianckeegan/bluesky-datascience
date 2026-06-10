"""Text preprocessing helpers for Part 06 - Natural Language Processing.

Short social media posts need different preprocessing than books or news
articles: they are full of URLs, @-handles, #hashtags, emoji, and
contractions. These helpers implement a small, transparent pipeline —
clean, tokenize, rejoin — that the notebook applies before counting words
and fitting topic models. Sentiment analysis with VADER deliberately skips
this pipeline and works on the raw text, because VADER's lexicon uses
punctuation, capitalization, and emoticons as signal.
"""

import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Matches http(s) URLs and bare www. links.
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

# Bluesky clients render links as truncated *display* URLs without the
# scheme (e.g., "boulderreportinglab.org/local-news/..."), so the text we
# collect is full of bare domains. This matches anything shaped like
# domain.tld with optional path, requiring each dotted part to be at least
# two characters so abbreviations like "e.g." and "U.S." survive.
DISPLAY_URL_PATTERN = re.compile(r"\b\w[\w\-]*(?:\.[\w\-]{2,})+(?:/\S*)?")

# Matches @-mentions of Bluesky handles, which are domain names
# (e.g., @brianckeegan.com or @example.bsky.social).
HANDLE_PATTERN = re.compile(r"@[A-Za-z0-9.\-]+")

# After cleaning, a token is a run of two or more letters.
TOKEN_PATTERN = re.compile(r"[a-z]{2,}")

# Leftovers from contractions once apostrophes are removed ("don't" ->
# "dont"), plus platform-flavored filler that sklearn's English list does
# not cover. Extend this set for your own corpus.
CUSTOM_STOPWORDS = frozenset({
    "im", "ive", "id", "ill", "dont", "didnt", "doesnt", "isnt", "wasnt",
    "wont", "cant", "couldnt", "wouldnt", "shouldnt", "youre", "youve",
    "youll", "theyre", "theyve", "thats", "whats", "heres", "theres",
    "hes", "shes", "weve", "lets", "gonna", "gotta", "lol", "tbh", "imo",
    "via", "amp", "just", "like", "really", "going", "got", "think",
})

# The full stopword list used by default throughout the notebook.
STOPWORDS = frozenset(ENGLISH_STOP_WORDS) | CUSTOM_STOPWORDS


def clean(text):
    """Normalize a raw post: strip URLs and @-handles, keep hashtag words.

    Lowercases, removes URLs and @-mentions entirely, turns "#hashtag"
    into the plain word "hashtag" (the tag is content!), deletes
    apostrophes so contractions become single tokens ("don't" -> "dont"),
    and collapses whitespace. Emoji and other punctuation survive here and
    are dropped later by the tokenizer.
    """
    text = text.lower()
    text = URL_PATTERN.sub(" ", text)
    text = HANDLE_PATTERN.sub(" ", text)
    text = DISPLAY_URL_PATTERN.sub(" ", text)
    text = text.replace("#", " ")     # keep the hashtag's word
    text = text.replace("’", "").replace("'", "")  # contractions
    return " ".join(text.split())


def tokenize(text, stopwords=STOPWORDS):
    """Clean a raw post and return its content tokens as a list.

    Tokens are runs of two or more letters, so numbers, emoji, and
    punctuation are dropped. Tokens in ``stopwords`` are removed. Pass
    ``stopwords=frozenset()`` to keep everything.
    """
    return [
        token
        for token in TOKEN_PATTERN.findall(clean(text))
        if token not in stopwords
    ]


def preprocess(text, stopwords=STOPWORDS):
    """Clean and tokenize a post, returning tokens rejoined by spaces.

    This is the convenient form for scikit-learn's vectorizers: store the
    result in a DataFrame column and vectorize with
    ``CountVectorizer(token_pattern=r"\\S+", lowercase=False)``.
    """
    return " ".join(tokenize(text, stopwords=stopwords))


def log_odds(counts_a, counts_b, alpha=0.5):
    """Smoothed log-odds ratio of word use in group A versus group B.

    ``counts_a`` and ``counts_b`` are aligned Series of word counts (the
    same vocabulary in the same order). Adds ``alpha`` to every count so
    words unseen in one group do not produce infinities, then returns
    log [ p_a / (1 - p_a) ] - log [ p_b / (1 - p_b) ] as a Series sorted
    descending: large positive values are distinctive of A, large negative
    values distinctive of B. This is the simple version of the log-odds
    measure popularized by Monroe, Colaresi, & Quinn (2008).
    """
    a = counts_a + alpha
    b = counts_b + alpha
    odds_a = a / (a.sum() - a)
    odds_b = b / (b.sum() - b)
    return (np.log(odds_a) - np.log(odds_b)).sort_values(ascending=False)


def top_topic_words(lda_model, feature_names, n_words=12):
    """Tabulate the highest-weight words for each topic in a fitted LDA.

    Returns a DataFrame with one row per topic and columns word_1 ...
    word_n, ordered from most to less probable under each topic.
    """
    rows = {}
    for topic_idx, weights in enumerate(lda_model.components_):
        top_idx = weights.argsort()[::-1][:n_words]
        rows[f"topic_{topic_idx}"] = [feature_names[i] for i in top_idx]
    table = pd.DataFrame.from_dict(rows, orient="index")
    table.columns = [f"word_{i + 1}" for i in range(n_words)]
    return table
