import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+){0,4})\s+(.+)$")
_SPECIAL_HEADINGS = {
    "abstract", "acknowledgement", "acknowledgements", "acknowledgment",
    "acknowledgments", "appendix", "conclusion", "conclusions", "references",
}
_CAPTION = re.compile(r"^(?:figure|fig\.|table|algorithm)\s+\d+", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^\s*((?:[-*+]|•)|(?:\d+[.)]))\s+(.+)$")


@dataclass(frozen=True)
class ParsedPdfBlock:
    page_number: int
    kind: str
    text: str
    heading_level: int | None = None
    list_marker: str | None = None


@dataclass(frozen=True)
class ParsedPdfDocument:
    blocks: tuple[ParsedPdfBlock, ...]


@dataclass(frozen=True)
class _PdfCandidate:
    page_number: int
    page_width: float
    page_height: float
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    font_size: float
    bold_ratio: float


def parse_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _clean_line(text: str) -> str:
    return " ".join(
        text.replace("\u00ad", "").replace("ﬁ", "fi").replace("ﬂ", "fl").split()
    )


def _join_lines(lines: list[str]) -> str:
    result = ""
    for raw_line in lines:
        line = _clean_line(raw_line)
        if not line:
            continue
        if result.endswith("-") and line[:1].islower():
            result = result[:-1] + line
        else:
            result = f"{result} {line}".strip()
    return result


def _extract_candidates(pdf) -> list[_PdfCandidate]:
    candidates: list[_PdfCandidate] = []
    for page_number, page in enumerate(pdf, start=1):
        page_dict = page.get_text("dict", sort=False)
        width, height = float(page.rect.width), float(page.rect.height)
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            lines = block.get("lines", [])
            text = _join_lines([
                "".join(span.get("text", "") for span in line.get("spans", []))
                for line in lines
            ])
            if not text:
                continue
            spans = [span for line in lines for span in line.get("spans", []) if span.get("text", "").strip()]
            if not spans:
                continue
            weights = [max(len(span.get("text", "").strip()), 1) for span in spans]
            total_weight = sum(weights)
            font_size = sum(float(span.get("size", 0)) * weight for span, weight in zip(spans, weights)) / total_weight
            bold_weight = sum(
                weight for span, weight in zip(spans, weights)
                if "bold" in span.get("font", "").lower() or "medi" in span.get("font", "").lower()
            )
            x0, y0, x1, y1 = (float(value) for value in block.get("bbox", (0, 0, 0, 0)))
            candidates.append(_PdfCandidate(
                page_number, width, height, x0, y0, x1, y1, text,
                font_size, bold_weight / total_weight,
            ))
    return candidates


def _body_font_size(candidates: list[_PdfCandidate]) -> float:
    sizes: Counter[float] = Counter()
    for block in candidates:
        if len(block.text) >= 35 and block.y0 < block.page_height * 0.92:
            sizes[round(block.font_size * 2) / 2] += len(block.text)
    return sizes.most_common(1)[0][0] if sizes else 10.0


def _margin_key(block: _PdfCandidate) -> str:
    return re.sub(r"\d+", "#", block.text.casefold()).strip()


def _without_headers_and_footers(candidates: list[_PdfCandidate]) -> list[_PdfCandidate]:
    page_count = max((block.page_number for block in candidates), default=1)
    margin_counts = Counter(
        _margin_key(block)
        for block in candidates
        if block.y1 < block.page_height * 0.09 or block.y0 > block.page_height * 0.91
    )
    repeated = {
        key for key, count in margin_counts.items()
        if page_count > 1 and count >= 2
    }
    cleaned: list[_PdfCandidate] = []
    for block in candidates:
        is_page_number = block.y0 > block.page_height * 0.88 and bool(re.fullmatch(r"\d{1,4}", block.text))
        in_margin = block.y1 < block.page_height * 0.09 or block.y0 > block.page_height * 0.91
        if is_page_number or (in_margin and _margin_key(block) in repeated):
            continue
        cleaned.append(block)
    return cleaned


