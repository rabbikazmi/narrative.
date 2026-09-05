from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.models.commands import CommandIntent
from backend.models.navigation import PlaybackCompletionRequest

router = APIRouter(prefix="/playback", tags=["playback"])


@router.get("/state")
async def playback_state(request: Request):
    reader = request.app.state.reader
    return {
        **(await reader.store.read()).model_dump(),
        "request_id": reader.playback.request_id(),
    }


@router.get("/current")
async def current_sentence(request: Request):
    current = await request.app.state.reader.store.current_content()
    if not current:
        raise HTTPException(status_code=404, detail="No current sentence is available")
    return {
        **current.model_dump(),
        "request_id": request.app.state.reader.playback.request_id(),
    }


@router.get("/audio")
async def audio(request: Request):
    return StreamingResponse(request.app.state.reader.playback.audio_stream(), media_type="audio/wav")


@router.post("/start")
async def start(request: Request):
    await request.app.state.reader.start()
    return await playback_state(request)


@router.post("/pause")
async def pause(request: Request):
    await request.app.state.reader.command(CommandIntent.PAUSE)
    return await playback_state(request)


@router.post("/resume")
async def resume(request: Request):
    await request.app.state.reader.command(CommandIntent.RESUME)
    return await playback_state(request)


@router.post("/stop")
async def stop(request: Request):
    reader = request.app.state.reader
    await reader.stop()
    return await playback_state(request)


@router.post("/complete")
async def complete_playback(request: Request, payload: PlaybackCompletionRequest):
    try:
        await request.app.state.reader.complete_playback(
            sentence_id=payload.sentence_id,
            request_id=payload.request_id,
        )
        return await playback_state(request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
