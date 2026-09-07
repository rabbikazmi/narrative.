import re
from dataclasses import dataclass

from backend.document.normalizer import normalize_text
from backend.models.document import Document, Section, Sentence
from backend.utils.ids import document_id, section_id, sentence_id


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$")
_LIST_ITEM = re.compile(r"^\s*((?:[-*+]|•)|(?:\d+[.)]))\s+(.+)$")


@dataclass(frozen=True)
class _Block:
    page_number: int
    kind: str
    text: str
    list_marker: str | None = None


def _looks_like_heading(line: str) -> bool:
    return (
        0 < len(line) <= 120
        and not _LIST_ITEM.match(line)
        and not re.search(r"[.!?;:]$", line)
    )


def _content_blocks(lines: list[str], page_number: int) -> list[_Block]:
    """Join visual line wraps while retaining individual list items."""
    blocks: list[_Block] = []
    paragraph: list[str] = []
    active_list: tuple[str, list[str]] | None = None

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(_Block(page_number, "paragraph", " ".join(paragraph)))
            paragraph.clear()

    def flush_list() -> None:
        nonlocal active_list
        if active_list:
            marker, parts = active_list
            blocks.append(_Block(page_number, "list_item", " ".join(parts), marker))
            active_list = None

    for line in lines:
        match = _LIST_ITEM.match(line)
        if match:
            flush_paragraph()
            flush_list()
            active_list = (match.group(1), [match.group(2).strip()])
        elif active_list:
            active_list[1].append(line)
        else:
            paragraph.append(line)

    flush_paragraph()
    flush_list()
    return blocks


def _parse_blocks(text: str) -> list[_Block]:
    blocks: list[_Block] = []
    for page_number, page in enumerate(text.split("\f"), start=1):
        chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", page) if chunk.strip()]
        for chunk in chunks:
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not lines:
                continue

            markdown_heading = _MARKDOWN_HEADING.match(lines[0])
            if markdown_heading:
                blocks.append(_Block(page_number, "heading", markdown_heading.group(1).strip()))
                blocks.extend(_content_blocks(lines[1:], page_number))
            elif _looks_like_heading(lines[0]) and (len(lines) > 1 or len(chunks) > 1):
                blocks.append(_Block(page_number, "heading", lines[0]))
                blocks.extend(_content_blocks(lines[1:], page_number))
            else:
                blocks.extend(_content_blocks(lines, page_number))
    return blocks


def structure_document(name: str, text: str) -> Document:
    """Build a deterministic map while retaining boundaries needed for narration."""
    sections: list[Section] = []
    title: str | None = None
    pending_blocks: list[_Block] = []

    def flush_section() -> None:
        nonlocal title, pending_blocks
        if not pending_blocks:
            return

        section_number = len(sections) + 1
        built_sentences: list[Sentence] = []
        previous_page: int | None = None
        for block_number, block in enumerate(pending_blocks, start=1):
            parts = [part.strip() for part in _SENTENCE_BOUNDARY.split(block.text) if part.strip()]
            for position, raw_sentence in enumerate(parts, start=1):
                if not built_sentences:
                    boundary = "section"
                elif position > 1:
                    boundary = "sentence"
                elif previous_page != block.page_number:
                    boundary = "page"
                elif block.kind == "list_item":
                    boundary = "list_item"
                else:
                    boundary = "paragraph"

                sentence_number = len(built_sentences) + 1
                built_sentences.append(Sentence(
                    id=sentence_id(section_number, sentence_number),
                    raw_text=raw_sentence,
                    normalized_text=normalize_text(raw_sentence),
                    block_id=f"sec_{section_number}.block_{block_number}",
                    block_type=block.kind,
                    boundary_before=boundary,
                    page_number=block.page_number,
                    position_in_block=position,
                    list_marker=block.list_marker,
                ))
                previous_page = block.page_number

        if built_sentences:
            sections.append(Section(
                id=section_id(section_number),
                title=title,
                sentences=built_sentences,
            ))
        title = None
        pending_blocks = []

    for block in _parse_blocks(text):
        if block.kind == "heading":
            flush_section()
            title = block.text
        else:
            pending_blocks.append(block)
    flush_section()

    return Document(id=document_id(name), name=name, sections=sections)
