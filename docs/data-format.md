# Local data format

Wordflow reads a JSON array of records. Close the app before editing the file; use the `config` button to find the current path and keep a backup before replacing it. Restart to load your changes.

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
| `article_id` | A unique, stable string for each record. Use different IDs for different items. |
| `title` | Name shown in the library. Required when saving an article in the app. |
| `body` | The original text. |
| `mode` | `article` for sentence segments, or `note` for the UI's memo mode. |
| `group` | Optional library group; defaults to `Ungrouped`. |
| `completed_count` | Completed runs, displayed as zero to three filled dots. Defaults to zero. |
| `sentences` | Optional array of explicit practice segments. Omit it to derive segments from `body`. |

When `sentences` is supplied, the app uses those segments for practice and article previews. Otherwise, article mode splits at line breaks and whitespace after `.`, `!`, `?`, `;`, or `:`. Memo mode uses non-empty lines. Saving through the editor rebuilds segments from the body, so it can replace custom segmentation.

Practice targets English words, including internal apostrophes and hyphens. Numbers, other scripts, and standalone punctuation are skipped.

To select a different file, set `WORDFLOW_DATA_PATH` before launching. `SPELLLANE_DATA_PATH` remains supported as a legacy environment variable. Without an override, the app prefers `~/.wordflow/articles.json`, uses an existing `~/.spelllane/articles.json` when no new file exists, and may fall back to the current directory if it cannot create the home data folder. The path shown in `config` is authoritative.

Copy the complete JSON file to back it up. Invalid JSON is reported with its file path and location; repair it or restore a backup before restarting. There is no automatic merge or cloud backup.

The [sample records](../examples/articles.json) contain original practice text and can be used with a separate data path as shown in the [README](../README.md#local-data-and-sample-content).
