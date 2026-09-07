# Contributing to Wordflow

Wordflow is a small terminal tool for English typing and spelling practice. Keep the practice flow predictable, the interface quiet, and changes easy to understand.

Issues and pull requests in English or Chinese are welcome. Helpful contributions include reproducible bug reports, clearer setup instructions, terminal compatibility fixes, and focused improvements to daily practice. Discuss larger features in an issue before building them.

## Report a problem

Include your operating system, terminal app, Python version, the steps to reproduce, and what you expected to happen. For input or sentence-splitting bugs, a short invented passage and the exact keystrokes are especially helpful. Remove private information from screenshots and sample text.

## Work on the code

Follow the virtual environment setup in the [README](README.md#get-started), then install development dependencies:

```bash
python -m pip install -e ".[dev]"
pytest -q
PYTHONPATH=src python3 -m compileall -q src tests
```

On Windows, use `.\.venv\Scripts\python.exe` for Python commands, run tests with `-m pytest -q`, and compile with `-m compileall -q src tests`.

For behavior changes, add a regression test that demonstrates the problem. The UI tests use Textual's `run_test()` without needing an interactive terminal. Follow [AGENTS.md](AGENTS.md) for project conventions.

Use clear, imperative commit subjects, optionally with a scope, for example:

- `fix(practice): prevent queued input events from looping`
- `docs: clarify the first practice session`

In a pull request, explain the problem, the resulting behavior, and the checks you ran. Keep unrelated refactors out of the change. Contributions are made under the project's [MIT license](LICENSE).
