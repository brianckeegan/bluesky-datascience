"""Fail on prose that describes the retired case-study account, or that quotes
numbers from one particular run (issue #9).

PR #5 switched the case study from a personal academic account to nytimes.com,
but interpretation paragraphs kept describing the old account ("the author...
who has opted in") and quoting numbers ("in our run, about 25...") that no
longer matched the outputs above them. This check scans the prose of every
notebook (markdown cells) and R Markdown document (text outside code chunks).

A line can opt out with an HTML comment containing "stale-prose: ok" when a
match is intentional (e.g. a sentence about the history of the series).

Usage (from the repository root):
    python scripts/check_stale_prose.py [paths...]   # default: all tutorials
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATTERNS = {
    "retired case-study account": [
        r"brianckeegan\.com",
        r"did:plc:lse7",
        # "the author feed" is the endpoint (getAuthorFeed), not the retired author
        r"\bthe author(?:'s)? (?:own )?(?:account|posts|history)\b",
        r"\bthe author's (?:own )?feed\b",
        r"\bthe author\b[^.\n]{0,40}\b(?:opted|consent)",
        r"\b(?:who|which) (?:has|have) opted in\b",
        r"\bconsent(?:ed|ing) (?:ego|author|seed|account)\b",
        r"\b(?:seed|ego) account consented\b",
        r"\bacademic (?:seed|account|author|ego)\b",
        r"\bthe individual academic\b",
        r"\bthe author lives\b",
    ],
    "number quoted from one run": [
        r"\b[Ii]n (?:our|this|my) (?:run|execution)\b[^.\n]{0,60}\d",
        r"\b[Ww]hen (?:we|I) ran (?:this|it)\b[^.\n]{0,60}\d",
    ],
}
COMPILED = [(kind, re.compile(p)) for kind, ps in PATTERNS.items() for p in ps]
OPT_OUT = "stale-prose: ok"


def prose_lines(path):
    """Yield (location, line) for the prose of a notebook or R Markdown file."""
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text(encoding="utf-8"))
        for i, cell in enumerate(nb["cells"]):
            if cell["cell_type"] == "markdown":
                for line in "".join(cell["source"]).splitlines():
                    yield f"cell {i}", line
    else:
        in_chunk = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("```"):
                in_chunk = not in_chunk
                continue
            if not in_chunk:
                yield f"line {n}", line


def main(argv):
    paths = [Path(a) for a in argv] or sorted(
        list(ROOT.glob("Notebooks/**/*.ipynb")) + list(ROOT.glob("RMarkdown/**/*.Rmd")))
    found = 0
    for path in paths:
        if ".ipynb_checkpoints" in path.parts:
            continue
        for where, line in prose_lines(path):
            if OPT_OUT in line:
                continue
            for kind, pattern in COMPILED:
                match = pattern.search(line)
                if match:
                    found += 1
                    try:
                        rel = path.resolve().relative_to(ROOT)
                    except ValueError:
                        rel = path
                    print(f"[{kind}] {rel} {where}: ...{line[max(0, match.start() - 40):match.end() + 40]}...")
                    break
    print(f"{found} stale-prose problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
