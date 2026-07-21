from __future__ import annotations


def progress_key(task_id: str) -> str:
    return f"simulation:progress:{task_id}"


def project_progress_key(project_id: int) -> str:
    return f"simulation:progress:{project_id}"


def cancel_key(task_id: str) -> str:
    return f"simulation:cancel:{task_id}"


def project_lock_key(project_id: int) -> str:
    return f"simulation:project:{project_id}:running"


def heavy_resource_lock_key() -> str:
    return "simulation:heavy-resource:lock"


def export_progress_key(export_task_id: int) -> str:
    return f"simulation:export:progress:{export_task_id}"
