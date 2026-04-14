"""Textual application for Wordflow."""

from __future__ import annotations

from typing import Callable, List, Optional
from uuid import uuid4

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Click
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    TextArea,
)

from .parsing import extract_words
from .storage import Article, ArticleStore, ContentMode


class ArticleItem(ListItem):
    """List item carrying article metadata."""

    def __init__(self, article: Article) -> None:
        self.article = article
        gold_star = "[gold1]★[/gold1]"
        gray_star = "[dim]☆[/dim]"
        stars = gold_star * article.completed_count + gray_star * (3 - article.completed_count)
        title = article.title or "(untitled)"
        super().__init__(Label(Text.from_markup(f"{title}\n{stars}")))


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
        background: #121416;
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


class PracticeScreen(Screen[None]):
    """Practice a single article sentence by sentence."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]

    sentence_index = reactive(0)
    word_index = reactive(0)

    def __init__(
        self,
        article: Article,
        store: ArticleStore,
        on_completed: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self.article = article
        self.store = store
        self.on_completed = on_completed
        self.current_words = (
            extract_words(self.article.sentences[0]) if self.article.sentences else []
        )
        self.current_prefix = ""
        self.syncing_input = False
        self.is_complete = False

    def compose(self) -> ComposeResult:
        with Vertical(id="practice-root"):
            yield Static(self.article.title, id="practice-title")
            with VerticalScroll(id="article-view"):
                for index, sentence in enumerate(self.article.sentences):
                    yield Static(
                        sentence,
                        id=self.sentence_widget_id(index),
                        classes="article-sentence",
                    )
            yield Static("", id="practice-message")
            yield Input(placeholder="type", id="word-input")
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
        if self.is_complete or self.syncing_input or not self.current_words:
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

        self.refresh_article_view()
        self.sync_input_value()
        input_widget.cursor_position = len(input_widget.value)
        self.query_one("#practice-message", Static).update("[step] word complete")

    @on(Input.Submitted, "#word-input")
    def handle_submit(self, event: Input.Submitted) -> None:
        del event
        input_widget = self.query_one("#word-input", Input)
        input_widget.cursor_position = len(input_widget.value)

    def on_key(self, event) -> None:
        if self.is_complete:
            event.stop()
            self.app.pop_screen()

    def finish_article(self) -> None:
        if self.is_complete:
            return

        self.is_complete = True
        for index, sentence in enumerate(self.article.sentences):
            widget = self.query_one(f"#{self.sentence_widget_id(index)}", Static)
            widget.update(sentence)
            widget.remove_class("article-sentence--active")
        input_widget = self.query_one("#word-input", Input)
        input_widget.value = ""
        input_widget.disabled = True
        self.query_one("#practice-message", Static).update(
            "[bold #6fbf73]Good[/bold #6fbf73]  press any key"
        )

        completed_article = self.store.complete_article(self.article.article_id)
        if completed_article is not None:
            self.article.completed_count = completed_article.completed_count
            if self.on_completed is not None:
                self.on_completed()


class LibraryScreen(Screen[None]):
    """Main library management screen."""

    BINDINGS = []

    CSS = """
    Screen {
        layout: vertical;
        background: #101113;
        color: #c9cdd1;
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
        border: none;
        background: transparent;
        padding: 1;
    }

    #article-list {
        height: 1fr;
        border: none;
        background: #111316;
        color: #aeb4b9;
    }

    #filter-switch {
        height: 1;
        margin-bottom: 1;
        background: #111316;
    }

    #filter-label {
        width: 6;
        height: 1;
        color: #5f666c;
    }

    .filter-button {
        width: 11;
        height: 1;
        min-height: 1;
        background: #111316;
        color: #767d83;
        margin-right: 1;
        padding: 0 1;
        text-style: none;
    }

    .filter-button.-active {
        background: #26312b;
        color: #d4d9dd;
        text-style: bold;
    }

    .filter-button:hover {
        background: #1a1d20;
        color: #c0c6cb;
    }

    .filter-button:focus {
        background: #1a1d20;
        color: #cfd4d8;
        outline: none;
    }

    #editor-card {
        padding: 1;
    }

    #editor-title {
        width: 1fr;
        height: 1;
        min-height: 1;
        padding: 0 1;
        border: none;
        background: #111316;
        color: #c9cdd1;
        margin-bottom: 1;
    }

    #article-body {
        height: 1fr;
        margin: 0;
        border: none;
        background: #111316;
        color: #c9cdd1;
    }

    #status {
        height: 2;
        margin-top: 1;
        color: #6a7177;
    }

    #action-row {
        dock: bottom;
        layout: horizontal;
        height: 1;
        padding: 0 1;
        background: #101113;
    }

    .action-button {
        width: auto;
        height: 1;
        min-height: 1;
        border: none;
        background: transparent;
        color: #848b91;
        margin-right: 1;
        padding: 0 1;
    }

    .action-button:hover {
        color: #adb3b8;
    }

    .action-button:focus {
        color: #cfd4d8;
        text-style: bold;
    }

    #article-list > ListItem {
        padding: 0 1;
        background: transparent;
    }

    #article-list > ListItem Label {
        background: transparent;
        color: #aeb4b9;
    }

    #article-list > ListItem.-hovered,
    #article-list > ListItem.-highlight,
    #article-list:focus > ListItem.-highlight,
    #article-list > ListItem.is-selected,
    #article-list:focus > ListItem.is-selected {
        background: transparent;
    }

    #article-list > ListItem.is-selected,
    #article-list > ListItem.is-selected Label {
        color: #d4d9dd;
        text-style: bold;
    }

    Footer {
        dock: bottom;
        background: #101113;
        color: #575d62;
    }

    Input, TextArea {
        scrollbar-background: #111316;
        scrollbar-color: #30363b;
        scrollbar-color-hover: #3b4248;
    }

    Label {
        color: #aeb4b9;
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
        with Horizontal(id="library-root"):
            with Vertical(id="library-sidebar"):
                with Vertical(id="sidebar-card"):
                    with Horizontal(id="filter-switch"):
                        yield Static("mode", id="filter-label")
                        yield Static(
                            "article",
                            id="filter-article",
                            classes="filter-button",
                            markup=False,
                        )
                        yield Static(
                            "memo",
                            id="filter-note",
                            classes="filter-button",
                            markup=False,
                        )
                    yield ListView(id="article-list")
            with Vertical(id="editor-card"):
                yield Input(placeholder="name", id="editor-title")
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
        self.sync_action_controls()
        self.query_one("#status", Static).update(f"[ready] {article.title}")

    def clear_editor(self) -> None:
        self.selected_article_id = None
        if not self.is_creating_new:
            self.current_mode = self.current_filter
        self.query_one("#editor-title", Input).value = ""
        self.query_one("#article-body", TextArea).text = ""
        self.sync_article_list_selected_class()
        self.sync_action_controls()
        self.query_one("#status", Static).update("[idle] select or create")

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

    def sync_filter_controls(self) -> None:
        article_button = self.query_one("#filter-article", Static)
        note_button = self.query_one("#filter-note", Static)

        for button, active in (
            (article_button, self.current_filter == "article"),
            (note_button, self.current_filter == "note"),
        ):
            label = "article" if button.id == "filter-article" else "memo"
            button.update(f"> {label}" if active else f"  {label}")
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
        self.query_one("#editor-title", Input).value = (
            self.store.default_note_title() if mode == "note" else ""
        )
        self.query_one("#article-body", TextArea).text = ""
        self.query_one("#status", Static).update("[new] edit then save")
        self.sync_filter_controls()
        self.sync_action_controls()
        self.refresh_article_list()
        self.focus_editor()

    @on(ListView.Selected, "#article-list")
    def handle_select(self, event: ListView.Selected) -> None:
        self.load_article_from_item(event.item)

    def load_article_from_item(self, item: Optional[ListItem]) -> None:
        if not isinstance(item, ArticleItem):
            return
        if not self.is_creating_new and self.selected_article_id == item.article.article_id:
            return
        self.load_article(item.article)

    @on(Click, "#filter-article")
    def handle_filter_article_pressed(self, event: Click) -> None:
        event.stop()
        self.set_filter("article")

    @on(Click, "#filter-note")
    def handle_filter_note_pressed(self, event: Click) -> None:
        event.stop()
        self.set_filter("note")

    @on(Button.Pressed, "#action-new-article")
    def handle_action_new_article_pressed(self) -> None:
        self.handle_new()

    @on(Button.Pressed, "#action-new-memo")
    def handle_action_new_memo_pressed(self) -> None:
        self.start_new_item("note")

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
        self.open_settings()

    @on(Button.Pressed, "#action-cancel-new")
    def handle_action_cancel_new_pressed(self) -> None:
        self.cancel_new()

    def handle_new(self) -> None:
        self.start_new_item("article")

    def cancel_new(self) -> None:
        if not self.is_creating_new:
            return

        self.is_creating_new = False
        self.current_filter = self.previous_filter
        self.current_mode = self.previous_filter
        self.selected_article_id = self.previous_selected_article_id
        self.sync_filter_controls()
        self.sync_action_controls()
        self.refresh_article_list()

    def open_settings(self) -> None:
        self.app.push_screen(ImportArticlesScreen(self.store))

    def handle_save(self) -> None:
        title = self.query_one("#editor-title", Input).value.strip()
        body = self.query_one("#article-body", TextArea).text.strip()

        if not body:
            self.query_one("#status", Static).update("[missing] body")
            return

        if self.current_mode == "article" and not title:
            self.query_one("#status", Static).update("[missing] name")
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
        saved_article = next(
            (article for article in self.articles if article.article_id == target_article_id),
            None,
        )
        if saved_article is not None:
            self.current_mode = saved_article.mode
            self.query_one("#editor-title", Input).value = saved_article.title
        self.refresh_article_list()
        self.query_one("#status", Static).update("[saved]")

    def handle_delete(self) -> None:
        if not self.selected_article_id:
            self.query_one("#status", Static).update("[missing] select an item")
            return

        self.articles = self.store.delete_article(self.articles, self.selected_article_id)
        self.selected_article_id = None
        self.refresh_article_list()
        self.query_one("#status", Static).update("[removed] item")

    def handle_start(self) -> None:
        article = next(
            (item for item in self.articles if item.article_id == self.selected_article_id),
            None,
        )
        if article is None:
            self.query_one("#status", Static).update("[missing] select an item")
            return

        if not article.sentences:
            self.query_one("#status", Static).update("[invalid] empty")
            return

        self.app.push_screen(PracticeScreen(article, self.store, self.refresh_articles_from_store))

    def refresh_articles_from_store(self) -> None:
        selected_article_id = self.selected_article_id
        self.articles = self.store.load_articles()
        self.selected_article_id = selected_article_id
        self.refresh_article_list()


class WordflowApp(App[None]):
    """Main application."""

    TITLE = "Indexer"
    SUB_TITLE = "local records"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Footer {
        dock: bottom;
        background: #101113;
        color: #575d62;
    }

    Screen {
        background: #101113;
        color: #c9cdd1;
    }

    #practice-root {
        padding: 0 1;
        height: 1fr;
    }

    #practice-title {
        color: #cfd4d8;
        text-style: bold;
        margin-bottom: 0;
    }

    #article-view {
        height: 1fr;
        margin: 0;
        border: none;
        background: #111316;
        scrollbar-background: #111316;
        scrollbar-color: #30363b;
        scrollbar-color-hover: #3b4248;
        scrollbar-size-vertical: 1;
    }

    .article-sentence {
        padding: 0 1;
        margin: 0;
        color: #7c8389;
        background: #111316;
    }

    .article-sentence--active {
        color: #ccd1d6;
        background: #171a1d;
        text-style: bold;
    }

    #practice-message {
        height: 1;
        margin: 0;
        color: #666d73;
    }

    #word-input {
        border: none;
        background: #111316;
        color: #c7ccd1;
        dock: bottom;
    }
    """

    def on_mount(self) -> None:
        self.push_screen(LibraryScreen(ArticleStore()))
