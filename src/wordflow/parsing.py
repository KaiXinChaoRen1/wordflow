"""Parsing helpers for articles, notes, sentences, and words."""

from __future__ import annotations

import re
from typing import List

SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?;:])\s+|\n+")
WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
QUIZ_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")


def quiz_words(text: str) -> List[str]:
    return QUIZ_WORD_RE.findall(text)


def parse_quiz(text: str) -> List[dict[str, str]]:
    lines = [(number, line.strip()) for number, line in enumerate(text.splitlines(), 1) if line.strip()]
    if not lines:
        raise ValueError("empty quiz")
    if len(lines) % 2:
        raise ValueError(f"line {lines[-1][0]}: missing English")
    pairs = []
    for (zh_line, zh), (en_line, en) in zip(lines[::2], lines[1::2]):
        if not re.search(r"[\u3400-\u9fff]", zh):
            raise ValueError(f"line {zh_line}: expected Chinese")
        if re.search(r"[\u3400-\u9fff]", en) or not re.search(r"[A-Za-z]", en):
            raise ValueError(f"line {en_line}: expected English")
        pairs.append({"zh": zh, "en": en})
    return pairs


def split_sentences(text: str) -> List[str]:
    """Split raw article text into readable sentences."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    parts = SENTENCE_BREAK_RE.split(normalized)
    return [
        re.sub(r"[^\S\n]+", " ", part).strip()
        for part in parts
        if part.strip()
    ]


def split_lines(text: str) -> List[str]:
    """Split note text into one item per non-empty line."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def extract_words(sentence: str) -> List[str]:
    """Extract words while keeping apostrophes and hyphens."""
    return WORD_RE.findall(sentence)
