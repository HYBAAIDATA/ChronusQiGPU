path = "c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/frontend/app/mining/page.tsx"
with open(path, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

open_brace = content.count("{")
close_brace = content.count("}")
open_paren = content.count("(")
close_paren = content.count(")")
print(f"{{{open_brace} vs }{{{close_brace}: diff={open_brace-close_brace}")
print(f"({open_paren} vs ){close_paren}: diff={open_paren-close_paren}")

import re
for m in re.finditer(r'\)\}', content):
    start = max(0, m.start() - 50)
    end = min(len(content), m.end() + 10)
    snippet = content[start:end].replace("\n", "\\n")
    print(f"  )}} pattern at pos {m.start()}: ...{snippet}...")
