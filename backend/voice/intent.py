import re

from backend.models.commands import CommandIntent


_RULES: list[tuple[CommandIntent, tuple[str, ...]]] = [
    (CommandIntent.NEXT_SECTION, ("next section", "next chapter", "go forward")),
    (CommandIntent.PREVIOUS_SECTION, ("previous section", "previous chapter", "go back")),
    (CommandIntent.PREVIOUS_SENTENCE, ("previous sentence", "last sentence")),
    (CommandIntent.SLOW_DOWN, ("slow down", "slower", "reduce speed")),
    (CommandIntent.SPEED_UP, ("speed up", "faster", "increase speed")),
    (CommandIntent.READ_NUMBERS, ("read numbers", "read the numbers", "numbers only")),
    (CommandIntent.REPEAT, ("repeat", "say that again", "again")),
    (CommandIntent.RESUME, ("resume", "continue", "play")),
    (CommandIntent.PAUSE, ("pause", "stop reading")),
    (CommandIntent.SKIP, ("skip", "next sentence")),
]


def classify_intent(text: str) -> CommandIntent:
    normalized = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    normalized = " ".join(normalized.split())
    for intent, phrases in _RULES:
        if any(phrase in normalized for phrase in phrases):
            return intent
    raise ValueError(f"Unrecognized voice command: {text}")
