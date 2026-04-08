"""Textual application for Wordflow."""

from __future__ import annotations

from typing import List, Optional

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static, TextArea

from .parsing import extract_words
from .storage import Article, ArticleStore


class ArticleItem(ListItem):
    """List item carrying article metadata."""

    def __init__(self, article: Article) -> None:
        self.article = article
        sentence_count = len(article.sentences)
        summary = f"{sentence_count} sentence" if sentence_count == 1 else f"{sentence_count} sentences"
        super().__init__(Label(f"$ {article.title}\n  {summary}"))


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
            yield Static(f"$ wordflow run {self.article.title}", id="practice-title")
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

        self.query_one("#practice-progress", Static).update(
            f"[session] sentence={self.sentence_index + 1}/{len(self.article.sentences)} word={self.word_index + 1}/{len(self.current_words)}"
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
                text.stylize("bold green", start, end)
            elif index == self.word_index:
                prefix_length = min(len(self.current_prefix), len(word))
                if prefix_length:
                    text.stylize("bold green", start, start + prefix_length)
                text.stylize("bold yellow", start + prefix_length, end)

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
            self.query_one("#practice-message", Static).update("[edit] completed words are locked")
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
            self.query_one("#practice-message", Static).update(f"[error] next letter -> {target[len(self.current_prefix)]}")
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

        self.query_one("#practice-progress", Static).update(
            f"[session] sentence={self.sentence_index + 1}/{len(self.article.sentences)} word={self.word_index + 1}/{len(self.current_words)}"
        )
        self.refresh_article_view()
        self.sync_input_value()
        input_widget.cursor_position = len(input_widget.value)
        self.query_one("#practice-message", Static).update("[ok] word complete")

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
        self.query_one("#practice-message", Static).update("[done] 本轮训练结束 | press Esc to return")


class LibraryScreen(Screen[None]):
    """Main library management screen."""

    BINDINGS = [
        ("ctrl+n", "new_article", "New"),
        ("ctrl+s", "save_article", "Save"),
        ("ctrl+r", "run_article", "Run"),
        ("ctrl+d", "delete_article", "Delete"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #library-root {
        height: 1fr;
    }

    #article-list {
        width: 34;
        border: solid #3a3a3a;
    }

    #editor {
        padding: 0 1;
    }

    #editor-title {
        margin-bottom: 0;
    }

    #article-body {
        height: 1fr;
        margin: 0;
        border: solid #3a3a3a;
    }

    #status {
        height: 2;
        margin-top: 0;
        color: #a0a0a0;
    }

    Input, TextArea {
        border: solid #3a3a3a;
        background: #111111;
        color: #d0d0d0;
    }

    ListView {
        background: #111111;
    }

    ListItem.--highlight {
        background: #202020;
    }

    Label {
        color: #c0c0c0;
    }
    """

    selected_article_id: reactive[Optional[str]] = reactive(None)

    def __init__(self, store: ArticleStore) -> None:
        super().__init__()
        self.store = store
        self.articles: List[Article] = self.store.load_articles()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="library-root"):
            yield ListView(id="article-list")
            with Vertical(id="editor"):
                yield Input(placeholder="$ title", id="editor-title")
                yield TextArea("", id="article-body")
                yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_article_list()
        self.focus_editor()

    def refresh_article_list(self) -> None:
        list_view = self.query_one("#article-list", ListView)
        list_view.clear()
        for article in self.articles:
            list_view.append(ArticleItem(article))

        if self.articles:
            selected_index = 0
            if self.selected_article_id:
                for index, article in enumerate(self.articles):
                    if article.article_id == self.selected_article_id:
                        selected_index = index
                        break
            list_view.index = selected_index
            self.load_article(self.articles[selected_index])
        else:
            self.clear_editor()

    def load_article(self, article: Article) -> None:
        self.selected_article_id = article.article_id
        self.query_one("#editor-title", Input).value = article.title
        self.query_one("#article-body", TextArea).text = article.body
        self.query_one("#status", Static).update(
            f"[loaded] {article.title} | sentences={len(article.sentences)}"
        )

    def clear_editor(self) -> None:
        self.selected_article_id = None
        self.query_one("#editor-title", Input).value = ""
        self.query_one("#article-body", TextArea).text = ""
        self.query_one("#status", Static).update(
            "[idle] create or select an article | ctrl+s save | ctrl+r run"
        )

    def focus_editor(self) -> None:
        self.query_one("#editor-title", Input).focus()

    @on(ListView.Selected, "#article-list")
    def handle_select(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ArticleItem):
            self.load_article(event.item.article)

    def handle_new(self) -> None:
        self.clear_editor()
        self.focus_editor()

    def action_new_article(self) -> None:
        self.handle_new()

    def handle_save(self) -> None:
        title = self.query_one("#editor-title", Input).value.strip()
        body = self.query_one("#article-body", TextArea).text.strip()

        if not title or not body:
            self.query_one("#status", Static).update("[error] title and body are required")
            return

        updated_articles = self.store.upsert_article(
            self.articles,
            title=title,
            body=body,
            article_id=self.selected_article_id,
        )
        self.articles = updated_articles
        matching = next((article for article in self.articles if article.title == title and article.body == body), None)
        self.selected_article_id = matching.article_id if matching else self.selected_article_id
        self.refresh_article_list()
        self.query_one("#status", Static).update("[ok] article saved | ctrl+r run")

    def action_save_article(self) -> None:
        self.handle_save()

    def handle_delete(self) -> None:
        if not self.selected_article_id:
            self.query_one("#status", Static).update("[error] select an article to delete")
            return

        self.articles = self.store.delete_article(self.articles, self.selected_article_id)
        self.selected_article_id = None
        self.refresh_article_list()
        self.query_one("#status", Static).update("[ok] article deleted")

    def action_delete_article(self) -> None:
        self.handle_delete()

    def handle_start(self) -> None:
        article = next((item for item in self.articles if item.article_id == self.selected_article_id), None)
        if article is None:
            self.query_one("#status", Static).update("[error] select an article first")
            return

        if not article.sentences:
            self.query_one("#status", Static).update("[error] article has no valid sentences")
            return

        self.app.push_screen(PracticeScreen(article))

    def action_run_article(self) -> None:
        self.handle_start()


class WordflowApp(App[None]):
    """Main application."""

    TITLE = "Wordflow"
    SUB_TITLE = "terminal spelling session"
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

    #practice-root {
        padding: 0 1;
        height: 1fr;
    }

    #practice-title {
        color: #8d949a;
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
