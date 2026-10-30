"""Append-only audit trail: output/audit_trail.json.

Every agent-loop step (model step, MCP tool call, delegation, report, decision,
run start/end) is appended as one JSON object. The file is a JSON array that
grows across runs; it is never wiped. Writes go to a temp file first and are
swapped in, so a crash can't leave half a file behind.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

import config

_lock = threading.Lock()


def append(entry: dict[str, Any]) -> None:
    path = config.AUDIT_TRAIL
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows: list[Any] = []
        if path.exists() and path.stat().st_size > 0:
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                rows = loaded if isinstance(loaded, list) else [loaded]
            except json.JSONDecodeError:
                # Keep the damaged file for inspection instead of overwriting it.
                path.replace(path.with_name(f"audit_trail.corrupt-{datetime.now():%Y%m%d-%H%M%S}.json"))
        rows.append(entry)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(path)
