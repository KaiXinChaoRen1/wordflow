"""Textual application for Wordflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import uuid4

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static, TextArea

from .parsing import extract_words
from .storage import Article, ArticleStore, ContentMode


def format_mode_label(mode: ContentMode) -> str:
    return "memo" if mode == "note" else "doc"


def format_segment_label(article: Article) -> str:
    unit = "line" if article.mode == "note" else "sentence"
    count = len(article.sentences)
    suffix = unit if count == 1 else f"{unit}s"
    return f"{count} {suffix}"


class ArticleItem(ListItem):
    """List item carrying article metadata."""

    def __init__(self, article: Article) -> None:
        self.article = article
        meta = f"{format_mode_label(article.mode)} / {format_segment_label(article)}"
        super().__init__(Label(f"{article.title}\n{meta}"))


@dataclass
class SettingsEntry:
    key: str
    title: str
    summary: str


class SettingsItem(ListItem):
    """List item carrying settings metadata."""

    def __init__(self, entry: SettingsEntry) -> None:
        self.entry = entry
        super().__init__(Label(f"{entry.title}\n{entry.summary}"))


class ImportArticlesScreen(Screen[None]):
    """Explain how to edit the article storage file directly."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]
    CSS = """
    Screen {
        background: #111111;
    }

    #settings-detail-root {
        padding: 0 1;
        height: 1fr;
    }

    .settings-title {
        color: #c8ced3;
        text-style: bold;
        margin-bottom: 0;
    }

    .settings-copy {
        color: #8d949a;
        margin-bottom: 0;
    }

    .settings-path {
        color: #d9e1e7;
        background: #101214;
        border: solid #3a3a3a;
        padding: 1;
        margin: 1 0;
    }
    """

    def __init__(self, store: ArticleStore) -> None:
        super().__init__()
        self.store = store

    def compose(self) -> ComposeResult:
        storage_path = str(self.store.path.expanduser())
        legacy_path = "~/.spelllane/articles.json"
        yield Header()
        with Vertical(id="settings-detail-root"):
            yield Static("data path", classes="settings-title")
            yield Static(
                "edit or replace the file below to update local records.",
                classes="settings-copy",
            )
            yield Static(storage_path, classes="settings-path")
            yield Static(
                "expected format: json array using the current schema.",
                classes="settings-copy",
            )
            yield Static(f"legacy path: {legacy_path}", classes="settings-copy")
        yield Footer()


