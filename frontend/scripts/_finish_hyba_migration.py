from pathlib import Path
import re


def main() -> None:
    print("=== index.css tokens ===")
    css_path = Path("frontend/src/index.css")
    css = css_path.read_text(encoding="utf-8")
    css_fixes = [
        ("  --hyba-grey: var(--hyba-grey);", "  --hyba-grey: #718096;"),
        ("  --hyba-white: var(--hyba-white);", "  --hyba-white: #ffffff;"),
        ("  --hyba-success: var(--hyba-success);", "  --hyba-success: #12b76a;"),
        ("  --hyba-success-ink: var(--hyba-success-ink);", "  --hyba-success-ink: #067647;"),
        ("  --hyba-danger: var(--hyba-danger);", "  --hyba-danger: #b42318;"),
        ("  --hyba-danger-bright: var(--hyba-danger-bright);", "  --hyba-danger-bright: #df1b41;"),
        ("  --hyba-hypothesis: var(--hyba-hypothesis);", "  --hyba-hypothesis: #5b21b6;"),
    ]
    for old, new in css_fixes:
        if old not in css:
            print("  WARN css missing:", old)
        else:
            css = css.replace(old, new)
    if ".metric-prize" not in css and ".hyba-prize" not in css:
        css = (
            css.rstrip()
            + "

/* Prize metrics - gold for key KPI numbers only */
"
            + ".metric-prize,
.hyba-prize {
"
            + "  color: var(--hyba-gold);
"
            + "  font-variant-numeric: tabular-nums;
"
            + "}
"
        )
    css_path.write_text(css, encoding="utf-8", newline="
")
    print("  index.css token self-refs fixed")
