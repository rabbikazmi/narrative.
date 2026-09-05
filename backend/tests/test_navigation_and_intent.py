import pytest

from backend.document.structure import structure_document
from backend.models.commands import CommandIntent
from backend.navigation.controller import NavigationController
from backend.navigation.state import NavigationStateStore
from backend.voice.intent import classify_intent


@pytest.mark.asyncio
async def test_navigation_transitions_and_speed():
    store = NavigationStateStore()
    await store.load_document(structure_document("x.txt", "One.\n\nTwo."))
    controller = NavigationController(store)
    await controller.apply(CommandIntent.NEXT_SECTION)
    assert (await store.read()).current_section_id == "sec_2"
    await controller.apply(CommandIntent.SLOW_DOWN)
    assert (await store.read()).playback_speed == 0.9
    await controller.apply(CommandIntent.PREVIOUS_SECTION)
    assert (await store.read()).current_section_id == "sec_1"


@pytest.mark.asyncio
async def test_repeat_restores_last_spoken_sentence():
    store = NavigationStateStore()
    await store.load_document(structure_document("x.txt", "One."))
    controller = NavigationController(store)
    await controller.mark_spoken("sec_1.sent_1")
    await controller.apply(CommandIntent.REPEAT)
    assert (await store.read()).current_sentence_id == "sec_1.sent_1"


def test_closed_set_intent_variations():
    assert classify_intent("Could you go to the next chapter?") == CommandIntent.NEXT_SECTION
    assert classify_intent("say that again") == CommandIntent.REPEAT
    assert classify_intent("make it faster") == CommandIntent.SPEED_UP
