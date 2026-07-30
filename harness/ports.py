"""Port allocation for concurrent environment instances.

Ports are OS-assigned free ports via ``socket.bind(('', 0))`` — the lightweight
process + port model used by comparable DB-backed agent benchmarks (e.g.
AppWorld). No external service is required. This lets any number of env instances
run simultaneously, each on its own backend/frontend port pair.
"""

from __future__ import annotations

import contextlib
import socket
from typing import List, Tuple


def _find_free_port() -> int:
    """Return a currently-free TCP port assigned by the OS.

    There is an inherent (small) race between closing this socket and the child
    process binding the port. Allocating the two ports back-to-back and starting
    the servers immediately keeps the window tiny; readiness checks in the
    launcher catch the rare collision.
    """
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", 0))
        return s.getsockname()[1]


def alloc_port_pair() -> Tuple[int, int]:
    """Allocate a distinct (backend_port, frontend_port) pair."""
    backend = _find_free_port()
    frontend = _find_free_port()
    while frontend == backend:
        frontend = _find_free_port()
    return backend, frontend


class FreePortAllocator:
    """Default allocator: OS-assigned free ports, no shared state."""

    def alloc(self) -> Tuple[int, int]:
        return alloc_port_pair()

    def free(self, ports: List[int]) -> None:  # noqa: D401 - no-op for free ports
        """No-op: OS free ports need no explicit release."""
        return None


class FixedPortPool:
    """Bounded pool of pre-selected free (backend, frontend) port pairs.

    Unlike :class:`FreePortAllocator` (which asks the OS for a fresh free port on
    every call), this pool grabs ``size`` distinct pairs once and hands them out /
    takes them back via :meth:`alloc` / :meth:`free`. Each concurrency slot thus
    **reuses** the same ports across successive tasks: spin up -> run -> tear down
    (``EnvInstance.close`` calls ``free``) -> the next task reuses the pair. This
    keeps ports deterministic and avoids churn for long multi-task runs.

    Thread-safe (the orchestrator hands the same pool to worker processes only
    indirectly; within a process, concurrent slots may alloc/free concurrently).
    ``size`` should be >= the max number of concurrent env instances.
    """

    def __init__(self, size: int):
        if size < 1:
            raise ValueError("FixedPortPool size must be >= 1")
        import threading

        self._lock = threading.Lock()
        self._free: List[Tuple[int, int]] = []
        seen: set[int] = set()
        # Pre-select `size` distinct backend/frontend pairs (all distinct ports).
        while len(self._free) < size:
            b, f = alloc_port_pair()
            if b in seen or f in seen:
                continue
            seen.update((b, f))
            self._free.append((b, f))
        self._all = list(self._free)

    def alloc(self) -> Tuple[int, int]:
        with self._lock:
            if not self._free:
                # Fall back to an OS free pair if the pool is momentarily empty
                # (keeps the run going rather than blocking).
                return alloc_port_pair()
            return self._free.pop()

    def free(self, ports: List[int]) -> None:
        # ports is [backend, frontend] as passed by EnvInstance; return the pair
        # to the pool if it is one of ours.
        vals = [p for p in ports if p is not None]
        if len(vals) < 2:
            return
        pair = (vals[0], vals[1])
        with self._lock:
            if pair in self._all and pair not in self._free:
                self._free.append(pair)
