from backend.document.normalizer import extract_numeric_spans, normalize_text
from backend.document.parser import parse_file, parse_text
from backend.document.structure import structure_document


def _pdf_bytes(pages):
    import pymupdf

    document = pymupdf.open()
    for blocks in pages:
        page = document.new_page(width=612, height=792)
        for x, y, text, size, font in blocks:
            page.insert_text((x, y), text, fontsize=size, fontname=font)
    content = document.tobytes()
    document.close()
    return content


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


def test_pdf_uses_typography_for_sections_and_ignores_front_matter():
    parsed = parse_file("paper.pdf", _pdf_bytes([[
        (72, 70, "A Useful Paper", 18, "hebo"),
        (72, 105, "Ada Author", 10, "heit"),
        (72, 145, "Abstract", 12, "hebo"),
        (72, 170, "This paper presents a compact test document.", 10, "heit"),
        (72, 220, "1 Introduction", 12, "hebo"),
        (72, 245, "This is the introduction paragraph.", 10, "heit"),
        (72, 290, "1.1 Motivation", 10, "hebo"),
        (72, 315, "This is why the work matters.", 10, "heit"),
        (290, 760, "1", 9, "heit"),
    ]]))
    document = structure_document("paper.pdf", parsed)

    assert [section.title for section in document.sections] == [
        "Abstract", "1 Introduction", "1.1 Motivation",
    ]
    assert [section.level for section in document.sections] == [1, 1, 2]
    assert document.sections[2].parent_section_id == document.sections[1].id
    assert all("Ada Author" not in sentence.raw_text for section in document.sections for sentence in section.sentences)


def test_pdf_body_paragraphs_do_not_become_headings_and_pages_are_retained():
    parsed = parse_file("paper.pdf", _pdf_bytes([
        [(72, 100, "First ordinary paragraph on page one.", 10, "heit")],
        [(72, 100, "Second ordinary paragraph on page two.", 10, "heit")],
    ]))
    document = structure_document("paper.pdf", parsed)

    assert len(document.sections) == 1
    assert [sentence.page_number for sentence in document.sections[0].sentences] == [1, 2]
    assert document.sections[0].sentences[1].boundary_before == "page"


def test_markdown_heading_levels_create_parent_relationships():
    document = structure_document(
        "guide.md",
        "# Main\n\nOpening.\n\n## Detail\n\nExplanation.",
    )

    assert [section.level for section in document.sections] == [1, 2]
    assert document.sections[1].parent_section_id == document.sections[0].id


def test_heading_without_introductory_text_is_kept_as_subsection_parent():
    document = structure_document(
        "paper.md",
        "# 6 Results\n\n## 6.1 Translation\n\nThe model performs well.",
    )

    assert [section.title for section in document.sections] == ["6 Results", "6.1 Translation"]
    assert document.sections[0].sentences == []
    assert document.sections[1].parent_section_id == document.sections[0].id


def test_pdf_two_column_text_reads_left_column_before_right_column():
    parsed = parse_file("columns.pdf", _pdf_bytes([[
        (45, 80, "1 Findings", 12, "hebo"),
        (45, 120, "Left paragraph one has enough words.", 10, "heit"),
        (45, 170, "Left paragraph two continues the first column.", 10, "heit"),
        (320, 120, "Right paragraph one starts here.", 10, "heit"),
        (320, 170, "Right paragraph two completes the page.", 10, "heit"),
    ]]))

    paragraphs = [block.text for block in parsed.blocks if block.kind == "paragraph"]

    assert paragraphs == [
        "Left paragraph one has enough words.",
        "Left paragraph two continues the first column.",
        "Right paragraph one starts here.",
        "Right paragraph two completes the page.",
    ]
