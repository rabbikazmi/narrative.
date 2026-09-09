from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.metrics import now_ms, write_event
from backend.models.commands import CommandRequest, VoiceCommandResponse
from backend.voice.intent import classify_intent

router = APIRouter(prefix="/command", tags=["commands"])


@router.post("")
async def command(request: Request, payload: CommandRequest):
    try:
        intent = classify_intent(payload.text)
        await request.app.state.reader.command(intent)
        reader = request.app.state.reader
        return {
            "intent": intent,
            "state": (await reader.store.read()).model_dump(),
            "request_id": reader.playback.request_id(),
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/voice", response_model=VoiceCommandResponse)
async def voice_command(request: Request, audio: UploadFile = File(...)):
    reader = request.app.state.reader
    recognizer = reader.recognizer
    ground_truth = request.headers.get("x-metrics-ground-truth")
    expected_section = request.headers.get("x-metrics-expected-section")
    expected_sentence = request.headers.get("x-metrics-expected-sentence")
    try:
        transcript = await recognizer.transcribe(await audio.read(), audio.filename)
        if len(transcript.split()) > 10:
            raise ValueError("No short voice command was recognized.")
        try:
            intent = classify_intent(transcript)
        except ValueError as error:
            if ground_truth:
                write_event(
                    "command_recognition",
                    command_type=None,
                    command_spoken=ground_truth,
                    transcript=transcript,
                    intent=None,
                    pass_fail="fail",
                    expected_section_id=expected_section,
                    expected_sentence_id=expected_sentence,
                    matched_at=None,
                )
            raise HTTPException(
                status_code=422,
                detail=str(error),
                headers={"X-Metrics-Attempt-Recorded": "true"} if ground_truth else None,
            ) from error
        matched_at = now_ms()
        await reader.command(intent)
        write_event(
            "command_recognition",
            command_type=intent.value,
            command_spoken=ground_truth,
            transcript=transcript,
            intent=intent.value,
            pass_fail=("pass" if ground_truth.upper() == intent.value else "fail") if ground_truth else None,
            expected_section_id=expected_section,
            expected_sentence_id=expected_sentence,
            matched_at=matched_at,
        )
        return {
            "transcript": transcript,
            "intent": intent,
            "state": (await reader.store.read()).model_dump(),
            "request_id": reader.playback.request_id(),
            "metrics_matched_at": matched_at,
            "metrics_expected_section_id": expected_section,
            "metrics_expected_sentence_id": expected_sentence,
        }
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
