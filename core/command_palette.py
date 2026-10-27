"""
core/command_palette.py — Command discovery, fuzzy/substring filtering, MRU tracking, and safe dispatch.

Maintains session-only most-recently-used (MRU) commands, exposes system controls,
panels, resource profiles, registered actions, and enabled plugins.
Preserves safety confirmation gates and permission checks.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_MRU_COUNT = 8


@dataclass
class CommandItem:
    id: str
    title: str
    description: str = ""
    category: str = "SYSTEM"  # "SYSTEM" | "VIEW" | "PROFILE" | "ACTION" | "PLUGIN" | "RECENT"
    shortcut: str = ""
    handler: Optional[Callable[[], str | None]] = None
    is_available: bool = True
    unavailable_reason: str = ""
    action_name: Optional[str] = None
    plugin_name: Optional[str] = None
    requires_params: bool = False
    param_names: list[str] = field(default_factory=list)


class CommandPaletteRegistry:
    """Session-only command registry with search, MRU tracking, and safe execution."""

    def __init__(self, notify_log: Optional[Callable[[str], None]] = None):
        self._commands: dict[str, CommandItem] = {}
        self._mru_ids: collections.deque[str] = collections.deque(maxlen=MAX_MRU_COUNT)
        self._notify_log = notify_log or (lambda msg: None)

    def register(self, item: CommandItem):
        self._commands[item.id] = item

    def unregister(self, item_id: str):
        self._commands.pop(item_id, None)

    def clear(self):
        self._commands.clear()

    def get(self, item_id: str) -> Optional[CommandItem]:
        return self._commands.get(item_id)

    def record_mru(self, item_id: str):
        """Record command execution into session-only MRU. Does not persist to disk."""
        if item_id in self._commands:
            if item_id in self._mru_ids:
                self._mru_ids.remove(item_id)
            self._mru_ids.appendleft(item_id)

    def get_mru_items(self) -> list[CommandItem]:
        items = []
        for cid in self._mru_ids:
            cmd = self._commands.get(cid)
            if cmd:
                # Create a shallow copy marked as RECENT category
                recent_item = CommandItem(
                    id=cmd.id,
                    title=cmd.title,
                    description=cmd.description,
                    category="RECENT",
                    shortcut=cmd.shortcut,
                    handler=cmd.handler,
                    is_available=cmd.is_available,
                    unavailable_reason=cmd.unavailable_reason,
                    action_name=cmd.action_name,
                    plugin_name=cmd.plugin_name,
                    requires_params=cmd.requires_params,
                    param_names=cmd.param_names,
                )
                items.append(recent_item)
        return items

    def filter_commands(self, query: str = "") -> list[CommandItem]:
        """
        Filter commands by partial, case-insensitive match on title, description,
        category, and shortcut.
        When query is empty, returns MRU items followed by all registered commands.
        """
        clean_q = str(query or "").strip().lower()

        if not clean_q:
            recent = self.get_mru_items()
            recent_ids = {r.id for r in recent}
            rest = [c for c in self._commands.values() if c.id not in recent_ids]
            # Sort rest by category and title
            rest.sort(key=lambda x: (x.category, x.title.lower()))
            return recent + rest

        query_tokens = clean_q.split()
        matches = []

        for item in self._commands.values():
            haystack = f"{item.title} {item.description} {item.category} {item.shortcut}".lower()
            if all(tok in haystack for tok in query_tokens):
                # Scoring: exact prefix matches rank higher
                title_lower = item.title.lower()
                score = 0
                if title_lower.startswith(clean_q):
                    score += 50
                elif clean_q in title_lower:
                    score += 25
                if item.id in self._mru_ids:
                    score += 10
                matches.append((score, item))

        matches.sort(key=lambda pair: (-pair[0], pair[1].category, pair[1].title.lower()))
        return [item for _, item in matches]

    def execute(self, item_id: str) -> tuple[bool, str]:
        """
        Execute command safely.
        Returns (success: bool, message: str).
        """
        cmd = self._commands.get(item_id)
        if not cmd:
            msg = f"Command '{item_id}' not found."
            self._notify_log(f"ERR: {msg}")
            return False, msg

        if not cmd.is_available:
            msg = cmd.unavailable_reason or f"Command '{cmd.title}' is currently unavailable."
            self._notify_log(f"SYS: {msg}")
            return False, msg

        if cmd.requires_params:
            params_str = ", ".join(cmd.param_names) if cmd.param_names else "arguments"
            msg = (
                f"Action '{cmd.title}' requires parameters ({params_str}). "
                "Please speak or type your full request in the prompt."
            )
            self._notify_log(f"SYS: {msg}")
            return False, msg

        try:
            self.record_mru(cmd.id)
            if callable(cmd.handler):
                res = cmd.handler()
                msg = res if isinstance(res, str) else f"Executed: {cmd.title}"
                self._notify_log(f"SYS: {msg}")
                return True, msg
            else:
                msg = f"Ready: {cmd.title}"
                return True, msg
        except Exception as e:
            err_msg = f"Command '{cmd.title}' failed: {e}"
            self._notify_log(f"ERR: {err_msg}")
            return False, err_msg
