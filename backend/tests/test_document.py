from backend.document.normalizer import extract_numeric_spans, normalize_text
from backend.document.parser import parse_file, parse_text
from backend.document.structure import structure_document


def test_structure_preserves_raw_and_normalized_text():
    document = structure_document("Guide.txt", "Intro\n\nRead 42 on 2026-09-05.")
    sentence = document.sections[0].sentences[0]
    assert sentence.id == "sec_1.sent_1"
    assert sentence.raw_text == "Read 42 on 2026-09-05."
    assert "forty-two" in sentence.normalized_text
    assert "September five, two thousand and twenty-six" in sentence.normalized_text


def test_number_spans_are_independent_from_normalization():
    assert extract_numeric_spans("Use 12 and 3.5.") == ["12", "3.5"]
    assert normalize_text("Use 12") == "Use twelve"


def test_text_parser_accepts_text_files():
    assert parse_text("hello\r\nworld") == "hello\nworld"
    assert parse_file("notes.txt", b"hello") == "hello"
