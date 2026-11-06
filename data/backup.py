"""Copy ~/.wordflow data into this folder, leaving out New Concept original texts.

Run from the repo root:  python3 data/backup.py

The repo is public. New Concept original lessons are copyrighted, so they stay
local only. They are recognized by group name: "New Concept 2", "New Concept 3",
... with no " · " suffix. Companion groups such as "New Concept 2 · Modern" are
original writing and are kept.

To restore, copy the files back into ~/.wordflow (this overwrites them, and the
backup has no New Concept originals).
"""

import json
from pathlib import Path

SOURCE = Path.home() / ".wordflow"
TARGET = Path(__file__).resolve().parent


def is_new_concept_original(item: dict) -> bool:
    group = item.get("group", "")
    return group.startswith("New Concept") and " · " not in group


def backup(name: str) -> None:
    items = json.loads((SOURCE / name).read_text(encoding="utf-8"))
    kept = [item for item in items if not is_new_concept_original(item)]
    (TARGET / name).write_text(
        json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{name}: kept {len(kept)}, skipped {len(items) - len(kept)} New Concept originals")


if __name__ == "__main__":
    backup("articles.json")
    backup("quizzes.json")
