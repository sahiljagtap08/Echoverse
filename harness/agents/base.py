"""The **agent seam**: the tiny contract every solver agent implements.

The harness is *agent-agnostic* — it launches an environment, hands the live URL
and the task instruction to an :class:`Agent`, and grades whatever database state
the agent leaves behind. Everything model-specific (which API to call, how to
drive the browser, prompt/formatting quirks) lives **inside** an agent
implementation, not in the harness core.

Bring your own agent by:

1. creating ``harness/agents/<name>.py`` with a class implementing :class:`Agent`,
2. registering it with ``@register("<name>")`` (see :mod:`harness.agents`),
3. running it via ``python -m harness.run_agent --agent <name> ...``.

See :mod:`harness.agents.fara15` for the reference implementation.
"""

from __future__ import annotations

from typing import NamedTuple, Optional, Protocol, runtime_checkable


class AgentResult(NamedTuple):
    """Outcome of driving an agent against one task.

    Attributes
    ----------
    final_answer:
        The agent's final textual answer, if any (``read`` tasks). May be ``None``
        for pure ``write`` tasks whose success is judged from the DB state change.
    n_actions:
        Number of actions the agent took (best-effort; used for reporting).
    aborted:
        ``True`` if the run ended abnormally (crash/timeout) rather than the agent
        deciding it was done. Aborted runs are still graded on captured state.
    """

    final_answer: Optional[str]
    n_actions: int = 0
    aborted: bool = False


class AgentError(RuntimeError):
    """Raised when an agent cannot run (e.g. a missing optional dependency)."""


@runtime_checkable
class Agent(Protocol):
    """Protocol every solver agent must satisfy.

    An agent is constructed with its own configuration (endpoint, model, api key,
    …) by its factory — the harness passes only *per-task* inputs to
    :meth:`drive`. Keeping construction config out of ``drive`` is what lets the
    eval core stay model-agnostic.
    """

    #: Short, stable identifier used on the CLI (``--agent <name>``).
    name: str

    async def drive(
        self,
        *,
        url: str,
        task_id: str,
        instruction: str,
        output_dir: str,
        max_rounds: int,
        headless: bool,
    ) -> AgentResult:
        """Drive the agent against a running environment.

        Parameters
        ----------
        url:
            The live environment URL to act on.
        task_id:
            The task identifier (used for run/output naming).
        instruction:
            The natural-language goal the agent must accomplish.
        output_dir:
            Directory where the agent should write its trajectory artifacts
            (screenshots, action log, ``data_point.json`` …). The launcher writes
            ``final_db_state.db`` here separately.
        max_rounds:
            Upper bound on agent steps.
        headless:
            Whether to run the browser headless.

        Returns
        -------
        AgentResult
        """
        ...
