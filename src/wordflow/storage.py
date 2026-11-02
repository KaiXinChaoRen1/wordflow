"""Persistent storage for Wordflow articles and quizzes.

Each store owns one JSON file. Two rules hold for both files:

- Loading is strict: a record with a missing or wrong-typed field raises a
  ValueError naming the file, item number, and field, instead of being
  silently repaired.
- Saving refuses to overwrite edits made outside the app. The store remembers
  the file bytes from its last load/save (`snapshot`); if the file differs at
  save time, the save raises and the user must reload first.

The app keeps the loaded list in memory and passes the whole list back to
`save_articles`. Stores never re-read the file inside a save, because that
would refresh `snapshot` and hide external edits from the in-memory list.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Literal, Optional
from uuid import uuid4

from .parsing import extract_words, parse_quiz, quiz_words, split_lines, split_sentences

ContentMode = Literal["article", "note", "quiz"]
DEFAULT_GROUP = "Ungrouped"


@dataclass
class Article:
    article_id: str
    title: str
    body: str
    mode: ContentMode
    group: str
    sentences: List[str]
    completed_count: int = 0
    practice_sentence: int = 0
    practice_word: int = 0


@dataclass
class Quiz(Article):
    pairs: Optional[List[dict[str, str]]] = None


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


def _string_field(record: dict, key: str) -> str:
    """Optional string field; missing means empty."""
    value = record.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value.strip()


def _count_field(record: dict, key: str) -> int:
    value = record.get(key, 0)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def _check_practice_position(
    segment: object, word: object, segments: List[str], words_of: Callable[[str], List[str]]
) -> None:
    """Saved progress must point at an existing word; (0, 0) means "from the start"."""
    if not isinstance(segment, int) or not isinstance(word, int):
        raise ValueError("practice position must be integers")
    if (segment, word) == (0, 0):
        return
    if not 0 <= segment < len(segments) or not 0 <= word < len(words_of(segments[segment])):
        raise ValueError(f"practice position (segment {segment}, word {word}) is outside the text")


class ArticleStore:
    """Copy-practice records in articles.json."""

    kind = "article"

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _default_storage_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # File bytes as of our last load/save; None means "no file yet".
        self.snapshot: Optional[bytes] = None

    def load_articles(self) -> List[Article]:
        if not self.path.exists():
            self.snapshot = None
            return []
        data = self.path.read_bytes()
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"invalid JSON in {self.kind} data {self.path} "
                f"(line {error.lineno}, column {error.colno})"
            ) from error
        if not isinstance(payload, list):
            raise ValueError(f"{self.kind} data must be a JSON array: {self.path}")

        items: List[Article] = []
        seen_ids = set()
        for number, record in enumerate(payload, 1):
            try:
                if not isinstance(record, dict):
                    raise ValueError("expected object")
                item = self.parse_record(record)
                if item.article_id in seen_ids:
                    raise ValueError(f"duplicate id {item.article_id!r}")
            except ValueError as error:
                raise ValueError(f"invalid {self.kind} in {self.path}, item {number}: {error}") from error
            seen_ids.add(item.article_id)
            items.append(item)
        # Only a fully valid load becomes the baseline for the next save.
        self.snapshot = data
        return items

    def parse_record(self, record: dict) -> Article:
        article_id = record.get("article_id")
        if not isinstance(article_id, str) or not article_id.strip():
            raise ValueError("article_id must be a non-empty string")
        mode = record.get("mode", "article")
        if mode not in ("article", "note"):
            raise ValueError(f"mode must be 'article' or 'note', got {mode!r}")
        title = _string_field(record, "title")
        body = _string_field(record, "body")
        group = _string_field(record, "group") or DEFAULT_GROUP
        if mode == "note" and not title:
            title = self.default_note_title()

        raw_sentences = record.get("sentences")
        if raw_sentences is None:
            sentences = self.build_segments(body, mode)
        elif isinstance(raw_sentences, list) and all(isinstance(s, str) for s in raw_sentences):
            sentences = [s.strip() for s in raw_sentences if s.strip()]
        else:
            raise ValueError("sentences must be an array of strings")

        practice_sentence = record.get("practice_sentence", 0)
        practice_word = record.get("practice_word", 0)
        _check_practice_position(practice_sentence, practice_word, sentences, extract_words)
        return Article(
            article_id=article_id,
            title=title,
            body=body,
            mode=mode,
            group=group,
            sentences=sentences,
            completed_count=_count_field(record, "completed_count"),
            practice_sentence=practice_sentence,
            practice_word=practice_word,
        )

    def to_record(self, article: Article) -> dict:
        return asdict(article)

    def save_articles(self, articles: List[Article]) -> None:
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.snapshot:
            raise ValueError(f"{self.kind} data changed on disk; reload: {self.path}")
        payload = [self.to_record(article) for article in articles]
        # Write to a temp file and rename, so a crash mid-write never leaves
        # a truncated data file behind.
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.path)
            self.snapshot = self.path.read_bytes()
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def upsert_article(
        self,
        articles: List[Article],
        title: str,
        body: str,
        mode: ContentMode = "article",
        group: str = DEFAULT_GROUP,
        article_id: Optional[str] = None,
    ) -> List[Article]:
        if mode not in ("article", "note"):
            raise ValueError(f"unknown article mode: {mode}")
        cleaned_title = title.strip()
        cleaned_body = body.strip()
        if mode == "note" and not cleaned_title:
            cleaned_title = self.default_note_title()

        previous = next((a for a in articles if a.article_id == article_id), None)
        # Progress points into the old segments, so it only survives when the
        # text and split rule are unchanged.
        same_text = previous is not None and previous.body == cleaned_body and previous.mode == mode
        article = Article(
            article_id=article_id or str(uuid4()),
            title=cleaned_title,
            body=cleaned_body,
            mode=mode,
            group=group.strip() or DEFAULT_GROUP,
            sentences=self.build_segments(cleaned_body, mode),
            completed_count=previous.completed_count if previous else 0,
            practice_sentence=previous.practice_sentence if same_text else 0,
            practice_word=previous.practice_word if same_text else 0,
        )
        updated = [article if a.article_id == article.article_id else a for a in articles]
        if previous is None:
            updated.append(article)
        self.save_articles(updated)
        return updated

    def delete_article(self, articles: List[Article], article_id: str) -> List[Article]:
        updated = [article for article in articles if article.article_id != article_id]
        self.save_articles(updated)
        return updated

    def build_segments(self, body: str, mode: str) -> List[str]:
        return split_lines(body) if mode == "note" else split_sentences(body)

    def default_note_title(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class QuizStore(ArticleStore):
    """Chinese/English pairs in quizzes.json; `sentences` holds the English answers."""

    kind = "quiz"

    def parse_record(self, record: dict) -> Article:
        quiz_id = record.get("id")
        title = record.get("title")
        pairs = record.get("pairs")
        if not isinstance(quiz_id, str) or not quiz_id.strip():
            raise ValueError("id must be a non-empty string")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("missing title")
        if not isinstance(pairs, list) or not pairs:
            raise ValueError("pairs must be a non-empty array")
        for number, pair in enumerate(pairs, 1):
            if not isinstance(pair, dict) or not all(isinstance(pair.get(key), str) for key in ("zh", "en")):
                raise ValueError(f"pair {number}: expected zh and en strings")
            if any(mark in pair[key] for key in ("zh", "en") for mark in ("\n", "\r")):
                raise ValueError(f"pair {number}: each field must be one line")
            try:
                parse_quiz(pair["zh"] + "\n" + pair["en"])
            except ValueError as error:
                raise ValueError(f"pair {number}: {error}") from error

        clean_pairs = [{"zh": p["zh"].strip(), "en": p["en"].strip()} for p in pairs]
        answers = [p["en"] for p in clean_pairs]
        practice_index = record.get("practice_index", 0)
        practice_word = record.get("practice_word", 0)
        _check_practice_position(practice_index, practice_word, answers, quiz_words)
        return Quiz(
            article_id=quiz_id,
            title=title.strip(),
            body=self.pairs_body(clean_pairs),
            mode="quiz",
            group=_string_field(record, "group") or DEFAULT_GROUP,
            sentences=answers,
            completed_count=_count_field(record, "completed_count"),
            practice_sentence=practice_index,
            practice_word=practice_word,
            pairs=clean_pairs,
        )

    def to_record(self, article: Article) -> dict:
        assert isinstance(article, Quiz), f"QuizStore cannot save {article!r}"
        return {
            "id": article.article_id,
            "title": article.title,
            "group": article.group,
            "pairs": article.pairs,
            "completed_count": article.completed_count,
            "practice_index": article.practice_sentence,
            "practice_word": article.practice_word,
        }

    def upsert_article(self, articles: List[Article], title: str, body: str,
                       mode: ContentMode = "quiz", group: str = DEFAULT_GROUP,
                       article_id: Optional[str] = None) -> List[Article]:
        pairs = parse_quiz(body)
        previous = next((a for a in articles if a.article_id == article_id), None)
        body = self.pairs_body(pairs)
        same_text = previous is not None and previous.body == body
        quiz = Quiz(
            article_id=article_id or str(uuid4()),
            title=title.strip(),
            body=body,
            mode="quiz",
            group=group.strip() or DEFAULT_GROUP,
            sentences=[p["en"] for p in pairs],
            completed_count=previous.completed_count if previous else 0,
            practice_sentence=previous.practice_sentence if same_text else 0,
            practice_word=previous.practice_word if same_text else 0,
            pairs=pairs,
        )
        updated = [quiz if a.article_id == quiz.article_id else a for a in articles]
        if previous is None:
            updated.append(quiz)
        self.save_articles(updated)
        return updated

    def pairs_body(self, pairs: List[dict[str, str]]) -> str:
        return "\n".join(f"{p['zh']}\n{p['en']}" for p in pairs)