class SettingsScreen(Screen[None]):
    """Secondary settings menu."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]
    CSS = """
    Screen {
        background: #111111;
    }

    #settings-root {
        padding: 0 1;
        height: 1fr;
    }

    #settings-list {
        border: solid #3a3a3a;
        background: #111111;
    }

    .settings-title {
        color: #c8ced3;
        text-style: bold;
        margin-bottom: 0;
    }

    .settings-copy {
        color: #8d949a;
        margin-bottom: 1;
    }

    #settings-list > ListItem {
        padding: 0 1;
    }

    #settings-list > ListItem.-hovered {
        background: #111111;
    }

    #settings-list > ListItem.-highlight {
        background: #202020;
        color: #d3d8dc;
    }

    #settings-list:focus > ListItem.-highlight {
        background: #202020;
        color: #d3d8dc;
    }

    Label {
        color: #c0c0c0;
    }
    """

    def __init__(self, store: ArticleStore) -> None:
        super().__init__()
        self.store = store
        self.entries = [
            SettingsEntry(
                key="import",
                title="data path",
                summary="show the live file path and edit instructions.",
            )
        ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="settings-root"):
            yield Static("config", classes="settings-title")
            yield Static("local paths and maintenance entries.", classes="settings-copy")
            yield ListView(*(SettingsItem(entry) for entry in self.entries), id="settings-list")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#settings-list", ListView).focus()

    @on(ListView.Selected, "#settings-list")
    def handle_select(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, SettingsItem):
            return

        if event.item.entry.key == "import":
            self.app.push_screen(ImportArticlesScreen(self.store))


class PracticeScreen(Screen[None]):
    """Practice a single article sentence by sentence."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]

    sentence_index = reactive(0)
    word_index = reactive(0)

    def __init__(self, article: Article) -> None:
        super().__init__()
        self.article = article
        self.current_words = extract_words(self.article.sentences[0]) if self.article.sentences else []
        self.current_prefix = ""
        self.syncing_input = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="practice-root"):
            yield Static(format_mode_label(self.article.mode), id="practice-label")
            yield Static(self.article.title, id="practice-title")
            yield Static("", id="practice-progress")
            with VerticalScroll(id="article-view"):
                for index, sentence in enumerate(self.article.sentences):
                    yield Static(sentence, id=self.sentence_widget_id(index), classes="article-sentence")
            yield Static("", id="practice-message")
            yield Input(placeholder="type letters only, spaces are automatic", id="word-input")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_sentence()
        self.query_one("#word-input", Input).focus()

    def refresh_sentence(self) -> None:
        if not self.article.sentences:
            self.finish_article()
            return

        if self.sentence_index >= len(self.article.sentences):
            self.finish_article()
            return

        sentence = self.article.sentences[self.sentence_index]
        self.current_words = extract_words(sentence)
        if not self.current_words:
            self.sentence_index += 1
            self.word_index = 0
            self.current_prefix = ""
            self.refresh_sentence()
            return

        unit = "line" if self.article.mode == "note" else "sentence"
        self.query_one("#practice-progress", Static).update(
            f"[session] {unit}={self.sentence_index + 1}/{len(self.article.sentences)} word={self.word_index + 1}/{len(self.current_words)}"
        )
        self.refresh_article_view()
        self.sync_input_value()
        self.query_one("#practice-message", Static).update("")

    def sentence_widget_id(self, index: int) -> str:
        return f"sentence-{index}"

    def refresh_article_view(self) -> None:
        for index, sentence in enumerate(self.article.sentences):
            widget = self.query_one(f"#{self.sentence_widget_id(index)}", Static)
            if index == self.sentence_index:
                widget.update(self.render_sentence(sentence))
                widget.add_class("article-sentence--active")
            else:
                widget.update(sentence)
                widget.remove_class("article-sentence--active")

        current_widget = self.query_one(f"#{self.sentence_widget_id(self.sentence_index)}", Static)
        self.call_after_refresh(self.center_current_sentence, current_widget)

    def center_current_sentence(self, current_widget: Static) -> None:
        self.query_one("#article-view", VerticalScroll).scroll_to_widget(
            current_widget,
            animate=False,
            center=True,
            immediate=True,
        )

    def render_sentence(self, sentence: str) -> Text:
        words = extract_words(sentence)
        text = Text(sentence)
        search_from = 0

        for index, word in enumerate(words):
            start = sentence.find(word, search_from)
            if start < 0:
                continue
            end = start + len(word)
            search_from = end
            if index < self.word_index:
                text.stylize("bold #2f6a3d", start, end)
            elif index == self.word_index:
                prefix_length = min(len(self.current_prefix), len(word))
                if prefix_length:
                    text.stylize("bold #2f6a3d", start, start + prefix_length)
                text.stylize("bold #b87a20", start + prefix_length, end)

        return text

    def build_input_value(self) -> str:
        completed = " ".join(self.current_words[: self.word_index])
        if completed:
            return f"{completed} {self.current_prefix}"
        return self.current_prefix

    def sync_input_value(self) -> None:
        input_widget = self.query_one("#word-input", Input)
        self.syncing_input = True
        input_widget.value = self.build_input_value()
        input_widget.cursor_position = len(input_widget.value)
        self.syncing_input = False

    @on(Input.Changed, "#word-input")
    def handle_input_changed(self, event: Input.Changed) -> None:
        if self.syncing_input or not self.current_words:
            return

        input_widget = self.query_one("#word-input", Input)
        completed = " ".join(self.current_words[: self.word_index])
        locked_prefix = f"{completed} " if completed else ""
        raw_value = event.value

        if not raw_value.startswith(locked_prefix):
            self.sync_input_value()
            self.query_one("#practice-message", Static).update("[locked] completed words")
            return

        guess = raw_value[len(locked_prefix) :].replace(" ", "")
        target = self.current_words[self.word_index]

        if not guess:
            self.current_prefix = ""
            self.sync_input_value()
            self.query_one("#practice-message", Static).update("")
            return

        if not target.casefold().startswith(guess.casefold()):
            self.sync_input_value()
            self.query_one("#practice-message", Static).update(
                f"[hint] next -> {target[len(self.current_prefix)]}"
            )
            return

        self.current_prefix = guess

        if guess.casefold() != target.casefold():
            self.sync_input_value()
            self.refresh_article_view()
            self.query_one("#practice-message", Static).update("")
            return

        self.word_index += 1
        self.current_prefix = ""

        if self.word_index >= len(self.current_words):
            self.sentence_index += 1
            self.word_index = 0
            self.refresh_sentence()
            return

        unit = "line" if self.article.mode == "note" else "sentence"
        self.query_one("#practice-progress", Static).update(
            f"[session] {unit}={self.sentence_index + 1}/{len(self.article.sentences)} word={self.word_index + 1}/{len(self.current_words)}"
        )
        self.refresh_article_view()
        self.sync_input_value()
        input_widget.cursor_position = len(input_widget.value)
        self.query_one("#practice-message", Static).update("[step] word complete")

    @on(Input.Submitted, "#word-input")
    def handle_submit(self, event: Input.Submitted) -> None:
        del event
        input_widget = self.query_one("#word-input", Input)
        input_widget.cursor_position = len(input_widget.value)

    def finish_article(self) -> None:
        self.query_one("#practice-progress", Static).update("[session] complete")
        for index, sentence in enumerate(self.article.sentences):
            widget = self.query_one(f"#{self.sentence_widget_id(index)}", Static)
            widget.update(sentence)
            widget.remove_class("article-sentence--active")
        self.query_one("#word-input", Input).disabled = True
        self.query_one("#practice-message", Static).update("[done] press Esc to return")


