import re
from datetime import datetime

from num2words import num2words


_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_ABBREVIATIONS = {"Dr.": "Doctor", "Mr.": "Mister", "Mrs.": "Misses", "etc.": "et cetera"}
_DOMAIN_TERMS = {"API": "A P I", "PDF": "P D F", "TTS": "text to speech", "ASR": "speech recognition"}


def extract_numeric_spans(text: str) -> list[str]:
    return [match.group(0) for match in _NUMBER.finditer(text)]


def normalize_numbers(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        try:
            number = float(value) if "." in value else int(value)
            return num2words(number)
        except (ValueError, TypeError):
            return value

    return _NUMBER.sub(replace, text)


def normalize_dates(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        try:
            value = datetime.strptime(match.group(0), "%Y-%m-%d")
            return value.strftime("%B %-d, %Y")
        except ValueError:
            return match.group(0)

    # Windows has no %-d directive, so construct the date without platform formatting.
    def windows_safe_replace(match: re.Match[str]) -> str:
        year, month, day = (int(part) for part in match.groups())
        try:
            value = datetime(year, month, day)
            return f"{value.strftime('%B')} {day}, {year}"
        except ValueError:
            return match.group(0)

    return _DATE.sub(windows_safe_replace, text)


def normalize_abbreviations(text: str) -> str:
    for abbreviation, expansion in _ABBREVIATIONS.items():
        text = text.replace(abbreviation, expansion)
    return text


def normalize_domain_terms(text: str) -> str:
    for term, expansion in _DOMAIN_TERMS.items():
        text = re.sub(rf"\b{re.escape(term)}\b", expansion, text)
    return text


def normalize_text(text: str) -> str:
    """Return TTS text while leaving the source text untouched."""
    normalized = " ".join(text.split())
    normalized = normalize_dates(normalized)
    normalized = normalize_abbreviations(normalized)
    normalized = normalize_domain_terms(normalized)
    return normalize_numbers(normalized)
