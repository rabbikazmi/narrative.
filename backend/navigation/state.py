import asyncio
from collections.abc import Callable

from backend.models.document import Document, Sentence
from backend.models.navigation import CurrentSentence, NavigationState
from backend.utils.logger import log_event


class NavigationStateStore:
    """Owns the only mutable navigation state in the application."""

    def __init__(self) -> None:
        self._state = NavigationState()
        self._document: Document | None = None
        self._lock = asyncio.Lock()

    async def load_document(self, document: Document) -> NavigationState:
        async with self._lock:
            self._document = document
            first = self._first_sentence(document)
            first_section_id = next((section.id for section in document.sections
                                     if section.sentences), None)
            self._state = NavigationState(
                document_id=document.id,
                current_section_id=first_section_id,
                current_sentence_id=first.id if first else None,
            )
            log_event("state_changed", state=self._state.model_dump())
            return self._state.model_copy(deep=True)

    async def read(self) -> NavigationState:
        async with self._lock:
            return self._state.model_copy(deep=True)

    async def mutate(self, mutation: Callable[[NavigationState, Document | None], None]) -> NavigationState:
        async with self._lock:
            mutation(self._state, self._document)
            log_event("state_changed", state=self._state.model_dump())
            return self._state.model_copy(deep=True)

    async def current_sentence(self) -> Sentence | None:
        async with self._lock:
            return self._find_sentence(self._state.current_sentence_id)

    async def sentence_by_id(self, sentence_id: str | None) -> Sentence | None:
        async with self._lock:
            return self._find_sentence(sentence_id)

    async def sentence_after(self, sentence_id: str | None) -> Sentence | None:
        async with self._lock:
            if not self._document or not sentence_id:
                return None
            sentences = [
                sentence
                for section in self._document.sections
                for sentence in section.sentences
            ]
            for index, sentence in enumerate(sentences[:-1]):
                if sentence.id == sentence_id:
                    return sentences[index + 1].model_copy(deep=True)
            return None

    async def section_context(self, sentence_id: str | None) -> tuple[int, str | None] | None:
        async with self._lock:
            if not self._document or not sentence_id:
                return None
            populated_sections = [section for section in self._document.sections if section.sentences]
            for index, section in enumerate(populated_sections, start=1):
                if any(sentence.id == sentence_id for sentence in section.sentences):
                    return index, section.title
            return None

    async def current_content(self) -> CurrentSentence | None:
        async with self._lock:
            if not self._document or not self._state.current_sentence_id:
                return None
            for section in self._document.sections:
                for sentence in section.sentences:
                    if sentence.id == self._state.current_sentence_id:
                        return CurrentSentence(
                            section_id=section.id,
                            section_title=section.title,
                            sentence_id=sentence.id,
                            raw_text=sentence.raw_text,
                            normalized_text=sentence.normalized_text,
                            navigation=self._state.model_copy(deep=True),
                        )
            return None

    async def _current_sections(self) -> list:
        return self._document.sections if self._document else []

    def _find_sentence(self, sentence_id: str | None) -> Sentence | None:
        if not self._document or not sentence_id:
            return None
        return next((
            sentence for section in self._document.sections for sentence in section.sentences
            if sentence.id == sentence_id
        ), None)

    @staticmethod
    def _first_sentence(document: Document) -> Sentence | None:
        return next((sentence for section in document.sections for sentence in section.sentences), None)
