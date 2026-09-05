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

## Current integration boundary

Upload, document rendering, current-sentence highlighting, playback controls, speed commands, section navigation, and Rime audio fetching are connected to the current backend API. Automatic continuous reading remains dependent on replacing the backend's simulated completion with a client-confirmed completion endpoint.
