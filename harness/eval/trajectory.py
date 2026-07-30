"""Trajectory writers for the **eval/v02** on-disk layout (agent-agnostic).

These helpers synthesize the webeval-style companion files that surround an
agent run, so every per-task directory has the same shape regardless of which
solver produced it::

    <task>/
        data_point.json          # written by the agent (eval/v02 trajectory)
        <task>_final_answer.json # synthesized here (webeval FinalAnswer shape)
        web_surfer.log           # synthesized here (from data_point actions)
        core.log                 # synthesized here (high-level run log)
        times.json               # synthesized here (start/end/duration)
        baseline_db_state.db     # snapshot taken right after env init
        final_db_state.db        # captured by EnvInstance on close

They were previously private helpers inside the Fara batch runner; they contain
no model-specific logic (the only agent-dependent detail — the ``source`` label
in ``web_surfer.log`` — is a parameter).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

__all__ = [
    "post_screenshots",
    "write_final_answer",
    "write_web_surfer_log",
    "write_times",
    "write_core_log",
    "count_actions",
]

_POST_RE = re.compile(r"^screenshot_(\d+)_post\.png$")


def post_screenshots(traj_dir: str) -> List[str]:
    """Return ``screenshot_<n>_post.png`` filenames in numeric order."""
    files = [f for f in os.listdir(traj_dir) if _POST_RE.match(f)]
    files.sort(key=lambda x: int(_POST_RE.match(x).group(1)))
    return files


def write_final_answer(
    traj_dir: str, task_id: str, final_answer: Optional[str], aborted: bool
) -> None:
    payload = {
        "final_answer": final_answer if final_answer is not None else "<no_answer>",
        "env_state_json": "<no_answer>",
        "env_state_raw": "<no_answer>",
        "screenshots": post_screenshots(traj_dir),
        "is_aborted": bool(aborted),
        "is_rel_paths": True,
        "token_usage": {},
    }
    with open(os.path.join(traj_dir, f"{task_id}_final_answer.json"), "w") as f:
        json.dump(payload, f, indent=4)


def write_web_surfer_log(traj_dir: str, source: str = "Agent") -> None:
    """Derive ``web_surfer.log`` (one JSON object per line) from data_point.json.

    Each agent action becomes a line ``{source, url, action, arguments}`` where
    arguments carry the tool call plus the model's thoughts/reasoning.

    Parameters
    ----------
    source:
        The ``source`` label to stamp on each line (e.g. the agent class name).
    """
    dp_path = os.path.join(traj_dir, "data_point.json")
    if not os.path.exists(dp_path):
        return
    with open(dp_path) as f:
        dp = json.load(f)
    events = dp.get("solver_log", {}).get("events", [])
    lines: List[str] = []
    for ev in events:
        if ev.get("type") != "action":
            continue
        raw = ""
        msgs = ev.get("llm_conversation", {}).get("messages", [])
        if msgs:
            raw = msgs[-1].get("raw_response", "") or ""
        thoughts = raw.split("<tool_call>")[0].strip() if raw else ""
        args: Dict[str, Any] = {}
        name = ev.get("action_name", "")
        content = ev.get("content") or {}
        if isinstance(content, dict):
            # content is the tool call: {"name": "computer_use", "arguments": {...}}
            name = content.get("name", name)
            args = dict(content.get("arguments", {}) or {})
        args.setdefault("thoughts", thoughts)
        args.setdefault("reasoning", thoughts)
        lines.append(
            json.dumps(
                {
                    "source": source,
                    "url": "",
                    "action": name,
                    "arguments": args,
                }
            )
        )
    with open(os.path.join(traj_dir, "web_surfer.log"), "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def write_times(traj_dir: str, start: float, end: float) -> None:
    with open(os.path.join(traj_dir, "times.json"), "w") as f:
        json.dump({"start_time": start, "end_time": end, "duration": end - start}, f)


def write_core_log(
    traj_dir: str,
    task_id: str,
    url: str,
    final_db_path: Optional[str],
    start: float,
    end: float,
    n_actions: int,
) -> None:
    def ts(t: float) -> str:
        return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]

    lines = [
        f"{ts(start)} [INFO] harness.core.{task_id} - [Execution {task_id}] Start",
        f"{ts(start)} [INFO] harness.core.{task_id} - "
        f"Backend/Frontend launched; agent driving {url}",
        f"{ts(start)} [INFO] harness.core.{task_id} - "
        f"Snapshotted post-init baseline DB to baseline_db_state.db",
        f"{ts(end)} [INFO] harness.core.{task_id} - "
        f"Agent finished after {n_actions} actions",
        f"{ts(end)} [INFO] harness.core.{task_id} - "
        f"Captured final DB to {final_db_path}",
        f"{ts(end)} [INFO] harness.core.{task_id} - "
        f"[Execution {task_id}] Completed (duration={end - start:.2f}s)",
    ]
    with open(os.path.join(traj_dir, "core.log"), "w") as f:
        f.write("\n".join(lines) + "\n")


def count_actions(traj_dir: str) -> int:
    dp_path = os.path.join(traj_dir, "data_point.json")
    if not os.path.exists(dp_path):
        return 0
    with open(dp_path) as f:
        dp = json.load(f)
    return sum(
        1
        for ev in dp.get("solver_log", {}).get("events", [])
        if ev.get("type") == "action"
    )
