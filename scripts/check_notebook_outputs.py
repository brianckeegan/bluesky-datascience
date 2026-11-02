"""Fail if executed notebooks contain errors or deprecation-family warnings.

CI executes the notebooks with ``--allow-errors`` so that one failing cell
doesn't hide failures further down. That makes nbconvert "succeed" no matter
what, so this script reads the executed outputs and fails the build instead.

It fails on:
  * any cell whose output is an exception (``output_type == "error"``), and
  * any warning that says code will break in a future release
    (DeprecationWarning, FutureWarning, pandas' PandasNWarning, Pydantic
    deprecations) or that a model is unidentified (statsmodels'
    SingularMatrixWarning: the symptom Part 05 showed before issue #16).

Other warnings are printed but don't fail the build.

Usage:  python scripts/check_notebook_outputs.py NOTEBOOK.ipynb [...]
"""

import json
import re
import sys
from pathlib import Path

ANSI = re.compile("\x1b" + r"\[[0-9;]*m")
WARNING = re.compile(r"(\w*Warning): (.*)")
FAILING_WARNINGS = re.compile(
    r"^(DeprecationWarning|PendingDeprecationWarning|FutureWarning|"
    r"Pandas\d+Warning|PydanticDeprecated\w*|SingularMatrixWarning)$"
)


def problems(path):
    """Return (failures, notes) for one executed notebook."""
    failures, notes = [], []
    notebook = json.loads(Path(path).read_text())
    for index, cell in enumerate(notebook["cells"]):
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                message = ANSI.sub("", output.get("evalue", ""))[:200]
                failures.append(f"cell {index}: {output.get('ename')}: {message}")
            elif output.get("name") == "stderr":
                for line in "".join(output.get("text", "")).splitlines():
                    match = WARNING.search(line)
                    if not match:
                        continue
                    entry = f"cell {index}: {match.group(1)}: {match.group(2)[:200]}"
                    (failures if FAILING_WARNINGS.match(match.group(1)) else notes).append(entry)
    return failures, notes


def main(paths):
    if not paths:
        print(__doc__)
        return 2
    failed = False
    for path in paths:
        failures, notes = problems(path)
        status = "FAIL" if failures else "ok"
        print(f"[{status}] {path}")
        for entry in failures:
            print(f"    ERROR   {entry}")
        for entry in notes:
            print(f"    warning {entry}")
        failed = failed or bool(failures)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
