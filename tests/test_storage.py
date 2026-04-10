import json

from wordflow.storage import ArticleStore


def test_upsert_note_uses_lines_and_default_timestamp_title(tmp_path):
    store = ArticleStore(tmp_path / "articles.json")

    articles = store.upsert_article([], title="", body="Alpha\nBeta", mode="note")

    assert len(articles) == 1
    assert articles[0].mode == "note"
    assert articles[0].sentences == ["Alpha", "Beta"]
    assert articles[0].title


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


def test_load_articles_normalizes_unknown_mode_to_article(tmp_path):
    path = tmp_path / "articles.json"
    path.write_text(
        json.dumps(
            [
                {
                    "article_id": "1",
                    "title": "X",
                    "body": "A.\nB.",
                    "mode": "memo",
                }
            ]
        ),
        encoding="utf-8",
    )

    store = ArticleStore(path)
    articles = store.load_articles()

    assert len(articles) == 1
    assert articles[0].mode == "article"
