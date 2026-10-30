import re
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError

from src.app.schemas.voice import InstructionPayload, TaskCreate, TaskReplace, TaskUpdate
from src.app.services import task_store

_TASKS_PATH = re.compile(r"^/tasks(?:/(\d+))?/?$")


def execute_instruction(instruction: InstructionPayload) -> Any:
    """Dispatch the LLM's routing decision to the matching in-memory task operation."""
    match = _TASKS_PATH.fullmatch(instruction.endpoint.strip())
    if not match:
        raise _bad_instruction(f"Unknown endpoint '{instruction.endpoint}'.")

    task_id = int(match.group(1)) if match.group(1) else None
    method = instruction.method.upper()
    params = instruction.params

    try:
        if task_id is None:
            if method == "GET":
                return task_store.list_tasks()
            if method == "POST":
                return task_store.create_task(TaskCreate.model_validate(params))
        else:
            if method == "PUT":
                return task_store.replace_task(task_id, TaskReplace.model_validate(params))
            if method == "PATCH":
                return task_store.update_task(task_id, TaskUpdate.model_validate(params))
            if method == "DELETE":
                return task_store.delete_task(task_id)
    except ValidationError as exc:
        raise _bad_instruction(f"Invalid params for {method} {instruction.endpoint}: {exc.errors()}") from exc

    raise _bad_instruction(f"Unsupported operation {method} {instruction.endpoint}.")


def _bad_instruction(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
