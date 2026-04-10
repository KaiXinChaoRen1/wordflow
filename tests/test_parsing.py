from wordflow.parsing import extract_words, split_lines, split_sentences


def test_split_sentences_breaks_on_punctuation_and_newlines():
    text = "One day it rained. We stayed in!\nThen we cooked: soup."
    assert split_sentences(text) == [
        "One day it rained.",
        "We stayed in!",
        "Then we cooked:",
        "soup.",
    ]


def test_extract_words_keeps_apostrophes_and_hyphens():
    sentence = "Don't forget the well-known writer."
    assert extract_words(sentence) == ["Don't", "forget", "the", "well-known", "writer"]


def test_split_lines_uses_non_empty_lines_for_notes():
    text = "First note\n\nSecond note \r\n Third note"
    assert split_lines(text) == ["First note", "Second note", "Third note"]
