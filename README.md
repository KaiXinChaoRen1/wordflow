# Wordflow

Wordflow is a terminal-first English spelling trainer built with Python and Textual.

It looks like a dense reading tool from a distance, but underneath it is a focused typing workflow for practicing real article sentences one word at a time.

If you want to practice spelling in public without opening an obviously playful app, Wordflow is built for exactly that.

## Why Wordflow

- Looks like work: low-saturation terminal UI, compact layout, continuous article view
- Trains real text: practice with your own English articles instead of isolated word lists
- Stays in flow: type letters only, spaces are handled for you
- Gives instant feedback: completed words turn green, current sentence stays in view
- Fast to launch: built for keyboard-heavy use inside a terminal

## How It Works

1. Paste or write an English article
2. Wordflow splits it into readable sentences
3. Start a practice session
4. Type letters for the current word
5. When a word is fully matched, Wordflow advances automatically

During practice:

- The full article is shown in one scrollable reading window
- The active sentence is highlighted with a subtle background
- The current sentence stays near the center as you move forward
- Completed words are marked in green
- You never need to manually manage spaces between words

## Demo Feel

Wordflow is optimized for a very specific vibe:

- focused
- understated
- office-safe
- keyboard-first

It is intentionally not flashy. The UI is supposed to blend in as a serious terminal tool while still being pleasant to use for long sessions.

## Install

```bash
cd /Users/lwq/workspace/spelllane
python3 -m pip install --user .
wordflow
```

If `~/.local/bin` is already in your `PATH`, you can launch it anywhere with:

```bash
wordflow
```

If not, check:

```bash
echo $PATH
which wordflow
```

## Fastest Local Run

For this machine, the shortest launch command is:

```bash
wf
```

That command points directly at the local source tree, so after code changes you can just restart `wf` and immediately see the latest version.

You can also run:

```bash
cd /Users/lwq/workspace/spelllane
./run-dev.sh
```

## Development Setup

If you want the installed `wordflow` command to reflect local source changes too, use editable install:

```bash
cd /Users/lwq/workspace/spelllane
python3 -m pip install --user -e .
wordflow
```

## Controls

- `ctrl+n`: new article
- `ctrl+s`: save article
- `ctrl+r`: start practice
- `ctrl+d`: delete article
- `esc`: leave the practice screen

## Storage

Wordflow stores article data at:

```bash
~/.wordflow/articles.json
```

Compatibility behavior:

- If an older `~/.spelllane/articles.json` exists, Wordflow can still read it
- If the user home directory is not writable, Wordflow falls back to:

```bash
.wordflow/articles.json
```

## Tech

- Python
- Textual

## Why Star This

- It is a clean example of a focused Textual app with a strong UI constraint
- It solves a weirdly real problem: practicing English spelling without opening an obviously distracting app
- It is small enough to read quickly, but opinionated enough to feel distinct

If you like terminal apps, typing tools, or compact Python products with a clear point of view, this repo is worth a star.
