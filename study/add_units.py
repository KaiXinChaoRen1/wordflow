"""Add New Concept 2 companion units (modern article + quiz prep + quiz) to Wordflow data.

One unit = two original lessons. For each unit this writes:
  - Copy tab, group "New Concept 2 · Modern":    the article followed by quiz pairs
  - Quiz tab, group "New Concept 2 · Modern":    the quiz pairs
Both share the title "Lessons N–M · <title>".

Usage:
  python3 study/add_units.py <content.json>           # check only, writes nothing
  python3 study/add_units.py <content.json> --write   # back up, then write

Content file format: see study/STUDY_GUIDE.md (example: study/content/nce2-01-10.json).
Close the Wordflow app before --write.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# WORDFLOW_STUDY_DATA lets you rehearse against a copy of the data folder.
DATA = Path(os.environ.get("WORDFLOW_STUDY_DATA", Path.home() / ".wordflow")).expanduser()
REPO_SRC = Path(__file__).resolve().parent.parent / "src"  # this repo's Wordflow storage/validation code
sys.path.insert(0, str(REPO_SRC))
from wordflow.parsing import extract_words  # noqa: E402
from wordflow.storage import ArticleStore, QuizStore  # noqa: E402

ORIGINAL_GROUP = "New Concept 2"
MODERN_GROUP = "New Concept 2 · Modern"
CJK = re.compile(r"[㐀-鿿]")
CONTRACTION = re.compile(r"[A-Za-z](n't|'m|'re|'ve|'ll|'d)\b|\b(it|that|there|what|he|she|who|let)'s\b", re.IGNORECASE)


def fail(message: str) -> None:
    sys.exit(f"[stop] {message}")


def check_unit(unit: dict, originals: dict) -> tuple:
    """Validate one unit against the authoring rules; return (first, second, title)."""
    first, second = unit.get("lessons", [None, None])
    if not (isinstance(first, int) and second == first + 1 and first % 2 == 1):
        fail(f"lessons must be an odd/even pair like [11, 12], got {unit.get('lessons')}")
    label = f"Lessons {first}–{second}"
    title, article, quiz = unit.get("title"), unit.get("article"), unit.get("quiz")
    if not isinstance(title, str) or not title.strip():
        fail(f"{label}: missing title")
    for n in (first, second):
        if n not in originals:
            fail(f"{label}: original Lesson {n} not found in group {ORIGINAL_GROUP!r}")

    if not isinstance(article, str) or not article.strip():
        fail(f"{label}: missing article")
    bad = sorted({ch for ch in article if ord(ch) > 127})
    if bad:
        fail(f"{label}: article must be plain ASCII (straight quotes, no accents); found {bad}")
    if re.search(r"\d", article):
        fail(f"{label}: write numbers as words in the article (digits are skipped in practice)")
    if re.search(r"\b(Mr|Mrs|Ms|Dr|St)\.", article):
        fail(f"{label}: avoid 'Mr.'-style abbreviations (the period splits the sentence)")

    if not isinstance(quiz, list) or not 6 <= len(quiz) <= 9:
        fail(f"{label}: quiz needs 6-9 [zh, en] pairs")
    for number, pair in enumerate(quiz, 1):
        if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(s, str) and s.strip() for s in pair)):
            fail(f"{label}: quiz pair {number} must be [zh, en]")
        zh, en = pair
        if not CJK.search(zh) or re.search(r"[A-Za-z]", zh):
            fail(f"{label}: quiz pair {number} zh must be Chinese only (no Latin letters): {zh}")
        if CJK.search(en) or any(ord(ch) > 127 for ch in en) or re.search(r"\d", en):
            fail(f"{label}: quiz pair {number} en must be ASCII without digits: {en}")
        if CONTRACTION.search(en):
            fail(f"{label}: quiz pair {number} en must not use contractions: {en}")
        if "\n" in zh or "\n" in en:
            fail(f"{label}: quiz pair {number} must be single lines")

    words = len(extract_words(article))
    target = sum(len(extract_words(originals[n].body)) for n in (first, second))
    note = "" if 0.8 * target <= words <= 1.25 * target else "  <-- outside 80%-125% of originals"
    print(f"{label} · {title}: {words} words (originals {target}){note}, {len(quiz)} quiz pairs")
    return first, second, title.strip()


def main() -> None:
    if len(sys.argv) < 2:
        fail("usage: add_units.py <content.json> [--write]")
    write = "--write" in sys.argv
    content = json.loads(Path(sys.argv[1]).expanduser().read_text(encoding="utf-8"))
    units = content.get("units")
    if not isinstance(units, list) or not units:
        fail("content file needs a non-empty 'units' array")

    articles = ArticleStore(DATA / "articles.json")
    quizzes = QuizStore(DATA / "quizzes.json")
    article_items = articles.load_articles()
    quiz_items = quizzes.load_articles()
    originals = {}
    for item in article_items:
        match = re.match(r"Lesson (\d+) ", item.title)
        if item.group == ORIGINAL_GROUP and match:
            originals[int(match.group(1))] = item

    plans = []
    for unit in units:
        first, second, title = check_unit(unit, originals)
        plans.append((f"nce2-lessons-{first}-{second}", f"Lessons {first}–{second} · {title}", unit))
    for unit_id, full_title, _ in plans:
        if any(q.article_id == unit_id for q in quiz_items):
            fail(f"{full_title} already exists (quiz id {unit_id}); delete it first to regenerate")

    if not write:
        print("check passed; nothing written (add --write to save)")
        return
    # Match the app's launch commands (bin/wordflow, python -m wordflow), not
    # this script, whose own arguments usually contain "~/.wordflow".
    if subprocess.run(["pgrep", "-f", "(bin/wordflow|-m wordflow)( |$)"], capture_output=True).returncode == 0:
        fail("Wordflow seems to be running; close it first")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (DATA / "backup").mkdir(exist_ok=True)
    for name in ("articles.json", "quizzes.json"):
        shutil.copy2(DATA / name, DATA / "backup" / f"{name.split('.')[0]}-{stamp}.json")

    for unit_id, full_title, unit in plans:
        pairs_body = "\n".join(f"{zh.strip()}\n{en.strip()}" for zh, en in unit["quiz"])
        prep = "\n\n".join(f"{zh.strip()} {en.strip()}" for zh, en in unit["quiz"])
        body = f"{unit['article'].strip()}\n\n{prep}"
        article_items = articles.upsert_article(article_items, full_title, body, "article",
                                                MODERN_GROUP, f"{unit_id}-modern")
        quiz_items = quizzes.upsert_article(quiz_items, full_title, pairs_body, "quiz", MODERN_GROUP, unit_id)

    # Reload proves both files are still valid for the app.
    ArticleStore(articles.path).load_articles()
    QuizStore(quizzes.path).load_articles()
    print(f"written {len(plans)} units; backup stamp {stamp}")


main()
