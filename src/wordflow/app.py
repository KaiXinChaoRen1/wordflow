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

from .parsing import extract_words, quiz_words
from .storage import DEFAULT_GROUP, Article, ArticleStore, ContentMode, Quiz, QuizStore


def completion_marks(article: Article) -> Text:
    lit = min(3, article.completed_count)
    return Text.assemble(
        ("●" * lit, "#a4884a"),
        ("○" * (3 - lit), "dim"),
        (f" *{article.completed_count}" if article.completed_count > 3 else "", "dim"),
    )


class GroupHeader(ListItem):
    """Quiet section label for grouped article rows."""

    def __init__(self, group: str, count: int, expanded: bool) -> None:
        self.group = group
        self.count = count
        marker = "-" if expanded else "+"
        super().__init__(
            Label(Text.assemble((f"{marker} ", "dim"), (group, "dim"), (f" · {count}", "dim")))
        )


class ArticleItem(ListItem):
    """List item carrying article metadata."""

    def __init__(self, article: Article) -> None:
        self.article = article
        self._label = Label(self._label_text(selected=False))
        super().__init__(self._label)

    def _label_text(self, selected: bool, armed: bool = False) -> Text:
        title = self.article.title or "(untitled)"
        # An armed (awaiting-confirm) delete outranks the selection marker so a
        # glance at the row tells you what the next Del press will remove.
        marker = "!" if armed else (">" if selected else " ")
        return Text.assemble(
            f"{marker}   ",
            title,
            "  ",
            completion_marks(self.article),
            no_wrap=True,
        )

    def set_selected(self, selected: bool, armed: bool = False) -> None:
        self._label.update(self._label_text(selected, armed))


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
            yield Static("quiz data path", classes="settings-title")
            yield Static(str(self.store.path.with_name("quizzes.json")), classes="settings-path")
            yield Static(
                "edit JSON, then use reload in the library.",
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
        on_progress: Optional[Callable[[Article], None]] = None,
    ) -> None:
        super().__init__()
        self.article = article
        self.store = store
        self.on_completed = on_completed
        self.on_progress = on_progress
        self.current_words = (
            extract_words(self.article.sentences[0]) if self.article.sentences else []
        )
        self.current_prefix = ""
        self.active_sentence_index: Optional[int] = None
        self.is_complete = False
        self.choosing_resume = bool(article.practice_sentence or article.practice_word)
        self.progress_changed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="practice-root"):
            yield Static(self.article.title, id="practice-title")
            yield Static(
                f"Paused at sentence {self.article.practice_sentence + 1} of {len(self.article.sentences)}\n"
                "Enter  Continue    r  Start over",
                id="resume-prompt",
                markup=False,
            )
            yield Static("", id="practice-progress")
            with VerticalScroll(id="article-view"):
                for index, sentence in enumerate(self.article.sentences):
                    yield Static(
                        self.display_sentence(index),
                        id=self.sentence_widget_id(index),
                        classes="article-sentence",
                        markup=False,
                    )
            yield Static("", id="practice-message")
            yield Input(placeholder="type", id="word-input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#resume-prompt", Static).display = self.choosing_resume
        if self.choosing_resume:
            self.query_one("#word-input", Input).disabled = True
            return
        self.refresh_sentence()
        self.query_one("#word-input", Input).focus()

    def on_unmount(self) -> None:
        if self.progress_changed and self.on_progress is not None:
            self.on_progress(self.article)

    def refresh_sentence(self) -> None:
        while self.sentence_index < len(self.article.sentences):
            self.current_words = self.practice_words(self.article.sentences[self.sentence_index])
            if self.current_words:
                break
            self.sentence_index += 1
            self.word_index = 0
            self.current_prefix = ""
        else:
            self.finish_article()
            return

        self.refresh_article_view()
        self.refresh_progress()
        self.sync_input_value()
        self.set_message("")

    def refresh_progress(self) -> None:
        total = len(self.article.sentences)
        progress = self.query_one("#practice-progress", Static)
        if not total:
            progress.update(Text(""))
            return
        current = min(self.sentence_index + 1, total)
        progress.update(Text(f"{current} / {total}", "dim"))

    def sentence_widget_id(self, index: int) -> str:
        return f"sentence-{index}"

    def display_sentence(self, index: int) -> str:
        return self.article.sentences[index]

    def practice_words(self, sentence: str) -> List[str]:
        return extract_words(sentence)

    def show_wrong_input(self, target: str) -> None:
        self.set_message(f"[hint] next -> {target[len(self.current_prefix)]}")

    def set_message(self, text: str) -> None:
        self.query_one("#practice-message", Static).update(text)

    def refresh_article_view(self) -> None:
        previous_index = self.active_sentence_index
        changed_sentence = previous_index != self.sentence_index
        if changed_sentence and previous_index is not None:
            previous = self.query_one(f"#{self.sentence_widget_id(previous_index)}", Static)
            previous.update(Text(self.article.sentences[previous_index]))
            previous.remove_class("article-sentence--active")

        current_widget = self.query_one(f"#{self.sentence_widget_id(self.sentence_index)}", Static)
        current_widget.update(self.render_sentence(self.article.sentences[self.sentence_index]))
        current_widget.add_class("article-sentence--active")
        self.active_sentence_index = self.sentence_index
        if changed_sentence:
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
        value = self.build_input_value()
        # Programmatic corrections must not re-enter the input event queue.
        # A single remembered value cannot identify multiple queued changes.
        with input_widget.prevent(Input.Changed):
            input_widget.value = value
        input_widget.cursor_position = len(value)

    @on(Input.Changed, "#word-input")
    def handle_input_changed(self, event: Input.Changed) -> None:
        if self.is_complete or not self.current_words:
            return

        input_widget = self.query_one("#word-input", Input)
        completed = " ".join(self.current_words[: self.word_index])
        locked_prefix = f"{completed} " if completed else ""
        raw_value = event.value

        if not raw_value.startswith(locked_prefix):
            self.sync_input_value()
            self.set_message("[locked] completed words")
            return

        guess = raw_value[len(locked_prefix) :].replace(" ", "")
        target = self.current_words[self.word_index]

        if not guess:
            self.current_prefix = ""
            self.sync_input_value()
            self.refresh_article_view()
            self.set_message("")
            return

        if not target.casefold().startswith(guess.casefold()):
            self.sync_input_value()
            self.show_wrong_input(target)
            return

        self.current_prefix = guess

        if guess.casefold() != target.casefold():
            self.sync_input_value()
            self.refresh_article_view()
            self.set_message("")
            return

        self.word_index += 1
        self.current_prefix = ""

        if self.word_index >= len(self.current_words):
            self.sentence_index += 1
            self.word_index = 0
            self.refresh_sentence()
            if not self.is_complete:
                self.save_progress()
            return

        self.save_progress()
        self.refresh_article_view()
        self.sync_input_value()
        input_widget.cursor_position = len(input_widget.value)
        self.set_message("[step] word complete")

    def on_key(self, event) -> None:
        if self.choosing_resume:
            if event.key not in ("enter", "r"):
                return
            event.stop()
            self.choosing_resume = False
            self.query_one("#resume-prompt", Static).display = False
            if event.key == "enter":
                self.sentence_index = self.article.practice_sentence
                self.word_index = self.article.practice_word
            else:
                self.sentence_index = 0
                self.word_index = 0
                self.save_progress()
            input_widget = self.query_one("#word-input", Input)
            input_widget.disabled = False
            self.refresh_sentence()
            input_widget.focus()
            return
        if not self.is_complete:
            return
        event.stop()
        if event.key == "r":
            self.restart_practice()
        else:
            self.app.pop_screen()

    def save_progress(self) -> None:
        self.store.save_practice_progress(
            self.article.article_id, self.sentence_index, self.word_index
        )
        self.article.practice_sentence = self.sentence_index
        self.article.practice_word = self.word_index
        self.progress_changed = True

    def restart_practice(self) -> None:
        self.is_complete = False
        self.active_sentence_index = None
        self.sentence_index = 0
        self.word_index = 0
        self.current_prefix = ""
        self.save_progress()
        input_widget = self.query_one("#word-input", Input)
        input_widget.disabled = False
        self.refresh_sentence()
        input_widget.focus()

    def finish_article(self) -> None:
        if self.is_complete:
            return

        self.is_complete = True
        for index, sentence in enumerate(self.article.sentences):
            widget = self.query_one(f"#{self.sentence_widget_id(index)}", Static)
            widget.update(self.display_sentence(index))
            widget.remove_class("article-sentence--active")
        input_widget = self.query_one("#word-input", Input)
        with input_widget.prevent(Input.Changed):
            input_widget.value = ""
        input_widget.disabled = True
        self.refresh_progress()
        self.set_message("[bold #6fbf73]Good[/bold #6fbf73]  r repeat · any key back")

        completed_article = self.store.complete_article(self.article.article_id)
        if completed_article is not None:
            self.article.completed_count = completed_article.completed_count
            self.article.practice_sentence = 0
            self.article.practice_word = 0
            self.progress_changed = False
            if self.on_completed is not None:
                self.on_completed()


