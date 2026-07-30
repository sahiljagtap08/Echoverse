"""Reference solver agent: **Fara1.5** (the worked "bring your own agent" example).

This is the canonical implementation of the :class:`~harness.agents.base.Agent`
protocol. It drives the live environment browser with the **public**
``microsoft/fara`` package (``fara.Fara15Agent`` — imported, not vendored) against
an OpenAI-compatible endpoint serving a Fara1.5 model.

``fara`` is an **optional** dependency so the core harness (and this package's
import) stay lightweight — it is imported lazily inside :meth:`Fara15Agent.drive`.
Install it (and a Playwright browser) with::

    pip install -e "harness[fara]"       # requires Python >= 3.11 (fara uses enum.StrEnum)
    python -m playwright install chromium

You also need an OpenAI-compatible endpoint serving a Fara1.5 model (weights are
public on Hugging Face — ``microsoft/Fara1.5-4B`` / ``-9B`` / ``-27B``). The
easiest way is vLLM via ``scripts/serve_fara15.sh`` (see the harness README).

Copy this file to ``harness/agents/<your_agent>.py`` and adapt :meth:`drive` to
plug in your own solver.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from . import register
from .base import Agent, AgentError, AgentResult

_logger = logging.getLogger("harness.agents.fara15")

# Fara1.5 endpoint defaults. All three model sizes (4B/9B/27B) share the same
# runtime config; only the served weights differ. See scripts/serve_fara15.sh.
DEFAULT_BASE_URL = os.getenv("FARA_BASE_URL", "http://localhost:5002/v1/")
DEFAULT_MODEL = os.getenv("FARA_MODEL", "Fara1.5-9B")
DEFAULT_API_KEY = os.getenv("FARA_API_KEY", "not-needed")

_FARA_MISSING_MSG = (
    "The 'fara' package is required to run the Fara1.5 reference agent but is not "
    "installed. Install the optional extra and a Playwright browser:\n"
    '    pip install -e "harness[fara]"\n'
    "    python -m playwright install chromium"
)


def _import_fara():
    """Import the public fara agent lazily (keeps the core harness dep-light)."""
    try:
        from fara import (  # noqa: PLC0415 - intentional lazy import
            Fara15Agent as _Fara15Agent,
            Fara15AgentConfig,
            PlaywrightEnvironment,
            RunContext,
            Task,
        )
    except ImportError as exc:
        # fara uses enum.StrEnum (Python 3.11+). On 3.10 the package installs but
        # fails to import -- surface that clearly instead of "not installed".
        if sys.version_info < (3, 11):
            raise AgentError(
                "The 'fara' reference agent requires Python >= 3.11 "
                f"(this is {sys.version_info.major}.{sys.version_info.minor}); "
                "the public fara package uses enum.StrEnum. Recreate the "
                'environment on Python 3.11/3.12 and reinstall "harness[fara]".'
            ) from exc
        raise AgentError(_FARA_MISSING_MSG) from exc
    return _Fara15Agent, Fara15AgentConfig, PlaywrightEnvironment, RunContext, Task


def is_available() -> bool:
    """True if the optional ``fara`` package can be imported on this interpreter."""
    import importlib.util

    return sys.version_info >= (3, 11) and importlib.util.find_spec("fara") is not None


@register("fara15")
class Fara15Agent(Agent):
    """The released Fara1.5 computer-use agent as a harness :class:`Agent`.

    Construction config (endpoint/model/api key) is captured here; only per-task
    inputs are passed to :meth:`drive`.
    """

    name = "fara15"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        api_key: str = DEFAULT_API_KEY,
    ):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key

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
        (
            _Fara15Agent,
            Fara15AgentConfig,
            PlaywrightEnvironment,
            RunContext,
            Task,
        ) = _import_fara()

        env = PlaywrightEnvironment(
            viewport_width=1440,
            viewport_height=900,
            headless=headless,
            browser_channel="chromium",
            start_page=url,
            single_tab_mode=True,
            use_browserbase=False,
        )
        agent = _Fara15Agent(
            Fara15AgentConfig(
                client_config={
                    "model": self.model,
                    "base_url": self.base_url,
                    "api_key": self.api_key,
                },
                max_rounds=max_rounds,
                identity="fara_qwen35",
                critical_points="fara-1.5",
                computer_use_mode="fara_next_browser",
                save_screenshots=True,
                # Qwen3.5 hybrid-thinking backbone: force the non-thinking prefix,
                # or the model reasons in prose instead of emitting <tool_call>.
                extra_create_args={
                    "temperature": 0.0,
                    "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
                },
                # No user simulator at eval time: auto-answer ask_user_question so
                # the run doesn't wedge in WAITING_FOR_USER.
                auto_user_reply=True,
            )
        )

        task = Task(task_id=task_id, instruction=instruction)
        run_context = RunContext.create(
            environment=env,
            task=task,
            output_dir=Path(output_dir),
            run_id=task_id,
        )
        final_answer: Optional[str] = None
        actions = []
        aborted = False
        try:
            await env.initialize()
            await agent.initialize(run_context)
            final_answer, actions, _observations = await agent.run(run_context)
        except Exception as exc:  # surface as aborted; state is still graded
            aborted = True
            _logger.error("fara15 run failed for %s: %s", task_id, exc)
        finally:
            try:
                await agent.close(run_context)
            finally:
                await env.close()
        return AgentResult(
            final_answer=final_answer,
            n_actions=len(actions) if actions else 0,
            aborted=aborted,
        )
