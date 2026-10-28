"""
Zero-Freeze Task Execution Module (Parallel Threading) for JARVIS-S.

Executes automatic tasks (e.g. browser launch, WhatsApp desktop automation,
file search, system commands) asynchronously in dedicated daemon background
threads so the UI, visualizer, audio loop, and main thread NEVER freeze.
"""
import threading
import logging
from typing import Callable, Any
from core.ram_cleaner import release_unused_ram

logger = logging.getLogger("TaskRunner")


def run_task_in_background(task_function: Callable, *args: Any, **kwargs: Any) -> threading.Thread:
    """
    Execute task_function in a background daemon thread.
    Prevents blocking or freezing the main user loop, HUD visualizer, or Qt UI.
    Automatically triggers memory cleanup (release_unused_ram) when finished.
    """
    def _worker():
        try:
            task_function(*args, **kwargs)
        except Exception as e:
            logger.error(f"[TaskRunner] Background task {task_function.__name__} error: {e}", exc_info=True)
            print(f"[TaskRunner] ⚠️ Error in background task {getattr(task_function, '__name__', 'anon')}: {e}")
        finally:
            # Smart RAM release immediately after task completes
            try:
                release_unused_ram()
            except Exception:
                pass

    task_name = f"BgTask-{getattr(task_function, '__name__', 'worker')}"
    task_thread = threading.Thread(target=_worker, daemon=True, name=task_name)
    task_thread.start()
    return task_thread