class QuizPracticeScreen(PracticeScreen):
    BINDINGS = [("escape", "app.pop_screen", "Back"), ("ctrl+g", "hint", "Hint")]

    def on_mount(self) -> None:
        for index in range(len(self.article.sentences)):
            self.query_one(f"#{self.sentence_widget_id(index)}", Static).display = (
                index == self.article.practice_sentence if self.choosing_resume else index == 0
            )
        super().on_mount()

    def display_sentence(self, index: int) -> str:
        assert isinstance(self.article, Quiz) and self.article.pairs is not None
        return self.article.pairs[index]["zh"]

    def practice_words(self, sentence: str) -> List[str]:
        return quiz_words(sentence)

    def refresh_progress(self) -> None:
        current = min(self.sentence_index + 1, len(self.article.sentences))
        self.query_one("#practice-progress", Static).update(
            Text(f"{current} / {len(self.article.sentences)} · Ctrl+G hint", "dim")
        )

    def show_wrong_input(self, target: str) -> None:
        self.set_message("[wrong]")

    def refresh_article_view(self) -> None:
        for index in range(len(self.article.sentences)):
            widget = self.query_one(f"#{self.sentence_widget_id(index)}", Static)
            widget.display = index == self.sentence_index
        self.active_sentence_index = self.sentence_index

    def action_hint(self) -> None:
        if not self.is_complete and not self.choosing_resume and self.current_words:
            target = self.current_words[self.word_index]
            self.set_message(f"[hint] next -> {target[len(self.current_prefix)]}")


