from wordflow.parsing import extract_words, split_lines, split_sentences


def test_split_sentences_breaks_on_punctuation_and_newlines():
    text = "One day it rained. We stayed in!\nThen we cooked: soup."
    assert split_sentences(text) == [
        "One day it rained.",
        "We stayed in!",
        "Then we cooked:",
        "soup.",
    ]


def test_split_sentences_collapses_whitespace_and_trims():
    text = "  Hello   world.\t\tHow are   you?  "
    assert split_sentences(text) == ["Hello world.", "How are you?"]


def test_split_sentences_empty_or_blank_returns_empty_list():
    assert split_sentences("") == []
    assert split_sentences("   \n\t  ") == []


def test_split_sentences_without_trailing_break_keeps_single_sentence():
    assert split_sentences("no terminal punctuation here") == [
        "no terminal punctuation here"
    ]


def test_split_sentences_normalizes_carriage_returns():
    assert split_sentences("Line one.\r\nLine two.") == ["Line one.", "Line two."]


def test_split_sentences_uses_newlines_without_terminal_punctuation():
    assert split_sentences("A short heading\nFirst sentence.") == [
        "A short heading",
        "First sentence.",
    ]


def test_extract_words_keeps_apostrophes_and_hyphens():
    sentence = "Don't forget the well-known writer."
    assert extract_words(sentence) == ["Don't", "forget", "the", "well-known", "writer"]


def test_extract_words_ignores_numbers_and_punctuation():
    assert extract_words("123 !!! --- 4.5") == []
    assert extract_words("Pi is 3.14 today.") == ["Pi", "is", "today"]


def test_extract_words_empty_string():
    assert extract_words("") == []


def test_split_lines_uses_non_empty_lines_for_notes():
    text = "First note\n\nSecond note \r\n Third note"
    assert split_lines(text) == ["First note", "Second note", "Third note"]


def test_split_lines_trims_each_line_and_drops_blanks():
    text = "  alpha  \n\n   \n\t beta\t"
    assert split_lines(text) == ["alpha", "beta"]


def test_split_lines_empty_returns_empty_list():
    assert split_lines("") == []
    assert split_lines("\n\n  \n") == []
