"""Filed analytics claims. The gate reads the count."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PatentRegister:
    _titles: list[str] = field(default_factory=list)

    def file(self, title: str) -> int:
        if not title:
            raise ValueError("title is required")
        self._titles.append(title)
        return len(self._titles)

    def count(self) -> int:
        return len(self._titles)

    def titles(self) -> tuple[str, ...]:
        return tuple(self._titles)
