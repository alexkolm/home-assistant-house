"""Сравнить логику в этой папке с живым /homeassistant на HAOS.

Код на сервере иногда правят из веб-морды. Скрипт только читает файлы и
печатает расхождение. Ничего не копирует и никуда не пушит.

Подключение: ssh-псевдоним haos-house на этом компьютере.
Запуск из папки репозитория: python check_haos_drift.py
Код выхода: 0 — код совпадает, 1 — код разъехался, 2 — сервер недоступен.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

HOST = "haos-house"
REMOTE_ROOT = "/homeassistant"
WALKER = r"""
import hashlib
import os
import pathlib
import sys

root = pathlib.Path(os.environ["HAOS_ROOT"])
skip = {"secrets.yaml", "go2rtc.yaml", "check_haos_drift.py"}
code_suffixes = {".yaml", ".yml", ".py", ".jinja", ".jsonl"}


def add(found, path):
    if not path.is_file() or path.name in skip:
        return
    if path.suffix.lower() not in code_suffixes:
        return
    found.append(path.relative_to(root).as_posix())


found = []
for path in root.glob("*.yaml"):
    add(found, path)
for path in root.glob("*.yml"):
    add(found, path)
for path in root.glob("*.py"):
    add(found, path)
add(found, root / "pages.jsonl")
automations = root / "automations"
if automations.is_dir():
    for path in automations.glob("*.yaml"):
        add(found, path)
templates = root / "custom_templates"
if templates.is_dir():
    for path in templates.iterdir():
        add(found, path)
for rel in sorted(set(found)):
    data = (root / rel).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    print(hashlib.sha256(data).hexdigest(), rel)
"""


def hashes(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HAOS_ROOT"] = str(root)
    proc = subprocess.run(
        [sys.executable, "-c", WALKER],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(2)
    return parse_hashes(proc.stdout)


def remote_hashes() -> dict[str, str]:
    proc = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=20",
            HOST,
            f"HAOS_ROOT={REMOTE_ROOT} python3 -",
        ],
        input=WALKER,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout)
        print(f"Не удалось прочитать HAOS через {HOST}.", file=sys.stderr)
        raise SystemExit(2)
    return parse_hashes(proc.stdout)


def parse_hashes(text: str) -> dict[str, str]:
    found = {}
    for line in text.splitlines():
        digest, rel = line.split(" ", 1)
        found[rel] = digest
    return found


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    local_root = Path(__file__).resolve().parent
    local = hashes(local_root)
    remote = remote_hashes()
    drifted = []
    for rel in sorted(set(local) | set(remote)):
        if local.get(rel) == remote.get(rel):
            continue
        if rel not in local:
            drifted.append(f"только на HAOS: {rel}")
        elif rel not in remote:
            drifted.append(f"только локально: {rel}")
        else:
            drifted.append(f"отличается: {rel}")
    if not drifted:
        print(f"Код совпадает с HAOS ({len(local)} файлов).")
        return 0
    print("Предупреждение: код на HAOS и в локальной папке разъехался.")
    print("На сервер это не выкладывать, пока расхождение не разобрано.")
    for line in drifted:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
