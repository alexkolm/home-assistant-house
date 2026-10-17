#!/usr/bin/env python3
"""Keep /config/boiler_link.jsonl to the newest lines.

Called once a day from shell_command.trim_boiler_link_log.
A snapshot every 15 minutes is about 100 lines a day, so 8000 lines
cover roughly two months plus the connection events.
"""

from pathlib import Path

PATH = Path("/config/boiler_link.jsonl")
KEEP = 8000


def main() -> None:
    if not PATH.exists():
        return
    lines = PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(lines) <= KEEP:
        return
    tmp = PATH.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(lines[-KEEP:]), encoding="utf-8")
    tmp.replace(PATH)


if __name__ == "__main__":
    main()
