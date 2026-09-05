from pathlib import Path


def parse_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def parse_file(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        import fitz

        with fitz.open(stream=content, filetype="pdf") as pdf:
            return "\n\n".join(page.get_text() for page in pdf).strip()
    if suffix in {".txt", ".md"}:
        return parse_text(content.decode("utf-8-sig"))
    raise ValueError("Only PDF, TXT, and MD documents are supported")
