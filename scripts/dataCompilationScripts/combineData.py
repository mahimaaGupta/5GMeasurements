#!/usr/bin/env python3
import sys
from pathlib import Path

import pandas as pd

# ───────────────────────────── CONFIG ──────────────────────────────
IN_ROOT = Path("results/dummyVC/allMetrics")
OUT_ROOT = Path("results/dummyVC/allMetrics")

OPERATOR = "Vodafone"            # e.g. "Jio"; None = every operator folder in IN_ROOT

USE_WINDOW = False          # True: keep only WINDOWS below. False: keep all per-second data.
INCLUDE_TIMESTAMP = False  # keep the Timestamp column (you may want True when USE_WINDOW is False)

WINDOWS = {                # inclusive (first second, last second) kept per run
    "downlink": (0, 10),
    "uplink": (31, 41),
}
TIME_COL = "Timestamp"
RUN_COL = "Capture Run name"
# ───────────────────────────────────────────────────────────────────


def log(msg):
    print(msg, flush=True)


def main():
    if not IN_ROOT.is_dir():
        sys.exit(f"{IN_ROOT} not found")
    operators = [p for p in sorted(IN_ROOT.iterdir())
                 if p.is_dir() and (not OPERATOR or p.name.lower() == OPERATOR.lower())]
    if not operators:
        sys.exit(f"No operator folders found under {IN_ROOT}")

    for op in operators:
        for direction, (lo, hi) in WINDOWS.items():
            suffix = f"_{direction}.csv"
            # <location>/<date>/capture_*_<direction>.csv, ordered by date then run name
            files = sorted(op.glob(f"*/*/capture_*{suffix}"), key=lambda f: (f.parent.name, f.name))
            if not files:
                log(f"[{op.name}/{direction}] no files found")
                continue

            expected = hi - lo + 1
            frames = []
            for f in files:
                run = f.name[:-len(suffix)]
                df = pd.read_csv(f)
                if USE_WINDOW:
                    sub = df[df[TIME_COL].between(lo, hi)]
                    if len(sub) != expected:
                        log(f"    ! {run}: only {len(sub)} of {expected} rows in seconds {lo}-{hi} "
                            f"(file has {len(df)} s)")
                else:
                    sub = df
                if not INCLUDE_TIMESTAMP:
                    sub = sub.drop(columns=TIME_COL)
                sub = sub.copy()
                sub.insert(0, RUN_COL, run)
                frames.append(sub)

            out = pd.concat(frames, ignore_index=True)
            if "MIMO (layers)" in out.columns:      # keep whole numbers after the CSV round trip
                out["MIMO (layers)"] = out["MIMO (layers)"].round().astype("Int64")

            dest = OUT_ROOT / op.name / f"combined_{direction}.csv"
            dest.parent.mkdir(parents=True, exist_ok=True)
            out.to_csv(dest, index=False)
            log(f"[{op.name}/{direction}] {len(frames)} runs, {len(out)} rows -> {dest}")


if __name__ == "__main__":
    main()