"""Fill the results section of docs/EUCLID_V17_RESEARCH_RELEASE.md from the report.

Every number in that section is read from reports/euclid_v17/research_report.json;
nothing is typed by hand.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from euclid.cognition.research.report import comparison_table, render  # noqa: E402

MARKER_START = "<!-- RESULTS -->"
MARKER_END = "<!-- /RESULTS -->"


def main() -> int:
    report = json.loads((ROOT / "reports/euclid_v17/research_report.json").read_text(
        encoding="utf-8"))
    body = render(report)
    # drop the report's own title; keep everything else verbatim
    body = body.split("\n", 2)[2] if body.startswith("# ") else body
    section = "\n".join([
        MARKER_START,
        "## Results (generated from `reports/euclid_v17/research_report.json`)",
        "",
        body.replace("\n## ", "\n### "),
        MARKER_END,
    ])
    doc_path = ROOT / "docs/EUCLID_V17_RESEARCH_RELEASE.md"
    doc = doc_path.read_text(encoding="utf-8")
    if MARKER_END in doc:
        start = doc.index(MARKER_START)
        end = doc.index(MARKER_END) + len(MARKER_END)
        doc = doc[:start] + section + doc[end:]
    else:
        doc = doc.replace(MARKER_START, section, 1)
    doc_path.write_text(doc, encoding="utf-8")
    print("\n".join(comparison_table(report)[-1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
