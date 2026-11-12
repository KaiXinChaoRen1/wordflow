"""Back up all Wordflow data. Run: python3 data/backup.py

To restore, close Wordflow and copy the JSON files into ~/.wordflow/.
"""

from pathlib import Path
import shutil

SOURCE = Path.home() / ".wordflow"
TARGET = Path(__file__).resolve().parent

if __name__ == "__main__":
    for name in ("articles.json", "quizzes.json"):
        shutil.copy2(SOURCE / name, TARGET / name)
        print(f"Backed up {name}")
