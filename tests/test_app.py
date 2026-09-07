"""Behavioral tests for the Textual app, driven through a test pilot.

These avoid pytest-asyncio by running each scenario with asyncio.run.
"""

from __future__ import annotations

import asyncio

import pytest

from wordflow.app import ArticleItem, GroupHeader, LibraryScreen, PracticeScreen, WordflowApp
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


async def make_article(pilot, app, title, body, mode="article", group=None):
    lib = app.screen
    lib.start_new_item(mode)
    await pilot.pause()
    lib.query_one("#editor-title").value = title
    if group is not None:
        lib.query_one("#editor-group").value = group
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
        assert lib.articles[0].group == "Ungrouped"
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
        lib.query_one("#editor-group").value = "Work"
        await pilot.pause()
        assert lib.editor_is_dirty()
        assert status_text(lib) == "[edited]"

        lib.handle_save()
        await pilot.pause()
        assert status_text(lib) == "[saved]"
        assert not lib.editor_is_dirty()
        saved = ArticleStore(store_path).load_articles()[0]
        assert saved.body == "Changed body now."
        assert saved.group == "Work"

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
        assert lib.articles[0].group == "Ungrouped"
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


def test_articles_are_grouped_in_the_list(store_path):
    async def scenario(app, pilot):
        await make_article(pilot, app, "One", "Alpha.", group="Book 1")
        await make_article(pilot, app, "Two", "Beta.", group="Book 2")
        lib = await make_article(pilot, app, "Three", "Gamma.", group="Book 1")
        lib.refresh_article_list()
        await pilot.pause()

        rows = []
        for item in lib.query_one("#article-list").query("ListItem"):
            if isinstance(item, GroupHeader):
                rows.append(("group", item.group))
            elif isinstance(item, ArticleItem):
                rows.append(("article", item.article.title))

        assert rows == [
            ("group", "Book 1"),
            ("article", "One"),
            ("article", "Three"),
            ("group", "Book 2"),
            ("article", "Two"),
        ]

    run(scenario)


def test_enter_on_group_header_does_not_start_practice(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "One", "Alpha.", group="Book 1")
        header = next(
            item
            for item in lib.query_one("#article-list").query("ListItem")
            if isinstance(item, GroupHeader)
        )
        lib.handle_select(type("Event", (), {"item": header})())
        await pilot.pause()
        assert isinstance(app.screen, LibraryScreen)

    run(scenario)


def test_group_headers_expand_on_enter(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "One", "Alpha.", group="Book 1")
        lib.expanded_groups.clear()
        lib.selected_article_id = None
        lib.refresh_article_list()
        await pilot.pause()

        rows = list(lib.query_one("#article-list").query("ListItem"))
        assert [type(item).__name__ for item in rows] == ["GroupHeader"]

        lib.handle_select(type("Event", (), {"item": rows[0]})())
        await pilot.pause()

        rows = list(lib.query_one("#article-list").query("ListItem"))
        assert [type(item).__name__ for item in rows] == ["GroupHeader", "ArticleItem"]
        assert lib.query_one("#article-list").index == 0

    run(scenario)


def test_group_header_label_separates_name_and_count(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "One", "Alpha.", group="Book 1")
        header = next(
            item
            for item in lib.query_one("#article-list").query("ListItem")
            if isinstance(item, GroupHeader)
        )

        assert str(header.children[0].renderable) == "- Book 1 · 1"

    run(scenario)


def test_collapsing_selected_group_keeps_editor_preview(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "One", "Alpha.", group="Book 1")
        lib.load_article(lib.articles[0])
        await pilot.pause()

        lib.toggle_group("Book 1")
        await pilot.pause()

        assert lib.selected_article_id == lib.articles[0].article_id
        assert lib.query_one("#article-list").index == 0
        assert lib.query_one("#editor-title").value == "One"
        assert lib.query_one("#editor-group").value == "Book 1"
        assert lib.query_one("#article-body").text == "Alpha."

    run(scenario)


def test_list_labels_treat_user_brackets_as_plain_text(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "One [x]", "Alpha.", group="Book [1]")
        rows = list(lib.query_one("#article-list").query("ListItem"))
        header = next(item for item in rows if isinstance(item, GroupHeader))
        article = next(item for item in rows if isinstance(item, ArticleItem))

        assert str(header.children[0].renderable) == "- Book [1] · 1"
        assert str(article._label.renderable).endswith("One [x]  ○○○")

    run(scenario)


