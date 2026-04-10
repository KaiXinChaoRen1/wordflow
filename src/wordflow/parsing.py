"""Parsing helpers for articles, notes, sentences, and words."""

from __future__ import annotations

import re
from typing import List

SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?;:])\s+|\n+")
WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")


def split_sentences(text: str) -> List[str]:
    """Split raw article text into readable sentences."""
    normalized = re.sub(r"\s+", " ", text.replace("\r", " ")).strip()
    if not normalized:
        return []

    parts = SENTENCE_BREAK_RE.split(normalized)
    return [part.strip() for part in parts if part.strip()]


def split_lines(text: str) -> List[str]:
    """Split note text into one item per non-empty line."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def extract_words(sentence: str) -> List[str]:
    """Extract words while keeping apostrophes and hyphens."""
    return WORD_RE.findall(sentence)