class LibraryScreen(Screen[None]):
    """Main library management screen."""

    BINDINGS = []

    CSS = """
    Screen {
        layout: vertical;
        background: #111111;
        color: #d0d0d0;
    }

    #library-root {
        height: 1fr;
        padding: 0 1;
    }

    #library-sidebar {
        width: 34;
        margin-right: 1;
    }

    #sidebar-card, #editor-card {
        height: 1fr;
        border: solid #3a3a3a;
        background: #111111;
        padding: 1;
    }

    #article-list {
        height: 1fr;
        border: solid #3a3a3a;
        background: #111111;
    }

    #filter-switch {
        layout: grid;
        grid-size: 2 1;
        grid-gutter: 1;
        height: 3;
        margin-bottom: 1;
    }

    .filter-button {
        min-height: 3;
        border: solid #3a3a3a;
        background: #111111;
        color: #8d949a;
    }

    .filter-button.-active {
        background: #202020;
        border: solid #4a5157;
        color: #d3d8dc;
        text-style: bold;
    }

    #editor-card {
        padding: 1;
    }

    #title-wrap {
        height: auto;
        margin-bottom: 1;
    }

    #editor-title {
        width: 1fr;
        margin-right: 1;
        border: solid #3a3a3a;
        background: #111111;
        color: #d0d0d0;
    }

    #title-hint {
        width: 30;
        color: #6f767b;
        padding-top: 1;
    }

    #article-body {
        height: 1fr;
        margin: 0;
        border: solid #3a3a3a;
        background: #111111;
        color: #d0d0d0;
    }

    #status {
        height: 2;
        margin-top: 1;
        color: #7d858a;
    }

    #action-row {
        dock: bottom;
        layout: horizontal;
        height: 1;
        padding: 0 1;
        background: #111111;
    }

    .action-button {
        width: auto;
        height: 1;
        min-height: 1;
        border: none;
        background: transparent;
        color: #9aa1a7;
        margin-right: 1;
        padding: 0 1;
    }

    .action-button:hover {
        color: #c0c6cb;
    }

    .action-button:focus {
        color: #d3d8dc;
        text-style: bold;
    }

    #article-list > ListItem {
        padding: 0 1;
        color: #c0c0c0;
    }

    #article-list > ListItem.-hovered {
        background: #111111;
    }

    #article-list > ListItem.-highlight {
        background: #111111;
        color: #c0c0c0;
    }

    #article-list:focus > ListItem.-highlight {
        background: #111111;
        color: #c0c0c0;
    }

    #article-list > ListItem.is-selected {
        background: #1f4f8a;
        color: #f2f6fa;
    }

    #article-list:focus > ListItem.is-selected {
        background: #1f4f8a;
        color: #f2f6fa;
    }

    Header {
        dock: top;
        background: #111111;
        color: #a0a0a0;
    }

    Footer {
        dock: bottom;
        background: #111111;
        color: #686868;
    }

    Input, TextArea {
        scrollbar-background: #111111;
        scrollbar-color: #3b4146;
        scrollbar-color-hover: #4a5157;
    }

    Label {
        color: #c0c0c0;
    }
    """

    selected_article_id: reactive[Optional[str]] = reactive(None)
    current_mode: reactive[ContentMode] = reactive("article")
    current_filter: reactive[ContentMode] = reactive("article")

    def __init__(self, store: ArticleStore) -> None:
        super().__init__()
        self.store = store
        self.articles: List[Article] = self.store.load_articles()
        self.is_creating_new = False
        self.previous_selected_article_id: Optional[str] = None
        self.previous_filter: ContentMode = "article"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="library-root"):
            with Vertical(id="library-sidebar"):
                with Vertical(id="sidebar-card"):
                    with Grid(id="filter-switch"):
                        yield Button("Article", id="filter-article", classes="filter-button")
                        yield Button("Memo", id="filter-note", classes="filter-button")
                    yield ListView(id="article-list")
            with Vertical(id="editor-card"):
                with Horizontal(id="title-wrap"):
                    yield Input(placeholder="name", id="editor-title")
                    yield Static("", id="title-hint")
                yield TextArea("", id="article-body")
                yield Static("", id="status")
        with Horizontal(id="action-row"):
            yield Button("New A", id="action-new-article", classes="action-button")
            yield Button("New M", id="action-new-memo", classes="action-button")
            yield Button("Save", id="action-save", classes="action-button")
            yield Button("Run", id="action-run", classes="action-button")
            yield Button("Del", id="action-delete", classes="action-button")
            yield Button("Config", id="action-settings", classes="action-button")
            yield Button("Cancel", id="action-cancel-new", classes="action-button")

    def on_mount(self) -> None:
        self.refresh_article_list()
        self.sync_mode_controls()
        self.sync_filter_controls()
        self.sync_action_controls()
        self.focus_editor()

    def refresh_article_list(self) -> None:
        list_view = self.query_one("#article-list", ListView)
        list_view.clear()
        visible_articles = self.filtered_articles()
        if visible_articles:
            list_view.extend([ArticleItem(article) for article in visible_articles])
        self.call_after_refresh(self.reconcile_article_selection)

    def reconcile_article_selection(self) -> None:
        list_view = self.query_one("#article-list", ListView)
        visible_articles = self.filtered_articles()

        if not visible_articles:
            self.selected_article_id = None
            list_view.index = None
            self.clear_editor()
            return

        if not self.selected_article_id:
            list_view.index = None
            self.sync_article_list_selected_class()
            if not self.is_creating_new:
                self.clear_editor()
            return

        selected_index: Optional[int] = None
        for index, article in enumerate(visible_articles):
            if article.article_id == self.selected_article_id:
                selected_index = index
                break

        if selected_index is None:
            self.selected_article_id = None
            list_view.index = None
            self.clear_editor()
            return

        list_view.index = selected_index
        self.load_article(visible_articles[selected_index])

    def load_article(self, article: Article) -> None:
        self.is_creating_new = False
        self.selected_article_id = article.article_id
        self.current_mode = article.mode
        self.query_one("#editor-title", Input).value = article.title
        self.query_one("#article-body", TextArea).text = article.body
        self.sync_article_list_selected_class()
        self.sync_mode_controls()
        self.sync_action_controls()
        self.query_one("#status", Static).update(
            f"[ready] {article.title} | {format_mode_label(article.mode)} | {format_segment_label(article)}"
        )

    def clear_editor(self) -> None:
        self.selected_article_id = None
        self.query_one("#editor-title", Input).value = ""
        self.query_one("#article-body", TextArea).text = ""
        self.sync_article_list_selected_class()
        self.sync_mode_controls()
        self.sync_action_controls()
        self.query_one("#status", Static).update(
            "[idle] select or create an item"
        )

    def sync_article_list_selected_class(self) -> None:
        list_view = self.query_one("#article-list", ListView)
        selected_id = self.selected_article_id
        for item in list_view.query("ListItem"):
            if not isinstance(item, ArticleItem):
                continue
            if selected_id and item.article.article_id == selected_id:
                item.add_class("is-selected")
            else:
                item.remove_class("is-selected")

    def focus_editor(self) -> None:
        self.query_one("#editor-title", Input).focus()

    def sync_mode_controls(self) -> None:
        title_input = self.query_one("#editor-title", Input)
        title_hint = self.query_one("#title-hint", Static)
        body = self.query_one("#article-body", TextArea)

        if self.current_mode == "note":
            body.border_title = "memo"
            title_hint.update("auto: current time")
            if not self.selected_article_id and not title_input.value.strip():
                title_input.value = self.store.default_note_title()
        else:
            body.border_title = "doc"
            title_hint.update("name required")

    def sync_filter_controls(self) -> None:
        article_button = self.query_one("#filter-article", Button)
        note_button = self.query_one("#filter-note", Button)

        for button, active in (
            (article_button, self.current_filter == "article"),
            (note_button, self.current_filter == "note"),
        ):
            if active:
                button.add_class("-active")
            else:
                button.remove_class("-active")

    def sync_action_controls(self) -> None:
        save_button = self.query_one("#action-save", Button)
        cancel_button = self.query_one("#action-cancel-new", Button)
        save_button.display = self.is_creating_new
        cancel_button.display = self.is_creating_new

    def filtered_articles(self) -> List[Article]:
        return [article for article in self.articles if article.mode == self.current_filter]

    def set_filter(self, mode: ContentMode) -> None:
        self.is_creating_new = False
        self.current_filter = mode
        self.current_mode = mode
        self.selected_article_id = None
        self.sync_filter_controls()
        self.sync_action_controls()
        self.refresh_article_list()

    def start_new_item(self, mode: ContentMode) -> None:
        self.is_creating_new = True
        self.previous_selected_article_id = self.selected_article_id
        self.previous_filter = self.current_filter
        self.current_mode = mode
        self.current_filter = mode
        self.selected_article_id = None
        self.sync_filter_controls()
        self.sync_action_controls()
        self.clear_editor()
        self.refresh_article_list()
        if mode == "note":
            self.query_one("#editor-title", Input).value = self.store.default_note_title()
        self.sync_mode_controls()

    @on(ListView.Selected, "#article-list")
    def handle_select(self, event: ListView.Selected) -> None:
        self.load_article_from_item(event.item)

    def load_article_from_item(self, item: Optional[ListItem]) -> None:
        if not isinstance(item, ArticleItem):
            return
        if not self.is_creating_new and self.selected_article_id == item.article.article_id:
            return
        self.load_article(item.article)

    @on(Button.Pressed, "#filter-article")
    def handle_filter_article_pressed(self) -> None:
        self.set_filter("article")

    @on(Button.Pressed, "#filter-note")
    def handle_filter_note_pressed(self) -> None:
        self.set_filter("note")

    @on(Button.Pressed, "#action-new-article")
    def handle_action_new_article_pressed(self) -> None:
        self.handle_new()

    @on(Button.Pressed, "#action-new-memo")
    def handle_action_new_memo_pressed(self) -> None:
        self.start_new_item("note")
        self.focus_editor()

    @on(Button.Pressed, "#action-save")
    def handle_action_save_pressed(self) -> None:
        self.handle_save()

    @on(Button.Pressed, "#action-run")
    def handle_action_run_pressed(self) -> None:
        self.handle_start()

    @on(Button.Pressed, "#action-delete")
    def handle_action_delete_pressed(self) -> None:
        self.handle_delete()

    @on(Button.Pressed, "#action-settings")
    def handle_action_settings_pressed(self) -> None:
        self.action_open_settings()

    @on(Button.Pressed, "#action-cancel-new")
    def handle_action_cancel_new_pressed(self) -> None:
        self.action_cancel_new()

    def handle_new(self) -> None:
        self.start_new_item("article")
        self.focus_editor()

    def action_new_article(self) -> None:
        self.handle_new()

    def action_new_memo(self) -> None:
        self.start_new_item("note")
        self.focus_editor()

    def action_cancel_new(self) -> None:
        if not self.is_creating_new:
            return

        self.is_creating_new = False
        self.current_filter = self.previous_filter
        self.current_mode = self.previous_filter
        self.selected_article_id = self.previous_selected_article_id
        self.sync_filter_controls()
        self.sync_action_controls()
        self.refresh_article_list()

    def action_open_settings(self) -> None:
        self.app.push_screen(SettingsScreen(self.store))

    def handle_save(self) -> None:
        title = self.query_one("#editor-title", Input).value.strip()
        body = self.query_one("#article-body", TextArea).text.strip()

        if not body:
            self.query_one("#status", Static).update("[missing] body")
            return

        if self.current_mode == "article" and not title:
            self.query_one("#status", Static).update("[missing] name for doc")
            return

        target_article_id = self.selected_article_id or str(uuid4())
        updated_articles = self.store.upsert_article(
            self.articles,
            title=title,
            body=body,
            mode=self.current_mode,
            article_id=target_article_id,
        )
        self.articles = updated_articles
        self.is_creating_new = False
        self.selected_article_id = target_article_id
        saved_article = next((article for article in self.articles if article.article_id == target_article_id), None)
        if saved_article is not None:
            self.current_mode = saved_article.mode
            self.query_one("#editor-title", Input).value = saved_article.title
        self.refresh_article_list()
        self.query_one("#status", Static).update(f"[saved] {format_mode_label(self.current_mode)}")

    def action_save_article(self) -> None:
        self.handle_save()

    def handle_delete(self) -> None:
        if not self.selected_article_id:
            self.query_one("#status", Static).update("[missing] select an item")
            return

        self.articles = self.store.delete_article(self.articles, self.selected_article_id)
        self.selected_article_id = None
        self.refresh_article_list()
        self.query_one("#status", Static).update("[removed] item")

    def action_delete_article(self) -> None:
        self.handle_delete()

    def handle_start(self) -> None:
        article = next((item for item in self.articles if item.article_id == self.selected_article_id), None)
        if article is None:
            self.query_one("#status", Static).update("[missing] select an item")
            return

        if not article.sentences:
            unit = "lines" if article.mode == "note" else "sentences"
            self.query_one("#status", Static).update(f"[invalid] {format_mode_label(article.mode)} has no {unit}")
            return

        self.app.push_screen(PracticeScreen(article))

    def action_run_article(self) -> None:
        self.handle_start()


