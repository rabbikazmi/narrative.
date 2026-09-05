from pathlib import Path


def parse_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def parse_file(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        import fitz

        try:
            with fitz.open(stream=content, filetype="pdf") as pdf:
                return "\n\n".join(page.get_text() for page in pdf).strip()
        except Exception as error:
            raise ValueError("The PDF document could not be read") from error
    if suffix in {".txt", ".md"}:
        try:
            return parse_text(content.decode("utf-8-sig"))
        except UnicodeDecodeError as error:
            raise ValueError("The text document must be UTF-8 encoded") from error
    raise ValueError("Only PDF, TXT, and MD documents are supported")
