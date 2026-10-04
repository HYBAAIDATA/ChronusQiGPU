import re
import pathlib

for p in sorted(pathlib.Path("chronus/v33").rglob("*.py")):
    rel = p.as_posix()
    names = re.findall(r"^(?:def |class )(\w+)", p.read_text(encoding="utf-8"), re.M)
    if names:
        print(rel, "->", ", ".join(names[:25]))
