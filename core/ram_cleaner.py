"""
Smart RAM Caching & Memory Release Module for JARVIS-S.

Provides instant garbage collection and Windows working set trimming to
keep JARVIS's memory footprint locked at minimal RAM (50MB-100MB).
"""
import gc
import sys
import os
import psutil

def release_unused_ram() -> dict:
    """
    Collect Python garbage and trim the process working set back to the OS.
    Call after heavy tasks, browser interactions, or speaking turns.
    """
    # 1. Force full Python garbage collection
    collected = gc.collect()

    # 2. On Windows, empty the process working set to flush unreferenced pages
    if sys.platform == "win32":
        try:
            import ctypes
            # GetCurrentProcess returns a pseudo-handle (-1)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            # EmptyWorkingSet immediately returns trimmed memory to Windows OS
            ctypes.windll.psapi.EmptyWorkingSet(handle)
        except Exception:
            pass

    # Read current RSS memory in MB
    try:
        proc = psutil.Process(os.getpid())
        rss_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        rss_mb = 0.0

    return {
        "status": "ok",
        "objects_collected": collected,
        "rss_mb": rss_mb
    }


def get_current_ram_mb() -> float:
    """Return current process Resident Set Size in MB."""
    try:
        proc = psutil.Process(os.getpid())
        return round(proc.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0
