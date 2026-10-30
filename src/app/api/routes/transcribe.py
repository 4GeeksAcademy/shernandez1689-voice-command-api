from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from src.app.schemas.voice import InstructionRequest, TranscribeFlowResponse
from src.app.services.executor import execute_instruction
from src.app.services.instruction_router import resolve_instruction
from src.app.services.transcription import strip_leading_garbage, transcribe_audio
from src.app.utils.language import normalize_transcription_language

router = APIRouter(tags=["transcribe"])


@router.get("/")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/transcribe", response_model=TranscribeFlowResponse)
async def transcribe_and_run_flow(request: Request) -> TranscribeFlowResponse:
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        # Manual fallback from the frontend: the text is already transcribed.
        try:
            transcription = InstructionRequest.model_validate(await request.json()).transcription.strip()
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expected a JSON body like {'transcription': '...'}.",
            ) from exc
    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing audio 'file' field.",
            )
        audio = await upload.read()
        if not audio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded audio file is empty.",
            )
        audio = strip_leading_garbage(audio)
        language = normalize_transcription_language(form.get("language"))
        transcription = await run_in_threadpool(
            transcribe_audio, upload.filename or "command.webm", audio, language
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Send multipart/form-data with an audio 'file' or JSON with 'transcription'.",
        )

    instruction = await run_in_threadpool(resolve_instruction, transcription)
    result = execute_instruction(instruction)
    return TranscribeFlowResponse(
        transcription=transcription,
        instruction=instruction,
        result=result,
    )
