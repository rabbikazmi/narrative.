import re

from backend.document.normalizer import normalize_text
from backend.models.document import Document, Section, Sentence
from backend.utils.ids import document_id, section_id, sentence_id


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")


def structure_document(name: str, text: str) -> Document:
    """Build a deterministic document map from plain extracted text."""
    sections: list[Section] = []
    blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not blocks:
        blocks = [text.strip()] if text.strip() else []

    sections_to_build: list[tuple[str | None, str]] = []
    block_index = 0
    while block_index < len(blocks):
        block = blocks[block_index]
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if (len(lines) == 1 and not re.search(r"[.!?]$", lines[0])
                and block_index + 1 < len(blocks)):
            sections_to_build.append((lines[0], blocks[block_index + 1]))
            block_index += 2
        else:
            sections_to_build.append((None, block))
            block_index += 1

    for section_number, (block_title, raw_section) in enumerate(sections_to_build, start=1):
        lines = [line.strip() for line in raw_section.splitlines() if line.strip()]
        title = block_title or (lines[0] if len(lines) > 1 and not re.search(r"[.!?]$", lines[0]) else None)
        body = " ".join(lines[1:] if title and not block_title else lines)
        sentences = [part.strip() for part in _SENTENCE_BOUNDARY.split(body) if part.strip()]
        sections.append(Section(
            id=section_id(section_number),
            title=title,
            sentences=[Sentence(
                id=sentence_id(section_number, sentence_number),
                raw_text=sentence,
                normalized_text=normalize_text(sentence),
            ) for sentence_number, sentence in enumerate(sentences, start=1)],
        ))
    return Document(id=document_id(name), name=name, sections=sections)
