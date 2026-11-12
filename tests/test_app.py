"""Behavioral tests for the Textual app, driven through a test pilot.

These avoid pytest-asyncio by running each scenario with asyncio.run.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from textual.events import Key

from wordflow.app import ArticleItem, GroupHeader, LibraryScreen, PracticeScreen, QuizPracticeScreen, WordflowApp
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
        assert len(lib.items["article"]) == 1
        assert status_text(lib) == "[saved]"
        assert lib.items["article"][0].group == "Ungrouped"
        assert lib.items["article"][0].sentences == ["Hello world."]

    run(scenario)


def test_library_and_editor_are_separate_views(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        assert lib.query_one("#library-sidebar").display
        assert not lib.query_one("#editor-card").display
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert not lib.query_one("#library-sidebar").display
        assert lib.query_one("#editor-card").display
        lib.query_one("#editor-title").value = "One"
        lib.query_one("#article-body").text = "Hello."
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert lib.query_one("#library-sidebar").display
        assert not lib.query_one("#editor-card").display
        await pilot.press("ctrl+e")
        await pilot.pause()
        assert lib.query_one("#editor-card").display
        await pilot.press("escape")
        await pilot.pause()
        assert lib.query_one("#library-sidebar").display

    run(scenario)


def test_editing_existing_article_can_be_saved(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "A", "Hello world.")
        lib.load_article(lib.items["article"][0])
        await pilot.press("ctrl+e")
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
        assert lib.items["article"] == []

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
        assert lib.items["article"] == []

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
        assert len(lib.items["article"]) == 1
        assert lib.items["article"][0].mode == "note"
        assert lib.items["article"][0].group == "Ungrouped"
        assert lib.items["article"][0].title  # default timestamp title

    run(scenario)


def test_copy_list_includes_articles_and_memos(store_path):
    async def scenario(app, pilot):
        await make_article(pilot, app, "Art", "Hello world.", mode="article")
        lib = await make_article(pilot, app, "Memo", "a note", mode="note")

        lib.set_filter("article")
        await pilot.pause()
        assert [a.title for a in lib.filtered_articles()] == ["Art", "Memo"]

        lib.set_filter("quiz")
        await pilot.pause()
        assert lib.filtered_articles() == []

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
        lib.load_article(lib.items["article"][0])
        await pilot.pause()

        lib.toggle_group("Book 1")
        await pilot.pause()

        assert lib.selected_article_id == lib.items["article"][0].article_id
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
        assert str(article._label.renderable).endswith("One [x]  ")

    run(scenario)


def test_selected_row_shows_marker(store_path):
    async def scenario(app, pilot):
        await make_article(pilot, app, "One", "Alpha.")
        lib = await make_article(pilot, app, "Two", "Beta.")
        lib.load_article(lib.items["article"][0])
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
        assert label.endswith("One  ")

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
        lib.selected_article_id = lib.items["article"][0].article_id

        lib.handle_delete()  # first press only arms
        await pilot.pause()
        assert len(lib.items["article"]) == 1
        assert status_text(lib) == "[confirm] press Del again"

        lib.handle_delete()  # second press deletes
        await pilot.pause()
        assert lib.items["article"] == []
        assert status_text(lib) == "[removed] item"

    run(scenario)


def test_delete_confirmation_resets_when_selection_changes(store_path):
    async def scenario(app, pilot):
        await make_article(pilot, app, "Keep", "Alpha beta.")
        lib = await make_article(pilot, app, "Other", "Gamma delta.")

        lib.selected_article_id = lib.items["article"][0].article_id
        lib.handle_delete()  # arm deletion of first
        await pilot.pause()
        assert status_text(lib) == "[confirm] press Del again"

        # switching to another article disarms the pending delete
        lib.load_article(lib.items["article"][1])
        await pilot.pause()
        assert lib.pending_delete_id is None

        lib.handle_delete()  # only re-arms, does not delete
        await pilot.pause()
        assert len(lib.items["article"]) == 2

    run(scenario)


# --- Practice launch validation (regression for instant-completion bug) ---


def test_word_less_content_is_rejected_without_awarding_a_star(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Nums", "123. 456!")
        lib.selected_article_id = lib.items["article"][0].article_id
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
        await pilot.press("ctrl+l")
        await pilot.pause()
        assert app.focused is list_view

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
        assert len(lib.items["article"]) == 1
        assert status_text(lib) == "[saved]"

    run(scenario)


def test_new_copy_defaults_to_sentence_and_can_use_lines(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        await pilot.click("#action-new")
        await pilot.pause()
        assert lib.current_mode == "article"
        await pilot.click("#split-line")
        await pilot.pause()
        lib.query_one("#article-body").text = "A memo"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert lib.items["article"][0].mode == "note"

        await pilot.press("ctrl+n")
        await pilot.pause()
        assert lib.is_creating_new
        assert lib.current_mode == "article"

    run(scenario)


def test_copy_split_change_preserves_body_and_updates_practice(store_path):
    async def scenario(app, pilot):
        body = "Alpha. Beta.\nGamma!"
        lib = await make_article(pilot, app, "Lines", body, mode="note")
        assert lib.current_filter == "article"
        assert lib.items["article"][0].sentences == ["Alpha. Beta.", "Gamma!"]
        lib.handle_start()
        await pilot.pause()
        assert app.screen.article.mode == "note"
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("ctrl+e")
        await pilot.pause()
        await pilot.click("#split-sentence")
        await pilot.pause()
        assert lib.editor_is_dirty()
        await pilot.press("escape")
        await pilot.pause()
        assert lib.editing
        assert status_text(lib) == "[unsaved] save or discard"
        await pilot.press("ctrl+s")
        await pilot.pause()
        stored = ArticleStore(store_path).load_articles()[0]
        assert stored.mode == "article"
        assert stored.body == body
        assert stored.sentences == ["Alpha.", "Beta.", "Gamma!"]
        lib.handle_start()
        await pilot.pause()
        assert app.screen.article.sentences == ["Alpha.", "Beta.", "Gamma!"]

    run(scenario)


def test_quiz_input_practice_resume_and_completion(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        await pilot.click("#filter-quiz")
        await pilot.click("#action-new")
        lib.query_one("#editor-title").value = "Daily"
        lib.query_one("#article-body").text = "你好\nHi there.\n\n我赢了\nI win."
        await pilot.press("ctrl+s")
        await pilot.pause()
        data = json.loads(store_path.with_name("quizzes.json").read_text())
        assert data[0]["pairs"] == [{"zh": "你好", "en": "Hi there."}, {"zh": "我赢了", "en": "I win."}]
        assert not store_path.exists()
        lib.handle_start()
        await pilot.pause()
        practice = app.screen
        assert isinstance(practice, QuizPracticeScreen)
        assert str(practice.query_one("#sentence-0").renderable) == "你好"
        assert not practice.query_one("#sentence-1").display
        await pilot.press("x")
        await pilot.pause()
        assert message_text(practice) == "[wrong] next -> H"
        assert practice.query_one("#word-input").value == ""
        await pilot.press("h", "i")
        await pilot.pause()
        assert practice.query_one("#word-input").value == "Hi "
        await pilot.press("escape")
        await pilot.pause()
        lib.handle_start()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.word_index == 1
        for key in "there":
            await pilot.press(key)
        await pilot.pause()
        assert app.screen.query_one("#sentence-0").display
        assert message_text(app.screen) == "Enter  next"
        await pilot.press("ctrl+g", "enter")
        await pilot.pause()
        assert app.screen.query_one("#sentence-1").display
        assert str(app.screen.query_one("#sentence-1").renderable) == "我赢了"
        for key in "iwin":
            await pilot.press(key)
        await pilot.pause()
        assert not app.screen.is_complete
        assert message_text(app.screen) == "Enter  next"
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.is_complete
        data = json.loads(store_path.with_name("quizzes.json").read_text())
        assert data[0]["completed_count"] == 1
        assert data[0]["practice_index"] == 0
        assert message_text(app.screen) == "Good  Enter back"
        await pilot.press("x")
        await pilot.pause()
        assert app.screen.is_complete
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen is lib
        assert lib.items["quiz"][0].completed_count == 1

    run(scenario)


def test_external_quiz_edit_is_never_overwritten(store_path):
    """Regression: practice used to reload the file inside each save, which
    refreshed the change-on-disk baseline and let a later library save
    silently overwrite quizzes added outside the app."""
    quiz_path = store_path.with_name("quizzes.json")
    quiz_path.write_text(json.dumps([{"id": "a", "title": "A", "pairs": [{"zh": "你好", "en": "hello world"}]}]))

    async def scenario(app, pilot):
        lib = app.screen
        await pilot.click("#filter-quiz")
        await pilot.pause()
        data = json.loads(quiz_path.read_text())
        data.append({"id": "b", "title": "B", "pairs": [{"zh": "再见", "en": "bye"}]})
        quiz_path.write_text(json.dumps(data))

        lib.load_article(lib.items["quiz"][0])
        lib.handle_start()
        await pilot.pause()
        practice = app.screen
        await pilot.press(*"hello")
        await pilot.pause()
        assert "quiz data changed on disk; reload" in message_text(practice)
        assert practice.query_one("#word-input").disabled
        await pilot.press("escape")
        await pilot.pause()

        lib.handle_save()
        assert "changed on disk" in status_text(lib)
        assert [q["id"] for q in json.loads(quiz_path.read_text())] == ["a", "b"]
        lib.handle_reload()
        await pilot.pause()
        assert [q.article_id for q in lib.items["quiz"]] == ["a", "b"]

    run(scenario)


def test_quiz_validation_and_external_reload(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        await pilot.click("#filter-quiz")
        await pilot.click("#action-new")
        lib.query_one("#editor-title").value = "Bad"
        lib.query_one("#article-body").text = "你好\nHello\n再见"
        await pilot.pause()
        lib.handle_save()
        await pilot.pause()
        assert "line 3" in status_text(lib)
        assert not store_path.with_name("quizzes.json").exists()
        lib.cancel_new()
        await pilot.pause()
        store_path.with_name("quizzes.json").write_text(json.dumps([
            {"id": "external", "title": "External", "pairs": [{"zh": "你好", "en": "Hello"}]}
        ]), encoding="utf-8")
        lib.handle_reload()
        await pilot.pause()
        assert [a.title for a in lib.filtered_articles()] == ["External"]

    run(scenario)


def test_line_copy_displays_chinese_and_practices_english(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Daily", "你好\nHi.\n再见\nBye.", mode="note")
        lib.handle_start()
        await pilot.pause()
        practice = app.screen
        assert isinstance(practice, PracticeScreen)
        assert str(practice.query_one("#sentence-0").renderable) == "你好"
        assert practice.sentence_index == 1
        await pilot.press("h", "i")
        await pilot.pause()
        assert practice.sentence_index == 3
        assert str(practice.query_one("#sentence-2").renderable) == "再见"
        await pilot.press("b", "y", "e")
        await pilot.pause()
        assert practice.is_complete

    run(scenario)


def test_unsaved_edits_are_preserved_until_saved_or_cancelled(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "One", "Original.")
        await pilot.press("ctrl+e")
        await pilot.pause()
        lib.query_one("#article-body").text = "Changed."
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert lib.editing
        assert lib.current_filter == "article"
        assert lib.query_one("#article-body").text == "Changed."
        assert status_text(lib) == "[unsaved] save or discard"

        await pilot.click("#action-cancel-new")
        await pilot.pause()
        assert not lib.editing
        assert lib.query_one("#article-body").text == "Original."
        await pilot.click("#filter-quiz")
        await pilot.pause()
        assert lib.current_filter == "quiz"

    run(scenario)


def test_empty_library_rebuild_preserves_new_draft(store_path):
    async def scenario(app, pilot):
        lib = app.screen
        lib.start_new_item("article")
        lib.query_one("#editor-title").value = "Draft"
        lib.query_one("#article-body").text = "Draft body."
        await pilot.pause()
        assert lib.query_one("#editor-title").value == "Draft"
        assert lib.query_one("#article-body").text == "Draft body."

    run(scenario)


def test_ctrl_d_deletes_from_list(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Doomed", "Hello world.")
        lib.selected_article_id = lib.items["article"][0].article_id
        lib.query_one("#article-list").focus()
        await pilot.pause()
        await pilot.press("ctrl+d")  # arm
        await pilot.press("ctrl+d")  # confirm
        await pilot.pause()
        assert lib.items["article"] == []

    run(scenario)


def test_ctrl_r_starts_practice(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Drill", "Hello world.")
        lib.selected_article_id = lib.items["article"][0].article_id
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
        assert lib.current_filter == "quiz"
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert lib.current_filter == "article"

    run(scenario)


def test_arming_delete_marks_the_row(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Doomed", "Hello world.")
        lib.selected_article_id = lib.items["article"][0].article_id
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
    lib.selected_article_id = lib.items["article"][0].article_id
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
        assert message_text(practice) == ""

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
        assert lib.items["article"][0].completed_count == 1

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


def test_resume_or_restart_incomplete_practice(store_path):
    async def scenario(app, pilot):
        lib, practice = await start_practice(pilot, app, "Hi there. Next sentence.")
        await pilot.press("H", "i")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        saved = ArticleStore(store_path).load_articles()[0]
        assert (saved.practice_sentence, saved.practice_word) == (0, 1)

        lib.handle_start()
        await pilot.pause()
        practice = app.screen
        prompt = practice.query_one("#resume-prompt")
        assert prompt.display
        assert "Enter  Continue" in str(prompt.renderable)
        assert "r  Start over" in str(prompt.renderable)
        # No input box while the prompt waits, so it can't be mistaken for one.
        assert practice.query_one("#word-input").region.height == 0
        await pilot.press("enter")
        await pilot.pause()
        assert not prompt.display
        assert practice.query_one("#word-input").region.height == 1
        assert app.focused is practice.query_one("#word-input")
        assert practice.word_index == 1
        assert practice.query_one("#word-input").value == "Hi "
        await pilot.press("escape")
        await pilot.pause()

        lib.handle_start()
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.screen.word_index == 0
        assert ArticleStore(store_path).load_articles()[0].practice_word == 0

    run(scenario)


def test_leaving_practice_keeps_library_list_intact(store_path, monkeypatch):
    async def scenario(app, pilot):
        lib, _ = await start_practice(pilot, app, "Hi there.")
        list_view = lib.query_one("#article-list")
        rows = list(list_view.children)
        rebuilds = []
        monkeypatch.setattr(lib, "refresh_article_list", lambda *args, **kwargs: rebuilds.append(True))
        await pilot.press("H", "i", "escape")
        await pilot.pause()
        assert app.screen is lib
        assert not rebuilds
        assert list(list_view.children) == rows
        assert lib.items["article"][0].practice_word == 1

    run(scenario)


def test_completed_practice_clears_saved_progress(store_path):
    async def scenario(app, pilot):
        lib, _ = await start_practice(pilot, app, "Hi there.")
        for char in "Hithere":
            await pilot.press(char)
        await pilot.pause()
        saved = ArticleStore(store_path).load_articles()[0]
        assert saved.completed_count == 1
        assert (saved.practice_sentence, saved.practice_word) == (0, 0)
        await pilot.press("x")
        await pilot.pause()
        lib.handle_start()
        await pilot.pause()
        assert not app.screen.choosing_resume

    run(scenario)


def test_fourth_completion_shows_total_in_library(store_path):
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Drill", "Hi.")
        lib.items["article"][0].completed_count = 3
        lib.stores["article"].save_articles(lib.items["article"])
        lib.refresh_articles_from_store()
        await pilot.pause()
        lib.handle_start()
        await pilot.pause()
        await pilot.press("H", "i")
        await pilot.pause()
        assert lib.stores["article"].load_articles()[0].completed_count == 4
        await pilot.press("x")
        await pilot.pause()
        item = next(item for item in lib.query(ArticleItem))
        assert str(item._label.renderable).endswith("★ ×4")
        assert str(lib.query_one("#editor-completion").renderable) == "★ ×4"

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
        lib.items["article"][0].completed_count = 1
        lib.stores["article"].save_articles(lib.items["article"])
        lib.refresh_articles_from_store()
        await pilot.pause()
        assert str(lib.query_one("#editor-completion").renderable) == "●"
        assert lib.query_one("#article-body").text == "First sentence.\nSecond sentence!"
        assert lib.query_one("#article-body").soft_wrap
        assert not lib.editor_is_dirty()
        lib.query_one("#editor-title").value = "Renamed"
        lib.handle_save()
        await pilot.pause()
        assert lib.stores["article"].load_articles()[0].body == original
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


def test_moving_highlight_rewrites_only_changed_rows(store_path, monkeypatch):
    async def scenario(app, pilot):
        lib = None
        for title in ("A", "B", "C"):
            lib = await make_article(pilot, app, title, f"{title} body.")
        lib.query_one("#article-list").focus()
        rows = list(lib.query(ArticleItem))
        assert [row.article.title for row in rows] == ["A", "B", "C"]
        updates = []
        for row in rows:
            original = row._label.update
            monkeypatch.setattr(
                row._label, "update",
                lambda value, row=row, original=original: (updates.append(row.article.title), original(value)),
            )
        lib.load_article(rows[0].article)
        await pilot.pause()
        updates.clear()
        lib.load_article(rows[1].article)
        await pilot.pause()
        # Only the old and new selection change; "C" must not be rewritten.
        assert sorted(updates) == ["A", "B"]

    run(scenario)


def test_bracket_status_text_is_shown_literally(store_path):
    # Status/messages like "[saved]" must not be parsed as Rich markup,
    # which silently drops them from the screen.
    async def scenario(app, pilot):
        lib = await make_article(pilot, app, "Greeting", "Hello world.")
        assert "[saved]" in app.export_screenshot()

    run(scenario)


def test_quit_confirmation_can_cancel_and_confirm(store_path):
    async def scenario(app, pilot):
        original = app.screen
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert "Quit?" in str(app.screen.query_one("#quit-confirm").renderable)
        await pilot.press("n")
        await pilot.pause()
        assert app.screen is original
        await pilot.press("ctrl+c")
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert not app.is_running

    run(scenario)


@pytest.mark.parametrize("disk_error", [False, True])
def test_failed_completion_stays_failed_without_awarding_star(store_path, monkeypatch, disk_error):
    async def scenario(app, pilot):
        lib, practice = await start_practice(pilot, app, "Hi.")
        original = store_path.read_bytes()
        if disk_error:
            def fail_save(items):
                raise OSError("disk full")
            monkeypatch.setattr(practice.store, "save_articles", fail_save)
        else:
            store_path.write_bytes(original + b"\n")
        await pilot.press("h", "i")
        await pilot.pause()
        assert not practice.is_complete
        assert lib.items["article"][0].completed_count == 0
        assert practice.query_one("#word-input").disabled
        assert "disk full" in message_text(practice) if disk_error else "changed on disk" in message_text(practice)
        await pilot.press("x", "r")
        await pilot.pause()
        assert app.screen is practice
        assert not practice.is_complete
        assert json.loads(store_path.read_bytes())[0]["completed_count"] == 0
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is lib

    run(scenario)


def test_sentence_highlight_tracks_typing_and_clears_on_completion(store_path):
    async def scenario(app, pilot):
        _, practice = await start_practice(pilot, app, "Hello world. Bye.")
        first = practice.query_one("#sentence-0")
        await pilot.press("h")
        await pilot.pause()
        assert str(first.renderable) == "Hello world."
        assert any(span.start == 1 and span.end == 5 and span.style == "bold underline"
                   for span in first.renderable.spans)
        await pilot.press(*"elloworld")
        await pilot.pause()
        assert not first.renderable.spans
        assert not first.has_class("article-sentence--active")
        second = practice.query_one("#sentence-1")
        assert second.has_class("article-sentence--active")
        await pilot.press(*"bye")
        await pilot.pause()
        assert practice.is_complete
        assert not second.renderable.spans
        await pilot.press("r")
        await pilot.pause()
        assert first.has_class("article-sentence--active")
        assert not second.has_class("article-sentence--active")

    run(scenario)


@pytest.mark.parametrize("mode", ["article", "quiz"])
def test_queued_typing_keeps_up_across_word_boundaries(store_path, mode):
    async def scenario(app, pilot):
        body = "Hello world this is practice."
        lib = await make_article(pilot, app, "Burst", "你好\n" + body if mode == "quiz" else body, mode=mode)
        lib.handle_start()
        await pilot.pause()
        practice = app.screen
        input_widget = practice.query_one("#word-input")
        # Queue a burst without pausing between keys, as when the UI briefly
        # falls behind. A queued Changed event used to contain stale prefixes.
        for char in "helloworldthisispractice":
            input_widget.post_message(Key(char, char))
        await pilot.pause()
        if mode == "quiz":
            assert practice.waiting_for_enter
            await pilot.press("enter")
            await pilot.pause()
        assert practice.is_complete
        assert "Good" in message_text(practice)
        assert lib.stores[mode].load_articles()[0].completed_count == 1

    run(scenario)
