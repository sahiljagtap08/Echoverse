"""Task-JSONL loading helpers shared by the CLI entrypoints."""

from __future__ import annotations

import ast
import os
from typing import Any, Dict, List, Optional

from . import registry
from .util import load_jsonl


def load_env_tasks(
    env_name: str, envs_root: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Load all test tasks for an env from its discovered test-task file(s)."""
    tasks: List[Dict[str, Any]] = []
    for path in registry.test_task_files(env_name, envs_root):
        if os.path.exists(path):
            tasks.extend(load_jsonl(path))
    return tasks


def find_task(
    env_name: str, task_id: str, envs_root: Optional[str] = None
) -> Dict[str, Any]:
    """Return the single task dict with ``id == task_id`` or raise."""
    for task in load_env_tasks(env_name, envs_root):
        if task.get("id") == task_id:
            return task
    raise KeyError(f"Task '{task_id}' not found in env '{env_name}'.")


def acting_user(task: Dict[str, Any]) -> Optional[str]:
    """Return the task's acting user id, or ``None`` if the task has none.

    Some envs (e.g. echostay/echoforge) bind a task to a specific end user via
    ``task["metadata"]["acting_user_id"]`` (also accepting ``user_id`` / ``user``).
    The environment must be launched **as that user** (backend ``--user <id>``) or
    the agent acts as the default user and the resulting DB change won't match the
    task's reference/verification (which targets the acting user). Capability envs
    (datepickers/nested_filter) have no acting user and return ``None``.

    ``metadata`` may be a dict or a stringified dict (as stored in some JSONL); both
    are handled.
    """
    md = task.get("metadata")
    if isinstance(md, str):
        try:
            md = ast.literal_eval(md)
        except Exception:
            md = {}
    if isinstance(md, dict):
        for key in ("acting_user_id", "user_id", "user"):
            if md.get(key) is not None:
                return str(md[key])
    return None
