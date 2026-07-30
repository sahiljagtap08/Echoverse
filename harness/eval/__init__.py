"""Agent-agnostic **evaluation helpers** for running solver agents over env tasks.

This package hosts the reusable pieces of the "bring your own agent" workflow:

Modules
-------
trajectory : eval/v02 on-disk layout writers (screenshots/log companion files).
batch      : batch/random-sample driver — run an agent over N tasks of one env.

The agent contract itself lives in :mod:`harness.agents`; single-task runs use
:mod:`harness.run_agent`.
"""
