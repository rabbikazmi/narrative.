# Document Reader frontend

## Run locally

Start the FastAPI backend from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` requests to the backend at `http://127.0.0.1:8000`.

## Playback completion

Upload, document rendering, current-sentence highlighting, playback controls, speed commands, section navigation, and Rime audio fetching are connected to the backend API. When an audio clip ends naturally, the frontend sends its sentence and request IDs to `POST /playback/complete`, receives the next playback state, and starts the next sentence automatically. Interrupted or stale audio cannot advance the document.

## Voice commands

Voice control starts automatically after a document is uploaded and remains active while the reader is open. The microphone button toggles continuous listening off or on; it does not need to be pressed for each command. When speech begins, browser playback pauses immediately while the utterance is sent to the backend. A valid command applies the returned state; ordinary speech or an unrecognized command resumes from the same audio position. Browser echo cancellation and noise suppression are requested to reduce speaker feedback. Microphone access works on localhost during development; deployed builds must use HTTPS.
