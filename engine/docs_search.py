"""Documentation search helpers for LQoSync.

The docs search is intentionally local/read-only. It indexes Markdown files from
``docs/content`` plus the key operator docs and manifest entries, then returns
small excerpts suitable for the WebUI and API.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


DEFAULT_DOC_FILES = [
    "README.md",
    "FULL_DOCUMENTATION.md",
    "INSTALLATION.md",
    "GIT_INSTALL.md",
    "UNINSTALLATION.md",
    "BARE_METAL_INSTALL.md",
    "DOCKER_INSTALL.md",
    "docs/ABOUT_MODULE_OPERATOR_GUIDE.md",
    "docs/SMART_POLICY_CENTER.md",
    "docs/SMART_INSIGHTS.md",
    "docs/SMART_LIFECYCLE.md",
    "docs/SMART_SETUP_REPAIR.md",
    "docs/AI_ASSISTED_DEVELOPMENT.md",
]


@dataclass
class DocEntry:
    id: str
    title: str
    path: str
    anchor: str = ""
    summary: str = ""
    text: str = ""
    section: str = "Documentation"

    def public_dict(self) -> dict:
        data = asdict(self)
        # Avoid returning huge text bodies in search results.
        data.pop("text", None)
        return data


def _slug(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "doc"


def _title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip() or fallback
    return fallback


def _summary_from_markdown(text: str, max_len: int = 180) -> str:
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        return (line[: max_len - 1] + "…") if len(line) > max_len else line
    return ""


def _read_manifest(root: Path) -> dict:
    manifest = root / "docs" / "docs_manifest.json"
    if not manifest.exists():
        return {}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_docs_index(root: str | Path | None = None) -> list[DocEntry]:
    root_path = Path(root or Path(__file__).resolve().parents[1]).resolve()
    manifest = _read_manifest(root_path)
    seen: set[str] = set()
    entries: list[DocEntry] = []

    def add_file(rel_path: str, key: str | None = None, meta: dict | None = None):
        if not rel_path:
            return
        rel_path = rel_path.lstrip("/")
        path = root_path / rel_path
        if not path.exists() or not path.is_file():
            return
        doc_id = _slug(key or rel_path)
        if doc_id in seen:
            return
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return
        meta = meta or {}
        title = meta.get("title") or _title_from_markdown(text, path.stem.replace("_", " ").title())
        summary = meta.get("summary") or meta.get("description") or _summary_from_markdown(text)
        entries.append(
            DocEntry(
                id=doc_id,
                title=title,
                path=rel_path,
                anchor=meta.get("anchor", ""),
                summary=summary,
                text=text,
                section=(rel_path.split("/")[0] if "/" in rel_path else "root"),
            )
        )
        seen.add(doc_id)

    for key, meta in manifest.items():
        if isinstance(meta, dict):
            add_file(str(meta.get("file") or ""), key=key, meta=meta)

    for path in sorted((root_path / "docs" / "content").glob("*.md")):
        add_file(str(path.relative_to(root_path)))

    for rel in DEFAULT_DOC_FILES:
        add_file(rel)

    return sorted(entries, key=lambda d: (d.section, d.title.lower()))


def _tokenize(query: str) -> list[str]:
    return [t for t in re.split(r"\s+", (query or "").strip().lower()) if t]


def _excerpt(text: str, tokens: Iterable[str], max_len: int = 260) -> str:
    lower = text.lower()
    first = None
    for token in tokens:
        pos = lower.find(token.lower())
        if pos >= 0:
            first = pos if first is None else min(first, pos)
    if first is None:
        return _summary_from_markdown(text, max_len=max_len)
    start = max(0, first - 90)
    end = min(len(text), first + max_len)
    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


def search_docs(query: str, root: str | Path | None = None, limit: int = 20) -> dict:
    entries = build_docs_index(root)
    tokens = _tokenize(query)
    if not tokens:
        return {
            "query": query or "",
            "total": len(entries),
            "results": [dict(e.public_dict(), score=0, excerpt=e.summary) for e in entries[:limit]],
        }

    results = []
    for entry in entries:
        hay_title = entry.title.lower()
        hay_summary = entry.summary.lower()
        hay_path = entry.path.lower()
        hay_text = entry.text.lower()
        score = 0
        for token in tokens:
            if token in hay_title:
                score += 20
            if token in hay_summary:
                score += 10
            if token in hay_path:
                score += 6
            count = hay_text.count(token)
            if count:
                score += min(count, 12)
        if score:
            results.append(dict(entry.public_dict(), score=score, excerpt=_excerpt(entry.text, tokens)))
    results.sort(key=lambda x: (-x["score"], x["title"].lower()))
    return {"query": query, "total": len(results), "results": results[:limit]}


def get_doc(doc_id: str, root: str | Path | None = None) -> DocEntry | None:
    doc_id = _slug(doc_id)
    for entry in build_docs_index(root):
        if entry.id == doc_id:
            return entry
    return None