class LibraryScreen(Screen[None]):
    """Main library management screen."""

    BINDINGS = [
        ("ctrl+n", "new_article", "New"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+r", "run", "Run"),
        ("ctrl+d", "delete", "Del"),
        ("ctrl+t", "toggle_filter", "Mode"),
        ("ctrl+l", "focus_list", "List"),
        ("ctrl+e", "edit", "Edit"),
        ("escape", "close_editor", "Back"),
    ]

    CSS = """
    Screen {
        layout: vertical;
        background: #101113;
        color: #c9cdd1;
    }

    #library-root {
        height: 1fr;
        padding: 0 1;
        align-horizontal: center;
    }

    #library-sidebar {
        width: 1fr;
        max-width: 100;
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
        scrollbar-size-vertical: 1;
        overflow-x: auto;
        scrollbar-size-horizontal: 1;
    }

    #filter-switch {
        height: 1;
        margin-bottom: 1;
        background: transparent;
    }

    #filter-label {
        width: 6;
        height: 1;
        color: #5f666c;
    }

    .filter-button {
        width: 12;
        height: 1;
        min-height: 1;
        background: transparent;
        color: #767d83;
        margin-right: 0;
        padding: 0;
        text-style: none;
    }

    .filter-button.-active {
        background: transparent;
        color: #d4d9dd;
        text-style: bold;
    }

    .filter-button:hover {
        background: transparent;
        color: #c0c6cb;
    }

    .filter-button:focus {
        background: transparent;
        color: #cfd4d8;
        outline: none;
    }

    #editor-card {
        display: none;
        width: 1fr;
        max-width: 100;
        padding: 1;
    }

    #editor-heading {
        height: 2;
    }

    #split-options {
        height: 1;
        margin-bottom: 1;
    }

    #split-label {
        width: 8;
        color: #767d83;
    }

    .split-button {
        width: 12;
        min-width: 0;
        height: 1;
        min-height: 1;
        border: none;
        padding: 0;
        background: transparent;
        color: #767d83;
    }

    .split-button.is-active {
        color: #d4d9dd;
        text-style: bold;
    }

    #editor-completion {
        width: auto;
        height: 1;
        margin-left: 1;
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

    #editor-group {
        width: 1fr;
        height: 1;
        min-height: 1;
        padding: 0 1;
        border: none;
        background: #111316;
        color: #9fa6ac;
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
        height: 1;
        padding: 0 2;
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
        min-width: 0;
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
        width: auto;
        min-width: 100%;
        height: 1;
        padding: 0 1;
        background: transparent;
    }

    #article-list > ListItem Label {
        width: auto;
        background: transparent;
        color: #aeb4b9;
    }

    #article-list > ListItem.group-header Label {
        color: #697178;
        text-style: bold;
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
        color: #ebeef0;
        text-style: bold;
    }

    Footer {
        dock: bottom;
        background: #101113;
        color: #6a7177;
    }

    Input, TextArea {
        scrollbar-background: #111316;
        scrollbar-color: #30363b;
        scrollbar-color-hover: #3b4248;
        scrollbar-size-vertical: 1;
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
        self.quiz_store = QuizStore(store.path.with_name("quizzes.json"))
        self.articles: List[Article] = self.store.load_articles() + self.quiz_store.load_articles()
        self.is_creating_new = False
        self.previous_selected_article_id: Optional[str] = None
        self.previous_filter: ContentMode = "article"
        # When False, the next (deferred) reconcile keeps the status the
        # current action just set instead of replacing it with [ready]/[idle].
        self.announce_on_reconcile = True
        # Snapshot of the editor's last saved/loaded content, used to tell
        # whether there are unsaved edits.
        self.loaded_title = ""
        self.loaded_group = DEFAULT_GROUP
        self.loaded_body = ""
        self.loaded_mode: ContentMode = "article"
        # Article armed for deletion, awaiting a confirming second Del press.
        self.pending_delete_id: Optional[str] = None
        self.expanded_groups: set[str] = set()
        self.pending_highlight_group: Optional[str] = None
        self.editing = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="library-root"):
            with Vertical(id="library-sidebar"):
                with Vertical(id="sidebar-card"):
                    with Horizontal(id="filter-switch"):
                        yield Static(
                            "copy",
                            id="filter-article",
                            classes="filter-button",
                            markup=False,
                        )
                        yield Static("quiz", id="filter-quiz", classes="filter-button", markup=False)
                    yield ListView(id="article-list")
            with Vertical(id="editor-card"):
                yield Input(placeholder="group", id="editor-group")
                with Horizontal(id="editor-heading"):
                    yield Input(placeholder="name", id="editor-title")
                    yield Static("", id="editor-completion")
                with Horizontal(id="split-options"):
                    yield Static("split", id="split-label")
                    yield Button("sentence", id="split-sentence", classes="split-button")
                    yield Button("line", id="split-line", classes="split-button")
                yield TextArea("", id="article-body")
        yield Static("", id="status")
        with Horizontal(id="action-row"):
            yield Button("+new", id="action-new", classes="action-button")
            yield Button("edit", id="action-edit", classes="action-button")
            yield Button("save", id="action-save", classes="action-button")
            yield Button("discard", id="action-cancel-new", classes="action-button")
            yield Button("back", id="action-back", classes="action-button")
            yield Button("run", id="action-run", classes="action-button")
            yield Button("del", id="action-delete", classes="action-button")
            yield Button("config", id="action-settings", classes="action-button")
            yield Button("reload", id="action-reload", classes="action-button")

    def on_mount(self) -> None:
        self.refresh_article_list()
        self.sync_filter_controls()
        self.sync_action_controls()
        self.query_one("#article-list", ListView).focus()

    def refresh_article_list(self, announce_status: bool = True) -> None:
        self.announce_on_reconcile = announce_status
        self.run_worker(
            self.rebuild_article_list(),
            group="article-list",
            exclusive=True,
        )

    async def rebuild_article_list(self) -> None:
        list_view = self.query_one("#article-list", ListView)
        list_view.index = None
        await list_view.clear()
        visible_items = self.visible_list_items()
        if visible_items:
            await list_view.extend(visible_items)
        self.reconcile_article_selection()

    def visible_list_items(self) -> List[ListItem]:
        items: List[ListItem] = []
        for group, articles in self.grouped_articles():
            expanded = group in self.expanded_groups
            header = GroupHeader(group, len(articles), expanded)
            header.add_class("group-header")
            items.append(header)
            if expanded:
                items.extend(ArticleItem(article) for article in articles)
        return items

    def reconcile_article_selection(self) -> None:
        announce = self.announce_on_reconcile
        self.announce_on_reconcile = True
        list_view = self.query_one("#article-list", ListView)
        pending_group = self.pending_highlight_group
        if not self.filtered_articles():
            self.pending_highlight_group = None
            self.selected_article_id = None
            list_view.index = None
            if not self.is_creating_new:
                self.clear_editor(announce=announce)
            return

        if not self.selected_article_id:
            self.sync_article_list_selected_class()
            if not self.is_creating_new:
                self.clear_editor(announce=announce)
            self.apply_pending_or_clear(list_view, pending_group)
            return

        selected_index: Optional[int] = None
        for index, item in enumerate(list_view.children):
            if (
                isinstance(item, ArticleItem)
                and item.article.article_id == self.selected_article_id
            ):
                selected_index = index
                break

        if selected_index is None:
            if any(
                article.article_id == self.selected_article_id
                for article in self.filtered_articles()
            ):
                self.sync_article_list_selected_class()
                self.apply_pending_or_clear(list_view, pending_group)
            else:
                self.apply_pending_or_clear(list_view, pending_group)
                self.selected_article_id = None
                self.clear_editor(announce=announce)
            return

        selected_item = list_view.children[selected_index]
        if (
            pending_group
            and isinstance(selected_item, ArticleItem)
            and (
                selected_item.article.group != pending_group
                or pending_group in self.expanded_groups
            )
            and self.apply_pending_or_clear(list_view, pending_group)
        ):
            return

        list_view.index = selected_index
        if isinstance(selected_item, ArticleItem) and not self.editor_is_dirty():
            self.load_article(selected_item.article, announce=announce)

    def highlight_group_header(self, list_view: ListView, group: Optional[str]) -> bool:
        if not group:
            return False
        for index, item in enumerate(list_view.children):
            if isinstance(item, GroupHeader) and item.group == group:
                list_view.index = index
                return True
        return False

    def apply_pending_or_clear(self, list_view: ListView, group: Optional[str]) -> bool:
        if self.highlight_group_header(list_view, group):
            self.pending_highlight_group = None
            return True
        list_view.index = None
        return False

    def load_article(self, article: Article, announce: bool = True) -> None:
        self.is_creating_new = False
        self.pending_delete_id = None
        self.selected_article_id = article.article_id
        self.current_mode = article.mode
        self.query_one("#editor-title", Input).value = article.title
        self.query_one("#editor-group", Input).value = article.group
        body = "\n".join(article.sentences) if article.mode == "article" else article.body
        self.query_one("#article-body", TextArea).text = body
        self.query_one("#editor-completion", Static).update(completion_marks(article))
        self.mark_editor_saved(article.title, article.group, body)
        self.sync_article_list_selected_class()
        self.sync_action_controls()
        if announce:
            self.set_status("[ready] Enter to run in list")

    def clear_editor(self, announce: bool = True) -> None:
        self.pending_delete_id = None
        self.selected_article_id = None
        if not self.is_creating_new:
            self.current_mode = self.current_filter
        group = DEFAULT_GROUP
        self.query_one("#editor-title", Input).value = ""
        self.query_one("#editor-group", Input).value = group
        self.query_one("#editor-completion", Static).update("")
        self.query_one("#article-body", TextArea).text = ""
        self.mark_editor_saved("", group, "")
        self.sync_article_list_selected_class()
        self.sync_action_controls()
        if announce:
            self.set_status("[idle] select or create")

    def sync_article_list_selected_class(self) -> None:
        list_view = self.query_one("#article-list", ListView)
        selected_id = self.selected_article_id
        armed_id = self.pending_delete_id
        for item in list_view.query("ListItem"):
            if not isinstance(item, ArticleItem):
                continue
            selected = bool(selected_id and item.article.article_id == selected_id)
            armed = bool(armed_id and item.article.article_id == armed_id)
            item.set_class(selected, "is-selected")
            item.set_selected(selected, armed)

    def focus_editor(self) -> None:
        self.query_one("#editor-title", Input).focus()

    def set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def mark_editor_saved(self, title: str, group: str, body: str) -> None:
        self.loaded_title = title
        self.loaded_group = group
        self.loaded_body = body
        self.loaded_mode = self.current_mode

    def editor_is_dirty(self) -> bool:
        title = self.query_one("#editor-title", Input).value
        group = self.query_one("#editor-group", Input).value.strip() or DEFAULT_GROUP
        body = self.query_one("#article-body", TextArea).text
        return (
            title != self.loaded_title
            or group != self.loaded_group
            or body != self.loaded_body
            or self.current_mode != self.loaded_mode
        )

    @on(Input.Changed, "#editor-title")
    @on(Input.Changed, "#editor-group")
    @on(TextArea.Changed, "#article-body")
    def handle_editor_changed(self) -> None:
        # Comparing against the saved snapshot means programmatic loads (which
        # set value == snapshot) never flag as edited, so no guard is needed.
        if self.editor_is_dirty():
            self.set_status("[edited]")
        self.sync_action_controls()

    def sync_filter_controls(self) -> None:
        article_button = self.query_one("#filter-article", Static)
        quiz_button = self.query_one("#filter-quiz", Static)

        for button, label, active in (
            (article_button, "copy", self.current_filter == "article"),
            (quiz_button, "quiz", self.current_filter == "quiz"),
        ):
            button.update(f"> {label}" if active else f"  {label}")
            button.set_class(active, "-active")

    def sync_action_controls(self) -> None:
        self.query_one("#split-options").display = self.current_mode != "quiz"
        for mode, selector in (("article", "#split-sentence"), ("note", "#split-line")):
            button = self.query_one(selector, Button)
            button.label = f"> {'sentence' if mode == 'article' else 'line'}" if self.current_mode == mode else ("sentence" if mode == "article" else "line")
            button.set_class(self.current_mode == mode, "is-active")
        cancel_button = self.query_one("#action-cancel-new", Button)
        cancel_button.display = self.editing and (self.is_creating_new or self.editor_is_dirty())
        for button in ("action-new", "action-edit", "action-run", "action-delete", "action-settings", "action-reload"):
            self.query_one(f"#{button}", Button).display = not self.editing
        self.query_one("#action-save", Button).display = self.editing
        self.query_one("#action-back", Button).display = self.editing

    def show_editor(self, editing: bool) -> None:
        self.editing = editing
        self.query_one("#library-sidebar").display = not editing
        self.query_one("#editor-card").display = editing
        self.sync_action_controls()
        if editing:
            self.focus_editor()
        else:
            self.query_one("#article-list", ListView).focus()

    def allow_navigation(self) -> bool:
        if self.editor_is_dirty():
            self.set_status("[unsaved] save or discard")
            return False
        return True

    def filtered_articles(self) -> List[Article]:
        return [
            article
            for _group, articles in self.grouped_articles()
            for article in articles
        ]

    def grouped_articles(self) -> List[tuple[str, List[Article]]]:
        groups: List[str] = []
        grouped: dict[str, List[Article]] = {}
        for article in self.articles:
            if not self.matches_filter(article):
                continue
            if article.group not in grouped:
                groups.append(article.group)
                grouped[article.group] = []
            grouped[article.group].append(article)
        return [
            (group, grouped[group])
            for group in groups
        ]

    def matches_filter(self, article: Article) -> bool:
        return (article.mode == "quiz") == (self.current_filter == "quiz")

    def set_filter(self, mode: ContentMode) -> None:
        if mode == self.current_filter:
            return
        if not self.allow_navigation():
            return
        self.is_creating_new = False
        self.current_filter = "quiz" if mode == "quiz" else "article"
        self.current_mode = mode
        self.selected_article_id = None
        self.expanded_groups.clear()
        self.sync_filter_controls()
        self.sync_action_controls()
        self.refresh_article_list()

    def start_new_item(self, mode: ContentMode) -> None:
        self.is_creating_new = True
        self.previous_selected_article_id = self.selected_article_id
        self.previous_filter = self.current_filter
        self.current_mode = mode
        self.current_filter = "quiz" if mode == "quiz" else "article"
        self.selected_article_id = None
        new_title = self.store.default_note_title() if mode == "note" else ""
        new_group = DEFAULT_GROUP
        self.query_one("#editor-title", Input).value = new_title
        self.query_one("#editor-group", Input).value = new_group
        self.query_one("#editor-completion", Static).update("")
        self.query_one("#article-body", TextArea).text = ""
        self.mark_editor_saved(new_title, new_group, "")
        self.set_status("[new] edit then save")
        self.sync_filter_controls()
        self.show_editor(True)
        self.refresh_article_list()

    @on(ListView.Highlighted, "#article-list")
    def handle_highlight(self, event: ListView.Highlighted) -> None:
        # Moving through the list with the arrow keys previews each item in
        # the editor so it can be read or edited.
        # Async list rebuilds can leave a stale Highlighted event pointing at
        # an item that has already been removed.
        if event.item not in self.query_one("#article-list", ListView).children:
            return
        self.load_article_from_item(event.item)

    @on(ListView.Selected, "#article-list")
    def handle_select(self, event: ListView.Selected) -> None:
        # Enter (or click) on a list item jumps straight into practice.
        if isinstance(event.item, GroupHeader):
            self.toggle_group(event.item.group)
            return
        if not isinstance(event.item, ArticleItem):
            return
        if self.load_article_from_item(event.item):
            self.handle_start()

    def toggle_group(self, group: str) -> None:
        self.pending_highlight_group = group
        if group in self.expanded_groups:
            self.expanded_groups.remove(group)
        else:
            self.expanded_groups.add(group)
        self.refresh_article_list(announce_status=False)

    def load_article_from_item(self, item: Optional[ListItem]) -> bool:
        if not isinstance(item, ArticleItem):
            return False
        if not self.is_creating_new and self.selected_article_id == item.article.article_id:
            return True
        if not self.allow_navigation():
            return False
        self.load_article(item.article)
        return True

    @on(Click, "#filter-article")
    def handle_filter_article_pressed(self, event: Click) -> None:
        event.stop()
        self.set_filter("article")

    @on(Button.Pressed, "#split-sentence")
    @on(Button.Pressed, "#split-line")
    def handle_split_pressed(self, event: Button.Pressed) -> None:
        self.current_mode = "article" if event.button.id == "split-sentence" else "note"
        self.sync_action_controls()
        if self.editor_is_dirty():
            self.set_status("[edited]")
        elif self.is_creating_new:
            self.set_status("[new] edit then save")
        else:
            self.set_status("[ready]")

    @on(Click, "#filter-quiz")
    def handle_filter_quiz_pressed(self, event: Click) -> None:
        event.stop()
        self.set_filter("quiz")

    @on(Button.Pressed, "#action-new")
    def handle_action_new_pressed(self) -> None:
        self.handle_new()

    @on(Button.Pressed, "#action-edit")
    def handle_action_edit_pressed(self) -> None:
        self.action_edit()

    @on(Button.Pressed, "#action-back")
    def handle_action_back_pressed(self) -> None:
        self.action_close_editor()

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

    @on(Button.Pressed, "#action-reload")
    def handle_reload(self) -> None:
        if not self.allow_navigation():
            return
        try:
            self.refresh_articles_from_store(announce_status=False)
        except ValueError as error:
            self.set_status(f"[invalid] {error}")
            return
        self.set_status("[reloaded]")

    @on(Button.Pressed, "#action-cancel-new")
    def handle_action_cancel_new_pressed(self) -> None:
        self.cancel_new()

    def action_new_article(self) -> None:
        self.handle_new()

    def action_save(self) -> None:
        if self.editing:
            self.handle_save()

    def action_run(self) -> None:
        self.handle_start()

    def action_toggle_filter(self) -> None:
        if self.editing:
            self.set_status("[editing] save or back")
            return
        modes: tuple[ContentMode, ...] = ("article", "quiz")
        self.set_filter(modes[(modes.index(self.current_filter) + 1) % len(modes)])

    def action_focus_list(self) -> None:
        if not self.editing:
            self.query_one("#article-list", ListView).focus()

    def action_edit(self) -> None:
        if self.editing:
            return
        if not self.selected_article_id:
            self.set_status("[missing] select an item")
            return
        self.show_editor(True)

    def action_close_editor(self) -> None:
        if not self.editing or not self.allow_navigation():
            return
        if self.is_creating_new:
            self.cancel_new()
        else:
            self.show_editor(False)

    def action_delete(self) -> None:
        if not self.editing:
            self.handle_delete()

    def handle_new(self) -> None:
        if self.allow_navigation():
            self.start_new_item(self.current_filter)

    def cancel_new(self) -> None:
        if not self.is_creating_new:
            article = next(
                (a for a in self.articles if self.matches_filter(a) and a.article_id == self.selected_article_id), None
            )
            if article is not None:
                self.load_article(article)
            else:
                self.clear_editor()
            self.show_editor(False)
            return

        self.is_creating_new = False
        self.current_filter = self.previous_filter
        self.current_mode = self.previous_filter
        self.selected_article_id = self.previous_selected_article_id
        self.sync_filter_controls()
        self.sync_action_controls()
        self.refresh_article_list()
        self.show_editor(False)

    def open_settings(self) -> None:
        self.app.push_screen(ImportArticlesScreen(self.store))

    def handle_save(self) -> None:
        title = self.query_one("#editor-title", Input).value.strip()
        group = self.query_one("#editor-group", Input).value.strip() or DEFAULT_GROUP
        body = self.query_one("#article-body", TextArea).text.strip()

        if not body:
            self.set_status("[missing] body")
            return

        if self.current_mode in ("article", "quiz") and not title:
            self.set_status("[missing] name")
            return

        # Display-only sentence breaks must not rewrite the stored original.
        if body == self.loaded_body:
            original = next(
                (a for a in self.articles if (a.mode == "quiz") == (self.current_mode == "quiz") and a.article_id == self.selected_article_id), None
            )
            if original is not None:
                body = original.body

        target_article_id = self.selected_article_id or str(uuid4())
        store = self.quiz_store if self.current_mode == "quiz" else self.store
        selected = [a for a in self.articles if (a.mode == "quiz") == (self.current_mode == "quiz")]
        try:
            updated_articles = store.upsert_article(
                selected, title=title, body=body, mode=self.current_mode,
                group=group, article_id=target_article_id,
            )
        except ValueError as error:
            self.set_status(f"[invalid] {error}")
            return
        self.articles = [a for a in self.articles if (a.mode == "quiz") != (self.current_mode == "quiz")] + updated_articles
        self.is_creating_new = False
        self.selected_article_id = target_article_id
        saved_article = next(
            (article for article in self.articles if article.mode == self.current_mode and article.article_id == target_article_id),
            None,
        )
        if saved_article is not None:
            self.current_mode = saved_article.mode
            self.expanded_groups.add(saved_article.group)
            self.query_one("#editor-title", Input).value = saved_article.title
            self.query_one("#editor-group", Input).value = saved_article.group
            self.mark_editor_saved(
                saved_article.title,
                saved_article.group,
                saved_article.body,
            )
        self.refresh_article_list(announce_status=False)
        self.show_editor(False)
        self.set_status("[saved]")

    def handle_delete(self) -> None:
        if not self.selected_article_id:
            self.set_status("[missing] select an item")
            return

        if self.pending_delete_id != self.selected_article_id:
            self.pending_delete_id = self.selected_article_id
            self.sync_article_list_selected_class()
            self.set_status("[confirm] press Del again")
            return

        self.pending_delete_id = None
        store = self.quiz_store if self.current_filter == "quiz" else self.store
        selected = [a for a in self.articles if (a.mode == "quiz") == (self.current_filter == "quiz")]
        try:
            updated = store.delete_article(selected, self.selected_article_id)
        except ValueError as error:
            self.set_status(f"[invalid] {error}")
            return
        self.articles = [a for a in self.articles if (a.mode == "quiz") != (self.current_filter == "quiz")] + updated
        self.selected_article_id = None
        self.refresh_article_list(announce_status=False)
        self.set_status("[removed] item")

    def handle_start(self) -> None:
        if self.editing:
            self.set_status("[editing] save or back")
            return
        article = next(
            (item for item in self.articles if self.matches_filter(item) and item.article_id == self.selected_article_id),
            None,
        )
        if article is None:
            self.set_status("[missing] select an item")
            return

        if not any(extract_words(sentence) for sentence in article.sentences):
            self.set_status("[invalid] empty")
            return

        screen = QuizPracticeScreen if isinstance(article, Quiz) else PracticeScreen
        store = self.quiz_store if isinstance(article, Quiz) else self.store
        self.app.push_screen(screen(article, store, self.refresh_articles_from_store, self.sync_practice_progress))

    def sync_practice_progress(self, practiced: Article) -> None:
        for article in self.articles:
            if article.mode == practiced.mode and article.article_id == practiced.article_id:
                article.practice_sentence = practiced.practice_sentence
                article.practice_word = practiced.practice_word
                break

    def refresh_articles_from_store(self, announce_status: bool = True) -> None:
        selected_article_id = self.selected_article_id
        self.articles = self.store.load_articles() + self.quiz_store.load_articles()
        self.selected_article_id = selected_article_id
        self.refresh_article_list(announce_status=announce_status)


class WordflowApp(App[None]):
    """Main application."""

    TITLE = "Indexer"
    SUB_TITLE = "local records"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Footer {
        dock: bottom;
        background: #101113;
        color: #6a7177;
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

    #resume-prompt {
        height: 2;
        margin: 1 0;
        color: #cfd4d8;
        text-style: bold;
    }

    #practice-progress {
        height: 1;
        color: #5f666c;
        margin-bottom: 0;
    }

    #article-view {
        height: 1fr;
        margin: 0;
        border: none;
        background: #111316;
        scrollbar-background: #111316;
        scrollbar-color: #24282c;
        scrollbar-color-hover: #30363b;
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
