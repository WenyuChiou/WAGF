#!/usr/bin/env python3
"""Tiny external model for the Archetype-C (subprocess) worked example.

Protocol (see ``broker.coupling.SubprocessModelConnector``): read ONE JSON
object from stdin (``{"period": <int>}``), write ONE JSON object to stdout
naming every field the contract declares, exit 0. No dependency beyond the
standard library — this stands in for "some researcher's Fortran/R/Python
model that already exists and speaks files or stdio."

Deterministic given ``period`` (a real model earns non-determinism; a demo
should not need one): a sensor "reading" that ramps up then spikes in
period 3, so the worked example agent sees a low-then-high signal.
"""
from __future__ import annotations

import json
import sys

READINGS_BY_PERIOD = {1: 12.0, 2: 18.0, 3: 47.0, 4: 22.0}


def main() -> int:
    raw = sys.stdin.read()
    request = json.loads(raw) if raw.strip() else {}
    period = int(request.get("period", 1))
    reading = READINGS_BY_PERIOD.get(period, READINGS_BY_PERIOD[max(READINGS_BY_PERIOD)])
    sys.stdout.write(json.dumps({"reading": reading, "period_echo": period}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
