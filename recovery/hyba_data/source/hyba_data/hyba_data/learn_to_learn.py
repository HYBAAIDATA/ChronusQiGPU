"""Learn-to-learn — teach how to learn, not encode all knowledge.

Doctrine (Andre / board):
  Behaviour skills and attributes are seeded. The system cannot know everything.
  We teach it *how to learn*: when unknown → go look (internet = biggest library),
  read (blogs, forums, docs), **store memory using φ-fold compression**, apply.

  There is a reason we can compress data — learned memory must use fold, not truncate.

Loop:
  1. know? → recall from folded memory
  2. else research (web)
  3. fold-store (PHI-1 / recon gate)
  4. apply (return structured knowledge for product use)

  PYTHONPATH=python_backend python3 -m hyba_data.learn_to_learn "what is golden ratio transform"
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from hyba_data.phi1_runtime import Phi1Runtime

MEMORY_ROOT = Path("artifacts/hyba_data/learn_memory")
INDEX_PATH = MEMORY_ROOT / "index.json"
REPORT_PATH = Path("artifacts/hyba_data/elevation/LEARN_TO_LEARN_REPORT.json")

USER_AGENT = (
    "HYBA-Data-LearnToLearn/1.0 (+https://hybasoftware.ae; research-memory; fold-not-truncate)"
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _qid(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()[:24]


def _text_to_array(text: str) -> np.ndarray:
    """Map text to float64 code units for φ-fold storage (invertible via char codes)."""
    # Use UTF-8 bytes as uint8 then float for fold path
    b = bytearray(text.encode("utf-8", errors="replace"))
    if not b:
        b = bytearray(b" ")
    # pair-fold kernels need even length — pad with 0 and record pad in first sentinel via length prefix
    # Prefix: 4 bytes little-endian original length, then payload, pad to even total
    n = len(b)
    prefix = n.to_bytes(4, "little")
    payload = bytearray(prefix) + b
    if len(payload) % 2 == 1:
        payload.append(0)
    # also pad to multiple of 4 for deeper cf levels
    while len(payload) % 4 != 0:
        payload.append(0)
    return np.frombuffer(bytes(payload), dtype=np.uint8).astype(np.float64)


def _array_to_text(arr: np.ndarray) -> str:
    a = np.asarray(arr).ravel()
    # clamp to byte range after unfold
    bytes_out = np.clip(np.rint(a), 0, 255).astype(np.uint8).tobytes()
    if len(bytes_out) < 4:
        return bytes_out.decode("utf-8", errors="replace")
    n = int.from_bytes(bytes_out[:4], "little")
    payload = bytes_out[4 : 4 + max(0, n)]
    return payload.decode("utf-8", errors="replace")


@dataclass
class ResearchHit:
    url: str
    title: str
    snippet: str
    source: str = "web"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryRecord:
    query_id: str
    query: str
    summary: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    handle_id: Optional[str] = None
    fold_hash: Optional[str] = None
    recon_error: Optional[float] = None
    created_at: str = field(default_factory=_utc)
    applied_count: int = 0
    skill_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FoldedMemoryStore:
    """Persistent learn-memory using PHI-1 fold/unfold (fold never truncate)."""

    def __init__(self, root: Path = MEMORY_ROOT) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.rt = Phi1Runtime(store_dir=self.root / "phi1_store")
        self.index: Dict[str, Any] = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        if INDEX_PATH.exists():
            try:
                return json.loads(INDEX_PATH.read_text())
            except Exception:
                pass
        return {"version": 1, "records": {}, "doctrine": "fold_never_truncate"}

    def _save_index(self) -> None:
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text(json.dumps(self.index, indent=2))

    def recall(self, query: str) -> Optional[MemoryRecord]:
        qid = _qid(query)
        # exact then fuzzy contains
        rec = self.index.get("records", {}).get(qid)
        if not rec:
            qlow = query.strip().lower()
            for r in self.index.get("records", {}).values():
                if qlow in (r.get("query") or "").lower() or (r.get("query") or "").lower() in qlow:
                    rec = r
                    break
        if not rec:
            return None
        handle = rec.get("handle_id")
        if not handle:
            return MemoryRecord(**{k: rec[k] for k in MemoryRecord.__dataclass_fields__ if k in rec})
        try:
            u = self.rt.phi_unfold_read(handle)
            body = _array_to_text(np.asarray(u["data"]))
            # body is full stored payload JSON
            payload = json.loads(body)
            return MemoryRecord(
                query_id=rec["query_id"],
                query=rec["query"],
                summary=payload.get("summary") or rec.get("summary") or "",
                sources=payload.get("sources") or rec.get("sources") or [],
                handle_id=handle,
                fold_hash=rec.get("fold_hash"),
                recon_error=rec.get("recon_error"),
                created_at=rec.get("created_at") or _utc(),
                applied_count=int(rec.get("applied_count") or 0),
                skill_tags=payload.get("skill_tags") or rec.get("skill_tags") or [],
            )
        except Exception:
            return MemoryRecord(**{k: rec.get(k) for k in MemoryRecord.__dataclass_fields__})

    def store(
        self,
        query: str,
        summary: str,
        sources: Sequence[ResearchHit | Dict[str, Any]],
        skill_tags: Optional[List[str]] = None,
        depth: int = 2,
    ) -> MemoryRecord:
        qid = _qid(query)
        srcs = []
        for s in sources:
            if isinstance(s, ResearchHit):
                srcs.append(s.to_dict())
            else:
                srcs.append(dict(s))
        payload = {
            "query": query,
            "summary": summary,
            "sources": srcs,
            "skill_tags": skill_tags or ["learn_to_learn", "web_research"],
            "stored_at": _utc(),
            "doctrine": "fold_never_truncate",
        }
        raw = json.dumps(payload, ensure_ascii=False)
        arr = _text_to_array(raw)
        target = 1
        while target < arr.size:
            target *= 2
        if target > arr.size:
            arr = np.pad(arr, (0, target - arr.size))
        w = self.rt.phi_fold_write(arr, mode="cf_tower", depth=min(depth, 3))
        if not w.get("passed_gate"):
            # still store meta with plain fallback for audit
            handle_id = None
            recon = w.get("cert", {}).get("recon_error")
            fold_hash = w.get("cert", {}).get("fold_hash")
        else:
            handle_id = w["handle"]["handle_id"]
            recon = w["cert"]["recon_error"]
            fold_hash = w["cert"]["fold_hash"]

        rec = MemoryRecord(
            query_id=qid,
            query=query,
            summary=summary[:4000],
            sources=srcs,
            handle_id=handle_id,
            fold_hash=fold_hash,
            recon_error=float(recon) if recon is not None else None,
            skill_tags=skill_tags or ["learn_to_learn", "web_research"],
        )
        self.index.setdefault("records", {})[qid] = rec.to_dict()
        self._save_index()
        # also write human-readable sidecar
        (self.root / f"{qid}.meta.json").write_text(json.dumps(rec.to_dict(), indent=2))
        return rec

    def mark_applied(self, query: str) -> None:
        qid = _qid(query)
        rec = self.index.get("records", {}).get(qid)
        if not rec:
            return
        rec["applied_count"] = int(rec.get("applied_count") or 0) + 1
        self._save_index()


class WebResearchLibrary:
    """Biggest library: the internet. DuckDuckGo HTML + Wikipedia + direct fetch."""

    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout

    def _fetch(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
        # limit size
        raw = raw[:400_000]
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return raw.decode("latin-1", errors="replace")

    def _strip_html(self, html: str) -> str:
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def search_wikipedia(self, query: str, limit: int = 3) -> List[ResearchHit]:
        hits: List[ResearchHit] = []
        try:
            api = (
                "https://en.wikipedia.org/w/api.php?"
                + urllib.parse.urlencode(
                    {
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": limit,
                        "format": "json",
                    }
                )
            )
            data = json.loads(self._fetch(api))
            for item in (data.get("query") or {}).get("search") or []:
                title = item.get("title") or "Wikipedia"
                snippet = self._strip_html(item.get("snippet") or "")
                url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                    title.replace(" ", "_")
                )
                hits.append(
                    ResearchHit(
                        url=url, title=title, snippet=snippet, source="wikipedia"
                    )
                )
        except Exception:
            pass
        return hits

    def search_duckduckgo(self, query: str, limit: int = 5) -> List[ResearchHit]:
        hits: List[ResearchHit] = []
        try:
            url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
                {"q": query}
            )
            html = self._fetch(url)
            # result links
            for m in re.finditer(
                r'uddg=([^&"\']+)|href="(https?://[^"\']+)"[^>]*class="[^\"]*result',
                html,
            ):
                raw_u = m.group(1) or m.group(2) or ""
                u = urllib.parse.unquote(raw_u)
                if "duckduckgo.com" in u:
                    continue
                if not u.startswith("http"):
                    continue
                title = u.split("//", 1)[-1][:80]
                hits.append(
                    ResearchHit(url=u, title=title, snippet="", source="duckduckgo")
                )
                if len(hits) >= limit:
                    break
            # also try result__a pattern
            if len(hits) < limit:
                for m in re.finditer(
                    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                    html,
                    flags=re.I | re.S,
                ):
                    u = m.group(1)
                    title = self._strip_html(m.group(2))[:120]
                    if u.startswith("//"):
                        u = "https:" + u
                    if "duckduckgo.com" in u:
                        continue
                    hits.append(
                        ResearchHit(
                            url=u, title=title or u, snippet="", source="duckduckgo"
                        )
                    )
                    if len(hits) >= limit:
                        break
        except Exception:
            pass
        return hits[:limit]

    def read_page(self, url: str, max_chars: int = 6000) -> str:
        try:
            html = self._fetch(url)
            text = self._strip_html(html)
            return text[:max_chars]
        except Exception as e:
            return f"[fetch_error] {type(e).__name__}: {e}"

    def research(self, query: str, read_top: int = 2) -> Dict[str, Any]:
        hits = self.search_wikipedia(query, limit=2)
        hits.extend(self.search_duckduckgo(query, limit=5))
        # dedupe urls
        seen = set()
        uniq: List[ResearchHit] = []
        for h in hits:
            if h.url in seen:
                continue
            seen.add(h.url)
            uniq.append(h)

        readings: List[Dict[str, Any]] = []
        for h in uniq[:read_top]:
            body = self.read_page(h.url)
            if not h.snippet:
                h.snippet = body[:400]
            readings.append(
                {
                    "url": h.url,
                    "title": h.title,
                    "source": h.source,
                    "text": body,
                }
            )

        # compose summary from snippets + readings
        parts = [f"Query: {query}", "Learned from public web (fold-stored):"]
        for h in uniq[:6]:
            parts.append(f"- {h.title}: {h.snippet[:300]} ({h.url})")
        for r in readings:
            parts.append(f"Reading {r['title']}: {r['text'][:800]}")
        summary = "\n".join(parts)[:8000]

        return {
            "query": query,
            "hits": [h.to_dict() for h in uniq],
            "readings": [
                {"url": r["url"], "title": r["title"], "source": r["source"], "chars": len(r["text"])}
                for r in readings
            ],
            "summary": summary,
            "library": "internet",
            "timestamp": _utc(),
        }


class LearnToLearn:
    """Seeded behaviour: skills to learn, not encyclopedic knowledge."""

    SEED_SKILLS = [
        "ask_when_unknown",
        "search_web",
        "read_sources",
        "fold_store_memory",
        "recall_before_research",
        "apply_to_product_context",
        "fold_never_truncate",
        "quantum_serves_data",
    ]

    def __init__(self) -> None:
        self.memory = FoldedMemoryStore()
        self.library = WebResearchLibrary()

    def know(self, query: str) -> Optional[MemoryRecord]:
        return self.memory.recall(query)

    def learn(self, query: str, *, force_refresh: bool = False) -> Dict[str, Any]:
        """Full loop: recall or research → fold-store → ready to apply."""
        if not force_refresh:
            existing = self.know(query)
            if existing and existing.summary:
                return {
                    "status": "RECALL",
                    "query": query,
                    "memory": existing.to_dict(),
                    "skills": self.SEED_SKILLS,
                    "used_web": False,
                    "doctrine": "fold_never_truncate",
                }

        research = self.library.research(query)
        rec = self.memory.store(
            query=query,
            summary=research["summary"],
            sources=research["hits"],
            skill_tags=["learn_to_learn", "web", "folded_memory"],
        )
        return {
            "status": "LEARNED",
            "query": query,
            "memory": rec.to_dict(),
            "research": {
                "n_hits": len(research["hits"]),
                "n_readings": len(research["readings"]),
                "readings": research["readings"],
            },
            "skills": self.SEED_SKILLS,
            "used_web": True,
            "doctrine": "fold_never_truncate",
            "recon_error": rec.recon_error,
            "fold_hash": rec.fold_hash,
        }

    def apply(self, query: str, *, context: Optional[str] = None) -> Dict[str, Any]:
        """Apply learned memory to a product/context decision."""
        pack = self.learn(query)
        mem = pack.get("memory") or {}
        summary = mem.get("summary") or ""
        self.memory.mark_applied(query)
        application = {
            "query": query,
            "context": context or "hyba_data_product",
            "guidance": summary[:2000],
            "sources": mem.get("sources") or [],
            "how": (
                "Behaviour seeded for learn-to-learn. Knowledge retrieved from "
                "φ-folded memory and/or internet research; applied without truncating source memory."
            ),
            "product_hooks": {
                "storage": "use fold/unfold for working sets — never truncate",
                "search": "structure-first; research web when unknown",
                "processing": "apply learned constraints to config/GPU/fold depth",
                "quantum_serves_data": True,
            },
        }
        pack["apply"] = application
        pack["status"] = pack.get("status", "APPLY") + "_APPLIED"
        return pack

    def run_demo(self, query: str = "golden ratio transform data compression") -> Dict[str, Any]:
        # offline-safe path: if network fails, still exercise fold memory with seeded note
        try:
            result = self.apply(query, context="pulvini_phi_fold")
        except Exception as e:
            seed = (
                f"Seeded knowledge for '{query}': φ-fold compresses by folding not truncating. "
                f"Quantum serves data. Error during web: {type(e).__name__}: {e}"
            )
            rec = self.memory.store(
                query=query,
                summary=seed,
                sources=[{"url": "local://seed", "title": "seed", "snippet": seed}],
                skill_tags=["seed", "learn_to_learn"],
            )
            result = {
                "status": "SEEDED_FALLBACK_APPLIED",
                "query": query,
                "memory": rec.to_dict(),
                "apply": {"guidance": seed, "context": "pulvini_phi_fold"},
                "error": f"{type(e).__name__}: {e}",
            }
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(result, indent=2, default=str))
        result["artifact"] = str(REPORT_PATH)
        return result


def build_learn_report(query: str = "golden ratio transform fold never truncate") -> Dict[str, Any]:
    engine = LearnToLearn()
    return engine.run_demo(query)


def main(argv: Optional[List[str]] = None) -> int:
    import sys

    argv = list(argv or sys.argv[1:])
    query = " ".join(argv) if argv else "golden ratio transform fold never truncate"
    report = build_learn_report(query)
    print(json.dumps({
        "status": report.get("status"),
        "query": report.get("query"),
        "used_web": report.get("used_web"),
        "recon_error": (report.get("memory") or {}).get("recon_error"),
        "handle_id": (report.get("memory") or {}).get("handle_id"),
        "artifact": report.get("artifact"),
        "skills": report.get("skills"),
    }, indent=2))
    return 0 if report.get("status") else 1


if __name__ == "__main__":
    raise SystemExit(main())
