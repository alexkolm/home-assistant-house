#!/usr/bin/env python3
"""Append one JSON object to /config/boiler_link.jsonl.

The argument is standard base64 of a single-line JSON object.
Home Assistant passes it from shell_command.boiler_link_append.
"""

import base64
import json
import sys
from pathlib import Path

PATH = Path("/config/boiler_link.jsonl")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("expected one base64 argument")
    try:
        raw = base64.b64decode(sys.argv[1], validate=True)
        record = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as err:
        raise SystemExit(f"bad payload: {err}") from err
    if not isinstance(record, dict) or "event" not in record or "ts" not in record:
        raise SystemExit("payload must be an object with ts and event")
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


if __name__ == "__main__":
    main()
