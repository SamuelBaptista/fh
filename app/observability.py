from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


class Logger:
    def __init__(self, load_id: str = "", event_id: str = "", request_id: str = ""):
        self._context = {
            "load_id": load_id,
            "event_id": event_id,
            "request_id": request_id,
        }

    def _emit(self, level: str, msg: str, **kwargs: object) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "msg": msg,
            **self._context,
            **kwargs,
        }
        print(json.dumps(record, default=str), file=sys.stdout, flush=True)

    def info(self, msg: str, **kwargs: object) -> None:
        self._emit("INFO", msg, **kwargs)

    def warn(self, msg: str, **kwargs: object) -> None:
        self._emit("WARN", msg, **kwargs)

    def error(self, msg: str, **kwargs: object) -> None:
        self._emit("ERROR", msg, **kwargs)


class JsonlWriter:
    def __init__(self, output_dir: Path | str = "runs"):
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def write(self, event_id: str, record: dict) -> None:
        path = self._dir / f"{event_id}.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
