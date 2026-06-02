import json

from wordflow.storage import Article, ArticleStore


def test_upsert_note_uses_lines_and_default_timestamp_title(tmp_path):
    store = ArticleStore(tmp_path / "articles.json")

    articles = store.upsert_article([], title="", body="Alpha\nBeta", mode="note")

    assert len(articles) == 1
    assert articles[0].mode == "note"
    assert articles[0].sentences == ["Alpha", "Beta"]
    assert articles[0].title


def test_upsert_article_splits_body_into_sentences(tmp_path):
    store = ArticleStore(tmp_path / "articles.json")

    articles = store.upsert_article([], title="A", body="One. Two.", mode="article")

    assert articles[0].sentences == ["One.", "Two."]


def test_upsert_existing_article_preserves_completed_count(tmp_path):
    store = ArticleStore(tmp_path / "articles.json")
    articles = store.upsert_article([], title="A", body="One.", article_id="1")
    articles[0].completed_count = 2
    store.save_articles(articles)

    updated = store.upsert_article(articles, title="A2", body="Two.", article_id="1")

    assert len(updated) == 1
    assert updated[0].title == "A2"
    assert updated[0].completed_count == 2


def test_upsert_persists_to_disk(tmp_path):
    path = tmp_path / "articles.json"
    store = ArticleStore(path)
    store.upsert_article([], title="A", body="One.", article_id="1")

    reloaded = ArticleStore(path).load_articles()
    assert [a.title for a in reloaded] == ["A"]


def test_delete_article_removes_only_the_target(tmp_path):
    store = ArticleStore(tmp_path / "articles.json")
    articles = store.upsert_article([], title="A", body="One.", article_id="1")
    articles = store.upsert_article(articles, title="B", body="Two.", article_id="2")

    remaining = store.delete_article(articles, "1")

    assert [a.article_id for a in remaining] == ["2"]
    assert [a.article_id for a in ArticleStore(store.path).load_articles()] == ["2"]


def test_load_articles_defaults_legacy_items_to_article_mode(tmp_path):
    path = tmp_path / "articles.json"
    path.write_text(
        json.dumps(
            [
                {
                    "article_id": "1",
                    "title": "Legacy",
                    "body": "One day it rained. We stayed in!",
                }
            ]
        ),
        encoding="utf-8",
    )

    store = ArticleStore(path)
    articles = store.load_articles()

    assert len(articles) == 1
    assert articles[0].mode == "article"
    assert articles[0].sentences == ["One day it rained.", "We stayed in!"]


def test_load_articles_handles_invalid_json_gracefully(tmp_path):
    path = tmp_path / "articles.json"
    path.write_text("{bad json", encoding="utf-8")

    store = ArticleStore(path)
    articles = store.load_articles()

    assert articles == []


def test_load_articles_ignores_non_list_payload_and_bad_items(tmp_path):
    path = tmp_path / "articles.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert ArticleStore(path).load_articles() == []

    path.write_text(json.dumps(["string", 5, {"title": "ok", "body": "Hi."}]), encoding="utf-8")
    articles = ArticleStore(path).load_articles()
    assert len(articles) == 1
    assert articles[0].title == "ok"


def test_load_articles_normalizes_unknown_mode_to_article(tmp_path):
    path = tmp_path / "articles.json"
    path.write_text(
        json.dumps(
            [{"article_id": "1", "title": "X", "body": "A.\nB.", "mode": "memo"}]
        ),
        encoding="utf-8",
    )

    store = ArticleStore(path)
    articles = store.load_articles()

    assert len(articles) == 1
    assert articles[0].mode == "article"


def test_load_articles_clamps_completed_count(tmp_path):
    path = tmp_path / "articles.json"
    path.write_text(
        json.dumps(
            [
                {"article_id": "1", "title": "A", "body": "X.", "completed_count": 9},
                {"article_id": "2", "title": "B", "body": "X.", "completed_count": -4},
                {"article_id": "3", "title": "C", "body": "X.", "completed_count": "2"},
                {"article_id": "4", "title": "D", "body": "X.", "completed_count": "junk"},
            ]
        ),
        encoding="utf-8",
    )

    counts = {a.article_id: a.completed_count for a in ArticleStore(path).load_articles()}
    assert counts == {"1": 3, "2": 0, "3": 2, "4": 0}


def test_load_articles_note_without_title_gets_default(tmp_path):
    path = tmp_path / "articles.json"
    path.write_text(
        json.dumps([{"article_id": "1", "title": "", "body": "a\nb", "mode": "note"}]),
        encoding="utf-8",
    )

    article = ArticleStore(path).load_articles()[0]
    assert article.mode == "note"
    assert article.title


def test_complete_article_updates_count_and_caps_at_three(tmp_path):
    store = ArticleStore(tmp_path / "articles.json")
    articles = store.upsert_article([], title="A", body="One.", mode="article", article_id="1")
    articles[0].completed_count = 2
    store.save_articles(articles)

    completed = store.complete_article("1")
    assert completed is not None
    assert completed.completed_count == 3

    completed = store.complete_article("1")
    assert completed is not None
    assert completed.completed_count == 3


def test_complete_article_missing_id_returns_none(tmp_path):
    store = ArticleStore(tmp_path / "articles.json")
    store.upsert_article([], title="A", body="One.", article_id="1")

    assert store.complete_article("does-not-exist") is None


def test_default_storage_path_uses_env_override(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "data.json"
    monkeypatch.setenv("WORDFLOW_DATA_PATH", str(target))
    monkeypatch.delenv("SPELLLANE_DATA_PATH", raising=False)

    store = ArticleStore()
    assert store.path == target
    # constructor should create the parent directory
    assert target.parent.is_dir()


def test_save_and_load_round_trip_preserves_fields(tmp_path):
    path = tmp_path / "articles.json"
    store = ArticleStore(path)
    original = Article(
        article_id="1",
        title="Title",
        body="One. Two.",
        mode="article",
        sentences=["One.", "Two."],
        completed_count=1,
    )
    store.save_articles([original])

    loaded = ArticleStore(path).load_articles()[0]
    assert loaded == original
