from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.models.commands import CommandRequest
from backend.voice.intent import classify_intent

router = APIRouter(prefix="/command", tags=["commands"])


@router.post("")
async def command(request: Request, payload: CommandRequest):
    try:
        intent = classify_intent(payload.text)
        await request.app.state.reader.command(intent)
        return {"intent": intent, "state": (await request.app.state.reader.store.read()).model_dump()}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/voice")
async def voice_command(request: Request, audio: UploadFile = File(...)):
    recognizer = request.app.state.reader.recognizer
    transcript = await recognizer.transcribe(await audio.read())
    intent = classify_intent(transcript)
    await request.app.state.reader.command(intent)
    return {"transcript": transcript, "intent": intent}
