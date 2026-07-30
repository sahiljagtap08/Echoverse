"""CLI: run a solver **agent** against one synthetic-env task, then optionally grade it.

This is the generic single-task entrypoint of the "bring your own agent" seam. It
launches an environment with :class:`harness.launcher.EnvInstance`, constructs the
chosen agent via :func:`harness.agents.get_agent`, drives it against the live URL,
captures ``final_db_state.db``, and can grade the result with the built-in LLM
judge.

The agent is selected with ``--agent`` (default: ``fara15``, the reference
implementation). Agent endpoint/model/key are passed through ``--agent-*`` flags.

Example (end to end, Fara1.5)::

    # 1. serve the model (separate shell/env with vLLM):
    CUDA_VISIBLE_DEVICES=0 bash scripts/serve_fara15.sh 9b
    # 2. run + grade one datepicker task:
    python -m harness.run_agent --agent fara15 --env datepickers --task dpg_0008 \
        --output-dir ./runs/dpg_0008 --verify
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

from .agents import AgentError, available, get_agent
from .launcher import EnvInstance
from .registry import REGISTRY, default_db_path
from .tasks import acting_user, find_task

_logger = logging.getLogger("harness.run_agent")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a solver agent against one synthetic env task."
    )
    parser.add_argument("--env", required=True, choices=sorted(REGISTRY))
    parser.add_argument("--task", required=True, help="Task id to run.")
    parser.add_argument(
        "--agent",
        default="fara15",
        help=f"Solver agent to use (default: fara15). Available: {', '.join(available())}.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Where screenshots, data_point.json and final_db_state.db are written "
        "(default: ./runs/<task>).",
    )
    parser.add_argument("--envs-root", default=None, help="Directory holding the envs.")
    # -- agent endpoint (passed to the agent factory) --
    parser.add_argument(
        "--agent-base-url",
        default=None,
        help="OpenAI-compatible base URL of the agent's model server "
        "(default: the agent's own default; for fara15: env FARA_BASE_URL).",
    )
    parser.add_argument(
        "--agent-model",
        default=None,
        help="Served model name (default: the agent's own default; "
        "for fara15: env FARA_MODEL). Switch model size here.",
    )
    parser.add_argument(
        "--agent-api-key",
        default=None,
        help="API key for the agent endpoint (default: the agent's own default).",
    )
    parser.add_argument("--max-rounds", type=int, default=100)
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Show the browser window (default: headless).",
    )
    # -- optional verification --
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Grade the result with the LLM judge after the run.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Model/deployment for the judge (default: from env, else gpt-4o).",
    )
    parser.add_argument(
        "--judge-base-url",
        default=None,
        help="OpenAI-compatible base URL / Azure endpoint for the judge (default: env).",
    )
    parser.add_argument(
        "--auth",
        default="auto",
        choices=["auto", "openai", "azure-key", "azure-ad"],
        help="Judge authentication mode (default: auto-detect).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    # Build the agent up front (fail fast on unknown agent / missing dep) before
    # launching an environment, rather than tearing down a freshly started env.
    agent_cfg = {}
    if args.agent_base_url is not None:
        agent_cfg["base_url"] = args.agent_base_url
    if args.agent_model is not None:
        agent_cfg["model"] = args.agent_model
    if args.agent_api_key is not None:
        agent_cfg["api_key"] = args.agent_api_key
    try:
        agent = get_agent(args.agent, **agent_cfg)
    except AgentError as exc:
        raise SystemExit(str(exc))

    task = find_task(args.env, args.task, args.envs_root)
    instruction = task.get("goal", task.get("question", ""))
    if not instruction:
        _logger.warning("Task %s has no 'goal'/'question' text.", args.task)
    output_dir = args.output_dir or os.path.join("./runs", args.task)
    os.makedirs(output_dir, exist_ok=True)

    # Some envs (echostay/echoforge) bind the task to a specific end user; launch
    # the env AS that user so the agent's writes land on the right rows and match
    # the task's reference/verification. Capability envs have no acting user.
    user = acting_user(task)
    extra_backend_args = {"user": user} if user is not None else None

    inst = EnvInstance(
        args.env,
        task_id=args.task,
        output_dir=output_dir,
        envs_root=args.envs_root,
        extra_backend_args=extra_backend_args,
    )
    inst.start()
    _logger.info(
        "Env '%s' up at %s; driving agent '%s'%s",
        args.env,
        inst.url,
        args.agent,
        f" (user {user})" if user is not None else "",
    )

    final_answer: Optional[str] = None
    try:
        result = asyncio.run(
            agent.drive(
                url=inst.url,
                task_id=args.task,
                instruction=instruction,
                output_dir=output_dir,
                max_rounds=args.max_rounds,
                headless=not args.headful,
            )
        )
        final_answer = result.final_answer
    finally:
        inst.close()  # captures final_db_state.db

    print(f"\nFinal answer: {final_answer}")
    print(f"Trajectory + screenshots: {output_dir}")
    if inst.final_db_path:
        print(f"Final DB captured: {inst.final_db_path}")

    if not args.verify:
        return 0

    # -- grade with the LLM judge --
    from .llm import OpenAIChatClient
    from .verify import SyntheticVerifier

    client = OpenAIChatClient(
        model=args.judge_model, base_url=args.judge_base_url, auth=args.auth
    )
    verifier = SyntheticVerifier(args.env, model_client=client)
    seed_db = default_db_path(args.env, args.envs_root)
    score, reasoning = asyncio.run(
        verifier.verify_llm(task, final_answer, seed_db, inst.final_db_path)
    )
    verdict = "PASS" if score >= 1.0 else "FAIL"
    print(f"\n{verdict}  score={score:.1f}")
    print(f"reason: {reasoning}\n")
    return 0 if score >= 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