def test_selected_row_shows_marker(store_path):
    async def scenario(app, pilot):
        await make_article(pilot, app, "One", "Alpha.")
        lib = await make_article(pilot, app, "Two", "Beta.")
        lib.load_article(lib.articles[0])
        await pilot.pause()

        markers = {}
        for item in lib.query_one("#article-list").query("ListItem"):
            if isinstance(item, ArticleItem):
                markers[item.article.title] = str(item._label.renderable)
        assert markers["One"].startswith("> ")
        assert markers["Two"].startswith("  ")

    run(scenario)


def test_article_row_shows_title_and_stars_on_one_line(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "One", "Alpha.")
        item = next(
            item
            for item in lib.query_one("#article-list").query("ListItem")
            if isinstance(item, ArticleItem)
        )

        label = str(item._label.renderable)
        assert "\n" not in label
        assert label.endswith("One  ○○○")

    run(scenario)


def test_delete_requires_selection(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        lib.handle_delete()
        await pilot.pause()
        assert status_text(lib) == "[missing] select an item"

    run(scenario)


def test_delete_needs_two_presses(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Doomed", "Hello world.")
        lib.selected_article_id = lib.articles[0].article_id

        lib.handle_delete()  # first press only arms
        await pilot.pause()
        assert len(lib.articles) == 1
        assert status_text(lib) == "[confirm] press Del again"

        lib.handle_delete()  # second press deletes
        await pilot.pause()
        assert lib.articles == []
        assert status_text(lib) == "[removed] item"

    run(scenario)


def test_delete_confirmation_resets_when_selection_changes(store_path):
    async def scenario(app, pilot):
        await make_article(pilot, app, "Keep", "Alpha beta.")
        lib = await make_article(pilot, app, "Other", "Gamma delta.")

        lib.selected_article_id = lib.articles[0].article_id
        lib.handle_delete()  # arm deletion of first
        await pilot.pause()
        assert status_text(lib) == "[confirm] press Del again"

        # switching to another article disarms the pending delete
        lib.load_article(lib.articles[1])
        await pilot.pause()
        assert lib.pending_delete_id is None

        lib.handle_delete()  # only re-arms, does not delete
        await pilot.pause()
        assert len(lib.articles) == 2

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


def test_arrow_keys_preview_and_enter_starts_practice(store_path):
    async def scenario(app, pilot):
        await make_article(pilot, app, "One", "Alpha beta.")
        lib = await make_article(pilot, app, "Two", "Gamma delta.")

        # After saving, "Two" is the highlighted row; move up to "One".
        list_view = lib.query_one("#article-list")
        list_view.focus()
        await pilot.pause()

        await pilot.press("up")
        await pilot.pause()
        assert lib.query_one("#editor-title").value == "One"  # previewed, not practiced
        assert isinstance(app.screen, LibraryScreen)

        await pilot.press("down")
        await pilot.pause()
        assert lib.query_one("#editor-title").value == "Two"

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PracticeScreen)

    run(scenario)


def test_keyboard_shortcuts_new_and_save(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert lib.is_creating_new

        lib.query_one("#editor-title").value = "KB"
        lib.query_one("#article-body").text = "Hello world."
        # ctrl+s reaches the screen even while the body editor is focused
        lib.query_one("#article-body").focus()
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert len(lib.articles) == 1
        assert status_text(lib) == "[saved]"

    run(scenario)


def test_ctrl_d_deletes_from_list(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Doomed", "Hello world.")
        lib.selected_article_id = lib.articles[0].article_id
        lib.query_one("#article-list").focus()
        await pilot.pause()
        await pilot.press("ctrl+d")  # arm
        await pilot.press("ctrl+d")  # confirm
        await pilot.pause()
        assert lib.articles == []

    run(scenario)


def test_ctrl_r_starts_practice(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Drill", "Hello world.")
        lib.selected_article_id = lib.articles[0].article_id
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert isinstance(app.screen, PracticeScreen)

    run(scenario)


def test_ctrl_t_toggles_mode_filter(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        assert lib.current_filter == "article"
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert lib.current_filter == "note"
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert lib.current_filter == "article"

    run(scenario)


def test_arming_delete_marks_the_row(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Doomed", "Hello world.")
        lib.selected_article_id = lib.articles[0].article_id
        lib.handle_delete()  # arm
        await pilot.pause()
        item = next(
            item
            for item in lib.query_one("#article-list").query("ListItem")
            if isinstance(item, ArticleItem)
        )
        assert str(item._label.renderable).startswith("!   ")

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


def test_completing_article_awards_star_and_returns_on_any_key(store_path):
    async def scenario(app, pilot):
        lib, practice = await start_practice(pilot, app, "Hi there.")
        for char in "Hithere":
            await pilot.press(char)
        await pilot.pause()
        assert practice.is_complete
        assert "Good" in message_text(practice)
        assert "any key back" in message_text(practice)
        assert ArticleStore(store_path).load_articles()[0].completed_count == 1

        # The next key returns to the quiet main view.
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, LibraryScreen)
        # star refresh propagated back to the library view
        assert lib.articles[0].completed_count == 1

    run(scenario)


def test_repeat_practice_with_r_key(store_path):
    async def scenario(app, pilot):
        _, practice = await start_practice(pilot, app, "Hi there.")
        for char in "Hithere":
            await pilot.press(char)
        await pilot.pause()
        assert practice.is_complete
        assert ArticleStore(store_path).load_articles()[0].completed_count == 1

        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, PracticeScreen)
        assert not practice.is_complete
        assert practice.sentence_index == 0 and practice.word_index == 0
        assert practice.query_one("#word-input").disabled is False

        for char in "Hithere":
            await pilot.press(char)
        await pilot.pause()
        assert ArticleStore(store_path).load_articles()[0].completed_count == 2

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


def test_long_title_can_scroll_horizontally(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Long title " * 12, "Alpha.")
        view = lib.query_one("#article-list")
        assert view.show_horizontal_scrollbar
        assert view.max_scroll_x > 0
        view.scroll_to(x=view.max_scroll_x, animate=False, immediate=True)
        await pilot.pause()
        assert view.scroll_x > 0

    run(scenario)


def test_preview_sentence_breaks_and_completion(store_path):
    async def scenario(app, pilot):
        original = "First sentence. Second sentence!"
        lib = await make_article(pilot, app, "One", original)
        lib.store.complete_article(lib.articles[0].article_id)
        lib.refresh_articles_from_store()
        await pilot.pause()
        assert str(lib.query_one("#editor-completion").renderable) == "●○○"
        assert lib.query_one("#article-body").text == "First sentence.\nSecond sentence!"
        assert lib.query_one("#article-body").soft_wrap
        assert not lib.editor_is_dirty()
        lib.query_one("#editor-title").value = "Renamed"
        lib.handle_save()
        await pilot.pause()
        assert lib.store.load_articles()[0].body == original
        lib.start_new_item("article")
        await pilot.pause()
        assert str(lib.query_one("#editor-completion").renderable) == ""

    run(scenario)


@pytest.mark.parametrize("values", [("H", "He", "Hel"), ("H", "Hx", "He", "H", "He", "Hel")])
def test_burst_input_does_not_replay_programmatic_changes(store_path, monkeypatch, values):
    async def scenario(app, pilot):
        _, practice = await start_practice(pilot, app, "Hello world.")
        sync = practice.sync_input_value
        sync_calls = 0

        def counted_sync():
            nonlocal sync_calls
            sync_calls += 1
            if sync_calls > 20:
                raise RuntimeError("Input.Changed feedback loop")
            sync()

        monkeypatch.setattr(practice, "sync_input_value", counted_sync)
        widget = practice.query_one("#word-input")
        for value in values:
            widget.value = value
        await pilot.pause()
        assert widget.value == "Hel"
        assert practice.current_prefix == "Hel"
        await pilot.press("l", "o")
        assert practice.word_index == 1

    run(scenario)


def test_typing_refreshes_only_current_sentence(store_path, monkeypatch):
    async def scenario(app, pilot):
        _, practice = await start_practice(pilot, app, "Hi there. Next sentence.")
        untouched = practice.query_one("#sentence-1")
        updates = []
        scrolls = []
        original_update = untouched.update

        def record_update(value):
            updates.append(value)
            original_update(value)

        monkeypatch.setattr(untouched, "update", record_update)
        monkeypatch.setattr(practice, "center_current_sentence", scrolls.append)
        await pilot.press("H", "backspace", "H", "i")
        assert not updates
        assert not scrolls
        await pilot.press(*"there")
        await pilot.pause()
        assert practice.sentence_index == 1
        assert untouched.has_class("article-sentence--active")
        assert not practice.query_one("#sentence-0").has_class("article-sentence--active")
        assert scrolls == [untouched]

    run(scenario)
