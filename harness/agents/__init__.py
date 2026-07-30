"""Agent registry — discover and construct solver agents by name.

Agents self-register via the :func:`register` decorator. Built-in agents are
imported lazily at first lookup so that importing this package never pulls in an
agent's optional dependencies (e.g. ``fara``): those are only imported when the
agent is actually constructed.

Usage::

    from harness.agents import get_agent, available
    agent = get_agent("fara15", base_url=..., model=..., api_key=...)
    print(available())   # ['fara15']
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Callable, Dict, List

from .base import Agent, AgentError, AgentResult

__all__ = ["Agent", "AgentError", "AgentResult", "register", "get_agent", "available"]

_logger = logging.getLogger("harness.agents")

# name -> factory(**cfg) -> Agent
_FACTORIES: Dict[str, Callable[..., Agent]] = {}

# Built-in agents importable on demand: name -> module to import (which registers it).
_BUILTINS: Dict[str, str] = {
    "fara15": "harness.agents.fara15",
}

# Submodules that are not agents (never auto-imported as candidates).
_NON_AGENT_MODULES = {"base"}

_discovered = False


def register(name: str) -> Callable[[Callable[..., Agent]], Callable[..., Agent]]:
    """Class/function decorator registering an agent factory under ``name``.

    The decorated object is called as ``factory(**cfg)`` and must return an
    object satisfying the :class:`~harness.agents.base.Agent` protocol.
    """

    def _decorator(factory: Callable[..., Agent]) -> Callable[..., Agent]:
        _FACTORIES[name] = factory
        return factory

    return _decorator


def _ensure_loaded(name: str) -> None:
    """Import whatever registers ``name`` (built-in fast-path, else discovery)."""
    if name in _FACTORIES:
        return
    module = _BUILTINS.get(name)
    if module:
        __import__(module)
        return
    # Not a built-in — a user may have dropped harness/agents/<name>.py.
    _discover()


def _discover() -> None:
    """Import every ``harness/agents/<name>.py`` so its ``@register`` runs.

    Lets users add an agent just by dropping a module into this package (no need to
    touch ``_BUILTINS``). Import errors (e.g. an agent's optional dependency) are
    logged and skipped so one broken agent never hides the others. Runs once.
    """
    global _discovered
    if _discovered:
        return
    _discovered = True
    for info in pkgutil.iter_modules(__path__):
        if info.name in _NON_AGENT_MODULES:
            continue
        try:
            importlib.import_module(f"{__name__}.{info.name}")
        except Exception as exc:  # pragma: no cover - defensive
            _logger.debug("skipping agent module '%s': %s", info.name, exc)


def available() -> List[str]:
    """Return the sorted names of all registerable agents (built-ins + discovered)."""
    _discover()
    return sorted(set(_FACTORIES) | set(_BUILTINS))


def get_agent(name: str, **cfg) -> Agent:
    """Construct the agent registered under ``name`` with the given config.

    Raises
    ------
    AgentError
        If ``name`` is unknown.
    """
    _ensure_loaded(name)
    factory = _FACTORIES.get(name)
    if factory is None:
        raise AgentError(
            f"Unknown agent '{name}'. Available agents: {', '.join(available())}. "
            "Add your own as harness/agents/<name>.py: implement the Agent protocol "
            "and decorate it with @register('<name>') (see harness.agents.fara15)."
        )
    return factory(**cfg)
