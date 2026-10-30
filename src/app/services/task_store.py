from fastapi import HTTPException, status

from src.app.schemas.voice import Task, TaskCreate, TaskReplace, TaskUpdate

# In-memory storage: resets every time the server restarts.
tasks: list[Task] = []
_next_id = 1


def list_tasks() -> list[Task]:
    return tasks


def create_task(payload: TaskCreate) -> Task:
    global _next_id
    task = Task(id=_next_id, title=payload.title, done=payload.done)
    _next_id += 1
    tasks.append(task)
    return task


def replace_task(task_id: int, payload: TaskReplace) -> Task:
    index = _find_index(task_id)
    task = Task(id=task_id, title=payload.title, done=payload.done)
    tasks[index] = task
    return task


def update_task(task_id: int, payload: TaskUpdate) -> Task:
    index = _find_index(task_id)
    changes = payload.model_dump(exclude_none=True)
    task = tasks[index].model_copy(update=changes)
    tasks[index] = task
    return task


def delete_task(task_id: int) -> dict[str, str]:
    index = _find_index(task_id)
    removed = tasks.pop(index)
    return {"message": f"Task {removed.id} '{removed.title}' deleted successfully."}


def _find_index(task_id: int) -> int:
    for index, task in enumerate(tasks):
        if task.id == task_id:
            return index
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Task {task_id} not found.",
    )
