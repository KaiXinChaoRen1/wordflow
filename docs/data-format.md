# Local data format

Wordflow reads a JSON array of records. Use the `config` button to find the current path and keep a backup before replacing it. After editing the file, press `reload` in the library (or restart). If the file changed on disk since the app last loaded it, saving is refused with `changed on disk; reload` instead of overwriting your edits.

```json
[
  {
    "article_id": "my-first-passage",
    "title": "Small steps",
    "body": "Write one sentence at a time. Small steps make practice easier.",
    "mode": "article",
    "group": "Daily practice",
    "completed_count": 0
  }
]
```

| Field | Meaning |
| --- | --- |
| `article_id` | Required. A unique, stable string for each record. |
| `title` | Name shown in the library. Required when saving an article in the app. |
| `body` | The original text. |
| `mode` | `article` (split by sentence, the default) or `note` (split by line). Other values are rejected. |
| `group` | Optional library group; defaults to `Ungrouped`. |
| `completed_count` | Non-negative integer of completed runs; three dots plus a count above three. Defaults to zero. |
| `sentences` | Optional array of explicit practice segments. Omit it to derive segments from `body`. |
| `practice_sentence`, `practice_word` | Optional saved position (segment and word index) of an unfinished run. Must point at an existing word; `0, 0` means start. |

When `sentences` is supplied, the app uses those segments for practice and article previews. Otherwise, article mode splits at line breaks and whitespace after `.`, `!`, `?`, `;`, or `:`. Memo mode uses non-empty lines. Saving through the editor rebuilds segments from the body, so it can replace custom segmentation.

Practice targets English words, including internal apostrophes and hyphens. Numbers, other scripts, and standalone punctuation are skipped.

To select a different file, set `WORDFLOW_DATA_PATH` before launching. `SPELLLANE_DATA_PATH` remains supported as a legacy environment variable. Without an override, the app prefers `~/.wordflow/articles.json`, uses an existing `~/.spelllane/articles.json` when no new file exists, and may fall back to the current directory if it cannot create the home data folder. The path shown in `config` is authoritative.

Loading is strict: a wrong type or out-of-range value is reported with the file, item number, and field, and is not repaired automatically. Copy the complete JSON file to back it up. Invalid JSON is reported with its file path and location; repair it or restore a backup before restarting. There is no automatic merge or cloud backup.

The [sample records](../examples/articles.json) contain original practice text and can be used with a separate data path as shown in the [README](../README.md#local-data-and-sample-content).