class WordflowApp(App[None]):
    """Main application."""

    TITLE = "Indexer"
    SUB_TITLE = "local records"
    ENABLE_COMMAND_PALETTE = False
    COMMAND_PALETTE_BINDING = ""

    CSS = """
    Header {
        dock: top;
        background: #111111;
        color: #a0a0a0;
    }

    Footer {
        dock: bottom;
        background: #111111;
        color: #686868;
    }

    Screen {
        background: #111111;
        color: #d0d0d0;
    }

    #practice-root {
        padding: 0 1;
        height: 1fr;
    }

    #practice-label {
        color: #8d949a;
        margin-bottom: 0;
    }

    #practice-title {
        color: #d3d8dc;
        text-style: bold;
        margin-bottom: 0;
    }

    #practice-progress {
        color: #747b80;
        margin-bottom: 0;
    }

    #article-view {
        height: 1fr;
        margin: 0;
        border: solid #3a3a3a;
        background: #101214;
        scrollbar-background: #101214;
        scrollbar-color: #3b4146;
        scrollbar-color-hover: #4a5157;
        scrollbar-size-vertical: 1;
    }

    .article-sentence {
        padding: 0 1;
        margin: 0;
        color: #848b91;
        background: #101214;
    }

    .article-sentence--active {
        color: #d3d8dc;
        background: #1c2126;
        text-style: bold;
    }

    #practice-message {
        height: 1;
        margin: 0;
        color: #7d858a;
    }

    #word-input {
        border: solid #3a3a3a;
        background: #101214;
        color: #c8ced3;
        dock: bottom;
    }
    """

    def on_mount(self) -> None:
        self.push_screen(LibraryScreen(ArticleStore()))

    def action_command_palette(self) -> None:
        """Disable the default Textual command palette."""
        return
