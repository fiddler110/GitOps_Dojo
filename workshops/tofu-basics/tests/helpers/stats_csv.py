#!/usr/bin/env python3
"""Turns one `podman stats --no-stream --format json` (or docker `--format '{{json .}}'`) reading into CSV rows.

    podman stats --no-stream --format json A B C | python3 stats_csv.py 1758460000.123 >> stats.csv

Row: epoch,name,mem_bytes,mem_pct,cpu_pct,pids       (nothing on stdin, or unparseable input, prints nothing)
podman's keys are name / mem_usage / mem_percent / cpu_percent / pids; docker's are Name / MemUsage / MemPerc /
CPUPerc / PIDs; both are read. mem_usage looks like "262.1kB / 10.43GB": the part before the slash is the use.
"""
import json
import re
import sys

UNITS = {"b": 1, "kb": 1000, "kib": 1024, "mb": 1000 ** 2, "mib": 1024 ** 2, "gb": 1000 ** 3, "gib": 1024 ** 3,
         "tb": 1000 ** 4, "tib": 1024 ** 4}


def to_bytes(text):
    m = re.match(r"\s*([0-9.]+)\s*([A-Za-z]*)", str(text).split("/")[0])
    if not m:
        return ""
    return str(int(float(m.group(1)) * UNITS.get(m.group(2).lower() or "b", 1)))


def pct(text):
    m = re.match(r"\s*([0-9.]+)", str(text))
    return m.group(1) if m else ""


def pick(entry, *names):
    for name in names:
        if name in entry:
            return entry[name]
    return ""


def load(raw):
    raw = raw.strip()
    if not raw:
        return []
    try:
        doc = json.loads(raw)
        return doc if isinstance(doc, list) else [doc]
    except ValueError:
        pass
    rows = []
    for line in raw.splitlines():  # docker: one JSON object per line
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def main(argv):
    epoch = argv[0] if argv else ""
    for e in load(sys.stdin.read()):
        if not isinstance(e, dict):
            continue
        name = pick(e, "name", "Name")
        print(",".join([epoch, str(name), to_bytes(pick(e, "mem_usage", "MemUsage")),
                        pct(pick(e, "mem_percent", "MemPerc")), pct(pick(e, "cpu_percent", "CPUPerc")),
                        str(pick(e, "pids", "PIDs", "PIDS"))]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
