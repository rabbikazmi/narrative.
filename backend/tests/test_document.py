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


def test_structure_preserves_paragraph_and_list_boundaries():
    document = structure_document(
        "guide.md",
        "# Getting started\n\nFirst sentence. Second sentence.\n\n"
        "- Upload a document\n- Press play\n\nFinal paragraph.",
    )

    section = document.sections[0]
    assert section.title == "Getting started"
    assert [sentence.boundary_before for sentence in section.sentences] == [
        "section", "sentence", "list_item", "list_item", "paragraph",
    ]
    assert section.sentences[2].block_type == "list_item"
    assert section.sentences[2].list_marker == "-"
    assert section.sentences[2].block_id != section.sentences[3].block_id


def test_structure_retains_page_transitions():
    document = structure_document(
        "pages.pdf",
        "First page sentence.\fSecond page sentence.",
    )

    first, second = document.sections[0].sentences
    assert first.page_number == 1
    assert second.page_number == 2
    assert second.boundary_before == "page"


def test_paragraphs_do_not_become_false_sections():
    document = structure_document(
        "essay.txt",
        "First paragraph.\n\nSecond paragraph.",
    )

    assert len(document.sections) == 1
    assert [sentence.boundary_before for sentence in document.sections[0].sentences] == [
        "section", "paragraph",
    ]
