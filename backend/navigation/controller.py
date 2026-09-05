from backend.models.commands import CommandIntent
from backend.models.document import Document, Sentence
from backend.models.navigation import NavigationState
from backend.navigation.state import NavigationStateStore


class NavigationController:
    def __init__(self, store: NavigationStateStore) -> None:
        self.store = store

    async def apply(self, intent: CommandIntent) -> NavigationState:
        def mutation(state: NavigationState, document: Document | None) -> None:
            sections = document.sections if document else []
            current_index = next((index for index, section in enumerate(sections)
                                  if section.id == state.current_section_id), 0)
            if intent == CommandIntent.NEXT_SECTION and sections:
                section = sections[min(current_index + 1, len(sections) - 1)]
                state.current_section_id = section.id
                state.current_sentence_id = section.sentences[0].id if section.sentences else None
            elif intent == CommandIntent.PREVIOUS_SECTION and sections:
                section = sections[max(current_index - 1, 0)]
                state.current_section_id = section.id
                state.current_sentence_id = section.sentences[0].id if section.sentences else None
            elif intent == CommandIntent.SKIP:
                self._move_sentence(state, sections, 1)
            elif intent == CommandIntent.REPEAT:
                state.current_sentence_id = state.last_spoken_id or state.current_sentence_id
            elif intent == CommandIntent.SLOW_DOWN:
                state.playback_speed = max(0.5, round(state.playback_speed - 0.1, 2))
            elif intent == CommandIntent.SPEED_UP:
                state.playback_speed = min(2.0, round(state.playback_speed + 0.1, 2))
            elif intent == CommandIntent.PAUSE:
                state.is_playing = False
            elif intent == CommandIntent.RESUME:
                state.is_playing = True

        return await self.store.mutate(mutation)

    async def mark_spoken(self, sentence_id: str) -> NavigationState:
        return await self.store.mutate(lambda state, _: setattr(state, "last_spoken_id", sentence_id))

    async def set_playing(self, is_playing: bool) -> NavigationState:
        return await self.store.mutate(lambda state, _: setattr(state, "is_playing", is_playing))

    async def advance_after_completion(self, sentence_id: str) -> NavigationState:
        def mutation(state: NavigationState, document: Document | None) -> None:
            if state.current_sentence_id != sentence_id:
                return
            sections = document.sections if document else []
            self._move_sentence(state, sections, 1)
        return await self.store.mutate(mutation)

    @staticmethod
    def _move_sentence(state: NavigationState, sections: list, delta: int) -> None:
        for section_index, section in enumerate(sections):
            for sentence_index, sentence in enumerate(section.sentences):
                if sentence.id == state.current_sentence_id:
                    target_index = sentence_index + delta
                    if target_index < len(section.sentences):
                        state.current_sentence_id = section.sentences[target_index].id
                    elif section_index + 1 < len(sections):
                        next_section = sections[section_index + 1]
                        state.current_section_id = next_section.id
                        state.current_sentence_id = next_section.sentences[0].id if next_section.sentences else None
                    return
