"""Regenerate (or just check) the frozen-case guard fixtures.

    python reproduction/frozen_guard/regenerate.py                    # run every case, print what differs, write nothing
    python reproduction/frozen_guard/regenerate.py --case flood       # one case
    python reproduction/frozen_guard/regenerate.py --update           # write the new fixtures

Only --update writes. The tests never regenerate. Read the printed differences before
you commit an update: a changed fixture means the code now behaves differently from the
paper's frozen case, and that has to be intended.

The irrigation case needs the optional CRSS bundle (ref/CRSS_DB/CRSS_DB, see DATA.md).
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frozen_guard_common as fg  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", choices=list(fg.CASES) + ["all"], default="all")
    ap.add_argument("--update", action="store_true", help="write the fixtures (default: only report)")
    args = ap.parse_args(argv)

    cases = fg.CASES if args.case == "all" else (args.case,)
    changed = 0
    with tempfile.TemporaryDirectory(prefix="frozen_guard_") as tmp:
        for case in cases:
            if case == "irrigation" and not fg.crss_available():
                print(f"[{case}] skipped: ref/CRSS_DB/CRSS_DB is absent (see DATA.md)")
                continue
            for arm in fg.arms(case):
                print(f"[{case}/{arm}] running ...", flush=True)
                art = fg.run_arm(case, arm, Path(tmp) / case / arm)
                try:
                    golden = fg.read_golden(case, arm)
                except FileNotFoundError:
                    golden = {}
                diffs = fg.diff_artifacts(golden, art, limit=20) if golden else ["no fixtures yet"]
                if diffs:
                    changed += 1
                    print(f"[{case}/{arm}] DIFFERS from the fixtures:")
                    for d in diffs:
                        print("   " + d)
                else:
                    print(f"[{case}/{arm}] unchanged")
                if args.update and diffs:
                    fg.write_golden(case, arm, art)
                    print(f"[{case}/{arm}] fixtures written")
    if changed and not args.update:
        print(f"\n{changed} arm(s) differ; nothing written (use --update to write).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
