"""Behavioral tests for the Textual app, driven through a test pilot.

These avoid pytest-asyncio by running each scenario with asyncio.run.
"""

from __future__ import annotations

import asyncio

import pytest

from wordflow.app import LibraryScreen, PracticeScreen, WordflowApp
from wordflow.storage import ArticleStore


@pytest.fixture
def store_path(tmp_path, monkeypatch):
    path = tmp_path / "articles.json"
    monkeypatch.setenv("WORDFLOW_DATA_PATH", str(path))
    monkeypatch.delenv("SPELLLANE_DATA_PATH", raising=False)
    return path


def status_text(screen) -> str:
    return str(screen.query_one("#status").renderable)


def message_text(screen) -> str:
    return str(screen.query_one("#practice-message").renderable)


def run(scenario):
    """Run an async scenario(app, pilot) inside a fresh test app."""

    async def driver():
        app = WordflowApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await scenario(app, pilot)

    asyncio.run(driver())


async def make_article(pilot, app, title, body, mode="article"):
    lib = app.screen
    lib.start_new_item(mode)
    await pilot.pause()
    lib.query_one("#editor-title").value = title
    lib.query_one("#article-body").text = body
    lib.handle_save()
    await pilot.pause()
    return lib


# --- LibraryScreen --------------------------------------------------------


def test_save_creates_article_and_lists_it(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Greeting", "Hello world.")
        assert len(lib.articles) == 1
        assert status_text(lib) == "[saved]"
        assert lib.articles[0].sentences == ["Hello world."]

    run(scenario)


def test_editing_existing_article_can_be_saved(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "A", "Hello world.")
        lib.load_article(lib.articles[0])
        await pilot.pause()
        assert lib.query_one("#action-save").display is True
        assert not lib.editor_is_dirty()

        lib.query_one("#article-body").text = "Changed body now."
        await pilot.pause()
        assert lib.editor_is_dirty()
        assert status_text(lib) == "[edited]"

        lib.handle_save()
        await pilot.pause()
        assert status_text(lib) == "[saved]"
        assert not lib.editor_is_dirty()
        assert ArticleStore(store_path).load_articles()[0].body == "Changed body now."

    run(scenario)


def test_save_requires_body(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        lib.start_new_item("article")
        await pilot.pause()
        lib.query_one("#editor-title").value = "T"
        lib.query_one("#article-body").text = "   "
        await pilot.pause()  # let editor-change events settle as during typing
        lib.handle_save()
        await pilot.pause()
        assert status_text(lib) == "[missing] body"
        assert lib.articles == []

    run(scenario)


def test_save_article_requires_title(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        lib.start_new_item("article")
        await pilot.pause()
        lib.query_one("#editor-title").value = ""
        lib.query_one("#article-body").text = "Body here."
        await pilot.pause()  # let editor-change events settle as during typing
        lib.handle_save()
        await pilot.pause()
        assert status_text(lib) == "[missing] name"
        assert lib.articles == []

    run(scenario)


def test_memo_save_allows_empty_title(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        lib.start_new_item("note")
        await pilot.pause()
        lib.query_one("#editor-title").value = ""
        lib.query_one("#article-body").text = "line one\nline two"
        lib.handle_save()
        await pilot.pause()
        assert len(lib.articles) == 1
        assert lib.articles[0].mode == "note"
        assert lib.articles[0].title  # default timestamp title

    run(scenario)


def test_filter_separates_articles_and_memos(store_path):
    async def scenario(app, pilot):
        await make_article(pilot, app, "Art", "Hello world.", mode="article")
        lib = await make_article(pilot, app, "Memo", "a note", mode="note")

        lib.set_filter("article")
        await pilot.pause()
        assert [a.title for a in lib.filtered_articles()] == ["Art"]

        lib.set_filter("note")
        await pilot.pause()
        assert [a.title for a in lib.filtered_articles()] == ["Memo"]

    run(scenario)


def test_delete_requires_selection(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        lib.handle_delete()
        await pilot.pause()
        assert status_text(lib) == "[missing] select an item"

    run(scenario)


def test_delete_removes_selected_article(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Doomed", "Hello world.")
        lib.selected_article_id = lib.articles[0].article_id
        lib.handle_delete()
        await pilot.pause()
        assert lib.articles == []
        assert status_text(lib) == "[removed] item"

    run(scenario)


# --- Practice launch validation (regression for instant-completion bug) ---


def test_word_less_content_is_rejected_without_awarding_a_star(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Nums", "123. 456!")
        lib.selected_article_id = lib.articles[0].article_id
        lib.handle_start()
        await pilot.pause()
        assert isinstance(app.screen, LibraryScreen)
        assert status_text(lib) == "[invalid] empty"
        assert ArticleStore(store_path).load_articles()[0].completed_count == 0

    run(scenario)


def test_start_requires_selection(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        lib.handle_start()
        await pilot.pause()
        assert status_text(lib) == "[missing] select an item"

    run(scenario)


# --- PracticeScreen -------------------------------------------------------


async def start_practice(pilot, app, body, title="Drill"):
    lib = await make_article(pilot, app, title, body)
    lib.selected_article_id = lib.articles[0].article_id
    lib.handle_start()
    await pilot.pause()
    practice = app.screen
    practice.query_one("#word-input").focus()
    await pilot.pause()
    return lib, practice


def test_typing_correct_word_advances(store_path):
    async def scenario(app, pilot):
        _, practice = await start_practice(pilot, app, "Hi there.")
        assert practice.current_words == ["Hi", "there"]
        await pilot.press("H", "i")
        await pilot.pause()
        assert practice.word_index == 1
        assert message_text(practice) == "[step] word complete"

    run(scenario)


def test_wrong_character_shows_hint_and_reverts(store_path):
    """Regression: hints used to be wiped by the re-entrant Changed event."""

    async def scenario(app, pilot):
        _, practice = await start_practice(pilot, app, "Hi there.")
        await pilot.press("H", "x")
        await pilot.pause()
        assert message_text(practice) == "[hint] next -> i"
        assert practice.query_one("#word-input").value == "H"

    run(scenario)


def test_completing_article_awards_star_and_returns_on_keypress(store_path):
    async def scenario(app, pilot):
        lib, practice = await start_practice(pilot, app, "Hi there.")
        for char in "Hithere":
            await pilot.press(char)
        await pilot.pause()
        assert practice.is_complete
        assert "Good" in message_text(practice)
        assert ArticleStore(store_path).load_articles()[0].completed_count == 1

        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, LibraryScreen)
        # star refresh propagated back to the library view
        assert lib.articles[0].completed_count == 1

    run(scenario)


def test_completed_words_are_locked(store_path):
    async def scenario(app, pilot):
        _, practice = await start_practice(pilot, app, "Hi there.")
        await pilot.press("H", "i")  # complete first word
        await pilot.pause()
        # try to corrupt the locked "Hi " prefix
        practice.query_one("#word-input").value = "Xy"
        await pilot.pause()
        assert message_text(practice) == "[locked] completed words"
        assert practice.word_index == 1

    run(scenario)


def test_case_insensitive_matching(store_path):
    async def scenario(app, pilot):
        _, practice = await start_practice(pilot, app, "Hi there.")
        await pilot.press("h", "i")  # lower-case input for "Hi"
        await pilot.pause()
        assert practice.word_index == 1

    run(scenario)