def _reading_order(page_blocks: list[_PdfCandidate]) -> list[_PdfCandidate]:
    """Order ordinary pages top-down and detected two-column regions left-before-right."""
    if not page_blocks:
        return []
    width = page_blocks[0].page_width
    narrow = [block for block in page_blocks if block.x1 - block.x0 < width * 0.56]
    left = [block for block in narrow if block.x1 <= width * 0.55]
    right = [block for block in narrow if block.x0 >= width * 0.45]
    if len(left) < 2 or len(right) < 2:
        return sorted(page_blocks, key=lambda block: (round(block.y0, 1), block.x0))

    column_blocks = [*left, *right]
    spanning = sorted(
        [block for block in page_blocks if block not in column_blocks],
        key=lambda block: (block.y0, block.x0),
    )
    ordered: list[_PdfCandidate] = []
    lower_bound = float("-inf")
    for separator in [*spanning, None]:
        upper_bound = separator.y0 if separator else float("inf")
        region = [block for block in column_blocks if lower_bound <= block.y0 < upper_bound]
        ordered.extend(sorted((block for block in region if block.x1 <= width * 0.55), key=lambda block: block.y0))
        ordered.extend(sorted((block for block in region if block.x0 >= width * 0.45), key=lambda block: block.y0))
        if separator:
            ordered.append(separator)
            lower_bound = separator.y1
    return ordered


def _heading_level(block: _PdfCandidate, body_size: float, is_title: bool) -> int | None:
    text = block.text.strip()
    if _CAPTION.match(text) or len(text) > 160 or text.endswith((".", ":", ";", ",")):
        return None
    if is_title:
        return 1
    numbered = _NUMBERED_HEADING.match(text)
    if numbered and (block.bold_ratio >= 0.45 or block.font_size >= body_size + 1):
        return min(numbered.group(1).count(".") + 1, 6)
    if text.casefold() in _SPECIAL_HEADINGS and (block.bold_ratio >= 0.45 or block.font_size >= body_size + 1):
        return 1
    return None


def _parse_pdf(content: bytes) -> ParsedPdfDocument:
    import pymupdf

    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            candidates = _without_headers_and_footers(_extract_candidates(pdf))
    except Exception as error:
        raise ValueError("The PDF document could not be read") from error

    body_size = _body_font_size(candidates)
    first_page = [block for block in candidates if block.page_number == 1]
    title = max(
        (block for block in first_page if block.y0 < block.page_height * 0.48),
        key=lambda block: block.font_size,
        default=None,
    )
    title = title if title and title.font_size >= body_size + 2.5 else None
    abstract = next((block for block in first_page if block.text.casefold() == "abstract"), None)

    readable_candidates = [
        block for block in candidates
        if not (title and abstract and block.page_number == 1 and title.y1 < block.y0 < abstract.y0)
        and not (block.page_number == 1 and block.y0 > block.page_height * 0.72 and block.font_size <= body_size - 0.75)
    ]
    ordered: list[_PdfCandidate] = []
    for page_number in sorted({block.page_number for block in readable_candidates}):
        ordered.extend(_reading_order([block for block in readable_candidates if block.page_number == page_number]))

    result: list[ParsedPdfBlock] = []
    for block in ordered:
        if block is title:
            continue
        level = _heading_level(block, body_size, block is title)
        if level is not None:
            result.append(ParsedPdfBlock(block.page_number, "heading", block.text, heading_level=level))
            continue
        list_match = _LIST_ITEM.match(block.text)
        if list_match:
            result.append(ParsedPdfBlock(
                block.page_number, "list_item", list_match.group(2).strip(), list_marker=list_match.group(1),
            ))
        else:
            result.append(ParsedPdfBlock(block.page_number, "paragraph", block.text))

    merged: list[ParsedPdfBlock] = []
    for block in result:
        previous = merged[-1] if merged else None
        continuation = (
            previous is not None
            and previous.kind == block.kind == "paragraph"
            and previous.page_number != block.page_number
            and (previous.text.endswith("-") or (
                not re.search(r"[.!?;:]$", previous.text) and block.text[:1].islower()
            ))
        )
        if continuation:
            joiner = "" if previous.text.endswith("-") else " "
            merged[-1] = ParsedPdfBlock(
                previous.page_number, "paragraph", previous.text.rstrip("-") + joiner + block.text,
            )
        else:
            merged.append(block)
    return ParsedPdfDocument(tuple(merged))


def parse_file(filename: str, content: bytes) -> str | ParsedPdfDocument:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(content)
    if suffix in {".txt", ".md"}:
        try:
            return parse_text(content.decode("utf-8-sig"))
        except UnicodeDecodeError as error:
            raise ValueError("The text document must be UTF-8 encoded") from error
    raise ValueError("Only PDF, TXT, and MD documents are supported")
