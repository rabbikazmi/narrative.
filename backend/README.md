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
pip install -e ".[asr]"
pytest
uvicorn backend.main:app --reload
```

Copy `backend/.env.example` to `backend/.env`, then set the Rime credentials. Faster Whisper is loaded lazily when the first recorded command reaches `POST /command/voice`; the first use can therefore take longer while the selected model is downloaded and loaded. The CPU defaults use the `base` English model with `int8` computation. Override the `WHISPER_*` values in `backend/.env` when another device, model, or language is needed.

Supported voice commands include start, next/previous section, next/previous sentence, repeat, pause, resume, stop, slower, faster, and read numbers.
