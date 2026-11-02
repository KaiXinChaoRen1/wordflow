"""Persistent storage for Wordflow articles."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional
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
        except json.JSONDecodeError as error:
            raise ValueError(
                f"invalid JSON in article data {self.path} "
                f"(line {error.lineno}, column {error.colno})"
            ) from error

        if not isinstance(payload, list):
            raise ValueError(f"article data must be a JSON array: {self.path}")

        articles = []
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise ValueError(
                    f"article data item {index} must be an object: {self.path}"
                )
            mode = self.normalize_mode(str(item.get("mode", "article")))
            article_id = str(item.get("article_id") or uuid4())
            title = str(item.get("title", "")).strip()
            body = str(item.get("body", "")).strip()
            group = str(item.get("group", "")).strip() or DEFAULT_GROUP
            if mode == "note" and not title:
                title = self.default_note_title()

            raw_sentences = item.get("sentences")
            if isinstance(raw_sentences, list):
                sentences = [
                    str(sentence).strip()
                    for sentence in raw_sentences
                    if str(sentence).strip()
                ]
            else:
                sentences = self.build_segments(body, mode)

            completed_count = item.get("completed_count", 0)
            if not isinstance(completed_count, int):
                try:
                    completed_count = int(completed_count)
                except (ValueError, TypeError):
                    completed_count = 0
            completed_count = max(0, completed_count)
            sentence_index = item.get("practice_sentence", 0)
            word_index = item.get("practice_word", 0)
            if not isinstance(sentence_index, int) or not 0 <= sentence_index < len(sentences):
                sentence_index = 0
                word_index = 0
            words = extract_words(sentences[sentence_index]) if sentences else []
            if not isinstance(word_index, int) or not 0 <= word_index < len(words):
                word_index = 0

            articles.append(
                Article(
                    article_id=article_id,
                    title=title,
                    body=body,
                    mode=mode,
                    group=group,
                    sentences=sentences,
                    completed_count=completed_count,
                    practice_sentence=sentence_index,
                    practice_word=word_index,
                )
            )
        return articles

    def save_articles(self, articles: List[Article]) -> None:
        payload = [asdict(article) for article in articles]
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.path)
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
        cleaned_title = title.strip()
        cleaned_body = body.strip()
        cleaned_group = group.strip() or DEFAULT_GROUP
        normalized_mode = self.normalize_mode(mode)
        if normalized_mode == "note" and not cleaned_title:
            cleaned_title = self.default_note_title()
        sentences = self.build_segments(cleaned_body, normalized_mode)

        existing_completed_count = 0
        practice_sentence = 0
        practice_word = 0
        if article_id:
            for article in articles:
                if article.article_id == article_id:
                    existing_completed_count = article.completed_count
                    if article.body == cleaned_body and article.mode == normalized_mode:
                        practice_sentence = article.practice_sentence
                        practice_word = article.practice_word
                    break

        article = Article(
            article_id=article_id or str(uuid4()),
            title=cleaned_title,
            body=cleaned_body,
            mode=normalized_mode,
            group=cleaned_group,
            sentences=sentences,
            completed_count=existing_completed_count,
            practice_sentence=practice_sentence,
            practice_word=practice_word,
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

    def complete_article(self, article_id: str) -> Optional[Article]:
        articles = self.load_articles()
        completed = None
        for article in articles:
            if article.article_id == article_id:
                article.completed_count += 1
                article.practice_sentence = 0
                article.practice_word = 0
                completed = article
                break
        if completed is not None:
            self.save_articles(articles)
        return completed

    def save_practice_progress(self, article_id: str, sentence: int, word: int) -> None:
        articles = self.load_articles()
        for article in articles:
            if article.article_id == article_id:
                article.practice_sentence = sentence
                article.practice_word = word
                self.save_articles(articles)
                return
        raise ValueError(f"article not found: {article_id}")

    def build_segments(self, body: str, mode: ContentMode) -> List[str]:
        normalized_mode = self.normalize_mode(mode)
        if normalized_mode == "note":
            return split_lines(body)
        return split_sentences(body)

    def normalize_mode(self, mode: str) -> ContentMode:
        return "note" if mode == "note" else "article"

    def default_note_title(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class QuizStore(ArticleStore):
    """Store quizzes separately using explicit Chinese/English pairs."""

    def __init__(self, path: Optional[Path] = None) -> None:
        super().__init__(path)
        self.snapshot: Optional[bytes] = None

    def load_articles(self) -> List[Article]:
        if not self.path.exists():
            self.snapshot = None
            return []
        try:
            data = self.path.read_bytes()
            payload = json.loads(data)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON in quiz data {self.path} (line {error.lineno}, column {error.colno})") from error
        if not isinstance(payload, list):
            raise ValueError(f"quiz data must be a JSON array: {self.path}")
        result: List[Article] = []
        ids = set()
        for index, item in enumerate(payload, 1):
            try:
                if not isinstance(item, dict):
                    raise ValueError("expected object")
                quiz_id = item.get("id")
                title = item.get("title")
                pairs = item.get("pairs")
                if not isinstance(quiz_id, str) or not quiz_id.strip() or quiz_id in ids:
                    raise ValueError("id must be a unique non-empty string")
                if not isinstance(title, str) or not title.strip():
                    raise ValueError("missing title")
                if not isinstance(pairs, list) or not pairs:
                    raise ValueError("pairs must be a non-empty array")
                for number, pair in enumerate(pairs, 1):
                    if not isinstance(pair, dict) or not all(isinstance(pair.get(key), str) for key in ("zh", "en")):
                        raise ValueError(f"pair {number}: expected zh and en strings")
                    if '\n' in pair['zh'] or '\n' in pair['en'] or '\r' in pair['zh'] or '\r' in pair['en']:
                        raise ValueError(f"pair {number}: each field must be one line")
                    try:
                        parse_quiz(pair['zh'] + '\n' + pair['en'])
                    except ValueError as error:
                        raise ValueError(f"pair {number}: {error}") from error
                group = item.get("group", DEFAULT_GROUP)
                if not isinstance(group, str):
                    raise ValueError("group must be a string")
                count = item.get("completed_count", 0)
                sentence = item.get("practice_index", 0)
                word = item.get("practice_word", 0)
                if not isinstance(count, int) or count < 0:
                    raise ValueError("invalid completed_count")
                if not isinstance(sentence, int) or not 0 <= sentence < len(pairs):
                    raise ValueError("invalid practice_index")
                if not isinstance(word, int) or not 0 <= word < len(quiz_words(pairs[sentence]['en'])):
                    raise ValueError("invalid practice_word")
                ids.add(quiz_id)
                clean_pairs = [{"zh": p['zh'].strip(), "en": p['en'].strip()} for p in pairs]
                body = '\n'.join(f"{p['zh']}\n{p['en']}" for p in clean_pairs)
                result.append(Quiz(quiz_id, title.strip(), body, "quiz", group.strip() or DEFAULT_GROUP,
                                   [p['en'] for p in clean_pairs], count, sentence, word, clean_pairs))
            except ValueError as error:
                raise ValueError(f"invalid quiz in {self.path}, item {index}: {error}") from error
        self.snapshot = data
        return result

    def save_articles(self, articles: List[Article]) -> None:
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.snapshot:
            raise ValueError(f"quiz data changed on disk; reload: {self.path}")
        payload = [{"id": a.article_id, "title": a.title, "group": a.group,
                    "pairs": a.pairs, "completed_count": a.completed_count,
                    "practice_index": a.practice_sentence, "practice_word": a.practice_word}
                   for a in articles if isinstance(a, Quiz)]
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.path)
            self.snapshot = self.path.read_bytes()
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def upsert_article(self, articles: List[Article], title: str, body: str,
                       mode: ContentMode = "quiz", group: str = DEFAULT_GROUP,
                       article_id: Optional[str] = None) -> List[Article]:
        pairs = parse_quiz(body)
        previous = next((a for a in articles if a.article_id == article_id), None)
        canonical_body = '\n'.join(f"{p['zh']}\n{p['en']}" for p in pairs)
        same = previous is not None and previous.body == canonical_body
        quiz = Quiz(article_id or str(uuid4()), title.strip(), canonical_body, "quiz",
                    group.strip() or DEFAULT_GROUP, [p['en'] for p in pairs],
                    previous.completed_count if previous else 0,
                    previous.practice_sentence if same else 0, previous.practice_word if same else 0, pairs)
        updated = [quiz if a.article_id == quiz.article_id else a for a in articles]
        if previous is None:
            updated.append(quiz)
        self.save_articles(updated)
        return updated
