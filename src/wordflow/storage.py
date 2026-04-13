"""Persistent storage for Wordflow articles."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional
from uuid import uuid4

from .parsing import split_lines, split_sentences

ContentMode = Literal["article", "note"]


@dataclass
class Article:
    article_id: str
    title: str
    body: str
    mode: ContentMode
    sentences: List[str]
    completed_count: int = 0


def _default_storage_path() -> Path:
    """Choose a writable default path, with an env override for testing."""
    override = os.environ.get("WORDFLOW_DATA_PATH") or os.environ.get("SPELLLANE_DATA_PATH")
    if override:
        return Path(override).expanduser()

    preferred = Path.home() / ".wordflow" / "articles.json"
    legacy = Path.home() / ".spelllane" / "articles.json"
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        if not preferred.exists() and legacy.exists():
            return legacy
        return preferred
    except PermissionError:
        fallback = Path.cwd() / ".wordflow" / "articles.json"
        legacy_fallback = Path.cwd() / ".spelllane" / "articles.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        if not fallback.exists() and legacy_fallback.exists():
            return legacy_fallback
        return fallback


class ArticleStore:
    """Load and save articles from a local JSON file."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _default_storage_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_articles(self) -> List[Article]:
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(payload, list):
            return []

        articles = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            mode = self.normalize_mode(str(item.get("mode", "article")))
            article_id = str(item.get("article_id") or uuid4())
            title = str(item.get("title", "")).strip()
            body = str(item.get("body", "")).strip()
            if mode == "note" and not title:
                title = self.default_note_title()

            raw_sentences = item.get("sentences")
            if isinstance(raw_sentences, list):
                sentences = [str(sentence).strip() for sentence in raw_sentences if str(sentence).strip()]
            else:
                sentences = self.build_segments(body, mode)

            completed_count = item.get("completed_count", 0)
            if not isinstance(completed_count, int):
                try:
                    completed_count = int(completed_count)
                except (ValueError, TypeError):
                    completed_count = 0
            completed_count = max(0, min(3, completed_count))

            articles.append(
                Article(
                    article_id=article_id,
                    title=title,
                    body=body,
                    mode=mode,
                    sentences=sentences,
                    completed_count=completed_count,
                )
            )
        return articles

    def save_articles(self, articles: List[Article]) -> None:
        payload = [asdict(article) for article in articles]
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def upsert_article(
        self,
        articles: List[Article],
        title: str,
        body: str,
        mode: ContentMode = "article",
        article_id: Optional[str] = None,
    ) -> List[Article]:
        cleaned_title = title.strip()
        cleaned_body = body.strip()
        normalized_mode = self.normalize_mode(mode)
        if normalized_mode == "note" and not cleaned_title:
            cleaned_title = self.default_note_title()
        sentences = self.build_segments(cleaned_body, normalized_mode)

        existing_completed_count = 0
        if article_id:
            for article in articles:
                if article.article_id == article_id:
                    existing_completed_count = article.completed_count
                    break

        article = Article(
            article_id=article_id or str(uuid4()),
            title=cleaned_title,
            body=cleaned_body,
            mode=normalized_mode,
            sentences=sentences,
            completed_count=existing_completed_count,
        )

        updated = []
        replaced = False
        for current in articles:
            if current.article_id == article.article_id:
                updated.append(article)
                replaced = True
            else:
                updated.append(current)
        if not replaced:
            updated.append(article)

        self.save_articles(updated)
        return updated

    def delete_article(self, articles: List[Article], article_id: str) -> List[Article]:
        updated = [article for article in articles if article.article_id != article_id]
        self.save_articles(updated)
        return updated

    def build_segments(self, body: str, mode: ContentMode) -> List[str]:
        normalized_mode = self.normalize_mode(mode)
        if normalized_mode == "note":
            return split_lines(body)
        return split_sentences(body)

    def normalize_mode(self, mode: str) -> ContentMode:
        return "note" if mode == "note" else "article"

    def default_note_title(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
