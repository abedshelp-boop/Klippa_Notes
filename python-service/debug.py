"""
Dev-time debug helper. `log` / `warn` are no-ops unless is_dev is True.
`error` always prints — errors stay loud in dev and prod.

Routing convention (matches electron/main.js stdout/stderr pipes):
- log()   -> stdout, shows up in Electron as "[Python] [Subsystem] message"
- warn()  -> stderr, shows up as "[Python ERROR] [WARN][Subsystem] message"
- error() -> stderr, shows up as "[Python ERROR] [ERROR][Subsystem] message"
"""

from __future__ import annotations

import os
import sys
from typing import Any


class Debug:
    def __init__(self, is_dev: bool) -> None:
        self._is_dev = is_dev

    def log(self, subsystem: str, message: str, *data: Any) -> None:
        if not self._is_dev:
            return
        print(f"[{subsystem}] {message}", *data)

    def warn(self, subsystem: str, message: str, *data: Any) -> None:
        if not self._is_dev:
            return
        print(f"[WARN][{subsystem}] {message}", *data, file=sys.stderr)

    def error(self, subsystem: str, message: str, *data: Any) -> None:
        # ALWAYS prints, even when is_dev=False.
        print(f"[ERROR][{subsystem}] {message}", *data, file=sys.stderr)


def create_debug(is_dev: bool) -> Debug:
    return Debug(is_dev)


# Default singleton wired against env var. Electron sets DEEN_DEV=1 in dev mode
# (see electron/main.js task in Phase 4). In packaged builds the var is absent.
debug = create_debug(os.environ.get("DEEN_DEV", "0") == "1")
