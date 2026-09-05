import re


def document_id(name: str) -> str:
    """Create a stable identifier from a document name."""
    value = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return value or "document"


def section_id(index: int) -> str:
    return f"sec_{index}"


def sentence_id(section_index: int, sentence_index: int) -> str:
    return f"sec_{section_index}.sent_{sentence_index}"
