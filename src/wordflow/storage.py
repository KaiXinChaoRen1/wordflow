"""Persistent storage for Wordflow articles."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from .parsing import split_sentences


@dataclass
class Article:
    article_id: str
    title: str
    body: str
    sentences: List[str]


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

        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        articles = []
        for item in payload:
            sentences = item.get("sentences") or split_sentences(item.get("body", ""))
            articles.append(
                Article(
                    article_id=item["article_id"],
                    title=item["title"],
                    body=item["body"],
                    sentences=sentences,
                )
            )
        return articles

    def save_articles(self, articles: List[Article]) -> None:
        payload = [asdict(article) for article in articles]
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def upsert_article(
        self, articles: List[Article], title: str, body: str, article_id: Optional[str] = None
    ) -> List[Article]:
        cleaned_title = title.strip()
        cleaned_body = body.strip()
        sentences = split_sentences(cleaned_body)
        article = Article(
            article_id=article_id or str(uuid4()),
            title=cleaned_title,
            body=cleaned_body,
            sentences=sentences,
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
