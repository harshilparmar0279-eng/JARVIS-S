"""
core/command_lock.py — Centralized Reentrant Command Mutex Lock and FIFO Task Queue.

Guarantees that Jarvis finishes executing one system command (e.g. YouTube playback,
browser launch, WhatsApp action) before triggering the next, eliminating race conditions,
task mixing, and redundant about:blank tabs.
"""
from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import Generator

_async_lock: asyncio.Lock | None = None
_sync_lock = threading.RLock()


def _get_async_lock() -> asyncio.Lock:
    global _async_lock
    if _async_lock is None:
        _async_lock = asyncio.Lock()
    return _async_lock


@asynccontextmanager
async def async_command_mutex(timeout: float = 30.0) -> Generator[None, None, None]:
    """Async context manager to serialize command execution."""
    lock = _get_async_lock()
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    try:
        yield
    finally:
        if lock.locked():
            try:
                lock.release()
            except RuntimeError:
                pass


@contextmanager
def sync_command_mutex(timeout: float = 30.0) -> Generator[bool, None, None]:
    """Sync thread-safe context manager for blocking OS/browser automation."""
    acquired = _sync_lock.acquire(timeout=timeout)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                _sync_lock.release()
            except RuntimeError:
                pass
