# Agent Notes

This project is a small terminal spelling trainer for personal use. Keep it simple, quiet, and easy to change.

## Product Direction

- Optimize for daily use by the maintainer, not for a polished public SaaS-style product.
- The spelling practice flow matters most. Preserve the core behavior unless the user explicitly asks to change it.
- Prefer predictable behavior over covering every edge case.
- When practice is complete, show a short success state such as `Good`, then let any key return to the main view.
- Completion stars should refresh immediately after practice finishes.

## Code Style

- Keep code small and direct. If 20 lines can cover 80% of the need, prefer that over 200 lines of edge-case machinery.
- Remove dead layers instead of adding new layers around them.
- Avoid duplicated UI state logic. One concept should have one owner.
- Prefer simple functions and local, readable state over abstractions that only hide a few lines.
- Do not add broad refactors unless they clearly make bugs easier to fix or features easier to extend.
- When editing existing code, follow the current Textual/Python structure rather than introducing a new framework or architecture.

## UI Direction

- The UI should feel like a modest terminal tool used at work: quiet, low-contrast, text-first, and slightly utilitarian.
- Avoid a “premium desktop app” look. No flashy panels, decorative gradients, or complex visual states.
- Show only information that helps the current task. Do not show mode labels, line counts, sentence counts, or other metadata unless it is actively useful.
- Keep state styling simple. Prefer text changes such as `>`, brighter text, or bold over multiple background colors.
- Avoid stacking hover, focus, selected, and active backgrounds. If a whole panel needs a background, the container should own it and child rows should stay transparent.
- Empty space and populated rows in the same panel should share the same background.
- Use restrained colors. The interface should look like work, not entertainment.

## Interaction Defaults

- Favor keyboard-friendly behavior, but do not make mouse support visually dominate the interface.
- After actions that change stored data, refresh the in-memory view immediately instead of relying on screen switches.
- Keep status messages short: examples include `[saved]`, `[missing] body`, `[invalid] empty`.
- When adding a feature, ask whether the UI text is necessary. If it is not necessary, omit it.

## Verification

- Run `pytest -q` after behavior changes.
- Run `PYTHONPATH=src python3 -m compileall -q src tests` after Python edits.
- For Textual UI changes, add or run a small `run_test` smoke when practical, especially for navigation, completion, or dynamic labels.
