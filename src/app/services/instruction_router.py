import json

from fastapi import HTTPException, status
from groq import GroqError
from pydantic import ValidationError

from src.app.core.config import get_settings
from src.app.schemas.voice import InstructionPayload
from src.app.services import task_store
from src.app.services.groq_client import get_groq_client

SYSTEM_PROMPT = """You are a router for a to-do list REST API. You translate a user's spoken command \
(in any language) into exactly ONE HTTP call against the API below.

Available endpoints:
- GET    /tasks             -> list all tasks. params: {}
- POST   /tasks             -> create a task. params: {"title": string, "done": boolean (optional, default false)}
- PUT    /tasks/{task_id}   -> replace a whole task. params: {"title": string, "done": boolean} (both required)
- PATCH  /tasks/{task_id}   -> partially update a task. params: any of {"title": string, "done": boolean}
- DELETE /tasks/{task_id}   -> delete a task. params: {}

Rules:
- Respond ONLY with a JSON object, no prose, no markdown, with exactly these keys:
  {"endpoint": string, "method": "GET" | "POST" | "PUT" | "PATCH" | "DELETE", "params": object}
- For PUT, PATCH and DELETE, put the numeric task id inside the endpoint path, e.g. "/tasks/3".
- The user will usually refer to tasks by title, not by id. Use the current task list provided \
to find the id of the task that best matches what the user said.
- "params" holds only the request body fields; never put the id in params.
- Marking a task as completed/finished/done means PATCH with {"done": true}; marking it as \
pending/not done means PATCH with {"done": false}. Renaming a task means PATCH with {"title": ...}.
- Keep task titles concise and in the same language the user spoke, with the first letter capitalized.
- If the command does not clearly map to an action, return {"endpoint": "/tasks", "method": "GET", "params": {}}.
"""


def resolve_instruction(transcription: str) -> InstructionPayload:
    settings = get_settings()
    current_tasks = [task.model_dump() for task in task_store.list_tasks()]
    user_message = (
        f"Current tasks: {json.dumps(current_tasks, ensure_ascii=False)}\n"
        f"User command: {transcription}"
    )

    try:
        completion = get_groq_client().chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except GroqError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Groq request failed: {exc}",
        ) from exc

    content = completion.choices[0].message.content or ""
    try:
        instruction = InstructionPayload.model_validate_json(content)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"The LLM returned an invalid instruction: {content}",
        ) from exc

    instruction.method = instruction.method.upper()
    return instruction
