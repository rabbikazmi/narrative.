from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.models.commands import CommandIntent

router = APIRouter(prefix="/playback", tags=["playback"])


@router.get("/state")
async def playback_state(request: Request):
    return (await request.app.state.reader.store.read()).model_dump()


@router.get("/audio")
async def audio(request: Request):
    return StreamingResponse(request.app.state.reader.playback.audio_stream(), media_type="audio/mpeg")


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
    await reader.requests.interrupt()
    await reader.controller.apply(CommandIntent.PAUSE)
    return await playback_state(request)
