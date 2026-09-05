import re

from backend.document.normalizer import normalize_text
from backend.models.document import Document, Section, Sentence
from backend.utils.ids import document_id, section_id, sentence_id


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")


def structure_document(name: str, text: str) -> Document:
    """Build a deterministic document map from plain extracted text."""
    sections: list[Section] = []
    raw_sections = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not raw_sections:
        raw_sections = [text.strip()] if text.strip() else []

    for section_number, raw_section in enumerate(raw_sections, start=1):
        lines = [line.strip() for line in raw_section.splitlines() if line.strip()]
        title = lines[0] if len(lines) > 1 and not re.search(r"[.!?]$", lines[0]) else None
        body = " ".join(lines[1:] if title else lines)
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
