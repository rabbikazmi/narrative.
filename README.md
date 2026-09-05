# Voice-Controlled Document Reader

A modular FastAPI prototype for parsing documents, navigating sentence state, recognizing closed-set voice commands, and rendering current content through Rime TTS.

## Module responsibilities

- `backend/main.py`: application factory, dependency wiring, and route registration.
- `backend/api/`: thin HTTP endpoints for documents, commands, and playback controls.
- `backend/models/`: Pydantic contracts for documents, navigation state, commands, and API payloads.
- `backend/document/parser.py`: PDF and text extraction into source text.
- `backend/document/structure.py`: deterministic section and sentence segmentation with stable IDs.
- `backend/document/normalizer.py`: pure text normalization helpers and numeric span extraction.
- `backend/navigation/state.py`: the single source of truth for mutable navigation state.
- `backend/navigation/controller.py`: intent-to-state transitions and content selection.
- `backend/voice/asr.py`: ASR abstraction with an optional faster-whisper adapter.
- `backend/voice/intent.py`: closed-set keyword/rule-based command classifier.
- `backend/tts/rime_client.py`: asynchronous Rime HTTP client, isolated from navigation.
- `backend/tts/request_manager.py`: request generations, cancellation, and stale-response rejection.
- `backend/playback/manager.py`: local playback lifecycle and interruption/completion semantics.
- `backend/utils/`: structured logging and stable ID helpers.
- `backend/tests/`: focused unit and async behavior tests, including stale TTS rejection.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pytest
uvicorn backend.main:app --reload
```

Set `RIME_API_KEY` and, when needed, `RIME_API_URL` through the environment. The local prototype uses a deterministic in-memory audio fallback when no API key is configured.
