#!/usr/bin/env python3
"""
Merge PHY (QMDL) + signal logs into one per-second CSV per capture,
separately for downlink and uplink.

Output:
  results/dummyVC/allMetrics/<operator>/<location>/<date>/capture_<id>_downlink.csv
  results/dummyVC/allMetrics/<operator>/<location>/<date>/capture_<id>_uplink.csv

PHY folder layout (USE_SPEEDTEST_PATH):
  True : <PHY_ROOT>/<operator>/<date>/capture_*/speedtest/readable_b887.csv (+ b881)
  False: <PHY_ROOT>/<operator>/<date>/capture_*/readable_b887.csv (+ b881)
  The PHY path has no location, so it is taken from the signal tree.

Optional (INCLUDE_THROUGHPUT = True): also adds the measured per-second throughput from
  results/Throughput/<operator>/<location>/<date>/capture_*/capture_*.csv
  (Timestamp, Download (Mbps), Upload (Mbps)).

Timeline = the QMDL (PHY) file: second 0 = its first sample, one row per second
up to its last sample. Everything else is fitted to that timeline:
  * PHY (5 ms)  -> per 1 s: mean for numeric columns (incl. MCS), most frequent modulation
  * Signal      -> first row = 0 s, then offsets from the HH:MM:SS diffs; values are
                   repeated until the next sample, and only as many seconds as the
                   QMDL covers are used. Values are converted to Strong/Average/Poor/No Signal.

Signal tree: <SIG_ROOT>/<operator>/<location>/<date>/capture_*/session_*/network_logs_*.csv

Usage: edit the CONFIG block below, then run  python build_all_metrics.py
"""
import re
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

# ───────────────────────────── CONFIG ──────────────────────────────
PHY_ROOT = Path("results/QMDL_Results")
SIG_ROOT = Path("/Volumes/Untitled/5G_Measurements/data")
OUT_ROOT = Path("results/dummyVC/allMetrics")
OPERATOR = None
LOCATION = "Bharti501"
DATE = "20261006"
USE_SPEEDTEST_PATH = False
INCLUDE_THROUGHPUT = True


# Where the signal log is searched inside a capture folder (first pattern that matches wins).
SIGNAL_GLOBS = ["session_*/network_logs_*.csv", "speedtest/session_*/network_logs_*.csv"]
TPUT_ROOT = Path("results/Throughput")
TPUT_TIME_COL = "Timestamp"
TPUT_SRC_COLS = {"downlink": "Download (Mbps)", "uplink": "Upload (Mbps)"}

# Unit of the PHY time column: "auto" (only detects epoch magnitudes), "s", "ms", "us" or "ns".
PHY_TIME_UNIT = "auto"

# Time-column names tried (case-insensitive) in the PHY files; falls back to column 0.
PHY_TIME_CANDIDATES = ["timestamp", "time", "epoch", "epoch_time", "unix_time",
                       "ts", "time_stamp", "sys_time", "datetime"]

# Shift the signal timeline relative to the QMDL timeline (seconds).
SIGNAL_OFFSET_S = 0

# MCS -> modulation (applied to every 5 ms row; fractional MCS is floored)
MCS_RANGES = [(0, 4, "QPSK"), (5, 10, "16QAM"), (11, 19, "64QAM"), (20, 27, "256QAM"), (28, 31, "Reserved")]
MOD_ORDER = [name for _, _, name in MCS_RANGES]   # also the tie-break order per second

# PHY files. "files" = accepted file names (first one found is used; both spellings are
# listed because the file is sometimes written without the underscore).
# "mcs" = source column converted to Modulation; "cols" = numeric columns.
# "retx" describes how new vs retransmitted bytes are found (summed per second, then
# rate = retx / (new + retx) * 100):
#   kind "rv"    (DL): rv == 0 -> tb_size_bytes is new, rv > 0 -> tb_size_bytes is retransmitted
#   kind "bytes" (UL): separate new / retransmitted byte columns
RATE_COL = "Retransmission Rate (%)"
# PHY throughput: per second, sum ALL transport-block bytes (new + retransmitted) * 8 / 1e6.
# "size" = bytes column; "fallback" = columns summed instead if "size" is absent.
TPUT_COL = "PHY Throughput (Mbps)"
DL_PHY = {"files": ["readable_b887.csv", "readableb887.csv"], "mcs": "mcs",
          "cols": {"num_rbs": "Resource Blocks", "num_layers": "MIMO (layers)"},
          "retx": {"kind": "rv", "rv": "rv", "size": "tb_size_bytes"},
          "tput": {"size": "tb_size_bytes"}}
UL_PHY = {"files": ["readable_b881.csv", "readableb881.csv"], "mcs": "avg_mcs_this_interval",
          "cols": {"delta_num_prb": "Resource Blocks"},
          "retx": {"kind": "bytes", "new": "delta_new_tx_bytes", "retx": "delta_retx_bytes"},
          "tput": {"size": "tb_size_bytes", "fallback": ["delta_new_tx_bytes", "delta_retx_bytes"]}}

# Per-second aggregation of the numeric 5 ms columns (mean, as requested).
# Override per source column if you prefer totals, e.g. {"delta_num_prb": "sum"}.
PHY_AGG_DEFAULT = "mean"
PHY_AGG_OVERRIDE = {}

# Signal level thresholds (dB / dBm). A value falls in the first level whose lower
# bound it reaches; "strong_inclusive" says whether the Strong bound itself is Strong.
#   RSRP: Strong > -85 | Average -105..-85 | Poor -120..-105 | No Signal < -120
#   RSRQ: Strong >= -9 | Average -14..-9   | Poor -19..-14   | No Signal < -19
#   SINR: Strong > 20  | Average 13..20    | Poor 0..13      | No Signal < 0
if OPERATOR == "Jio":
    SIG_LEVELS = {
        "rsrp": dict(strong=-85, average=-105, poor=-120, strong_inclusive=False),
        "rsrq": dict(strong=-9, average=-14, poor=-19, strong_inclusive=True),
        "sinr": dict(strong=20, average=13, poor=0, strong_inclusive=False),
    }
else :
    SIG_LEVELS = {
        "rsrp": dict(strong=-85, average=-105, poor=-120, strong_inclusive=False),
        "rsrq": dict(strong=-9, average=-14, poor=-19, strong_inclusive=True),
    }

SIG_COLS = list(SIG_LEVELS)
# ───────────────────────────────────────────────────────────────────

KEY_RE = re.compile(r"(\d{8}_\d{6})")


def log(msg):
    print(msg, flush=True)


# ───────────────────────────── helpers ─────────────────────────────
def capture_key(name: str) -> str:
    """'capture_002_20260929_113151' -> '20260929_113151' (used to match folders across trees)."""
    m = KEY_RE.findall(name)
    return m[-1] if m else name


def ci_child(parent, name):
    """Case-insensitive child lookup; returns None if parent is None / missing."""
    if parent is None or not parent.is_dir():
        return None
    p = parent / name
    if p.exists():
        return p
    for c in parent.iterdir():
        if c.name.lower() == name.lower():
            return c
    return None


def find_capture_dir(parent, key):
    if parent is None or not parent.is_dir():
        return None
    for c in sorted(parent.iterdir()):
        if c.is_dir() and capture_key(c.name) == key:
            return c
    return None


def subdirs(parent, pattern="*"):
    return sorted(p for p in parent.glob(pattern) if p.is_dir())


def find_phy_file(folder, names):
    """First existing file among the accepted names (case-insensitive)."""
    for n in names:
        p = ci_child(folder, n)
        if p is not None and p.is_file():
            return p
    return None


def to_seconds(col, unit="auto"):
    """Convert a time column to float seconds (numeric epoch/relative or datetime strings)."""
    num = pd.to_numeric(col, errors="coerce")
    if num.notna().mean() > 0.9:
        x = num.astype(float)
        if unit == "auto":
            m = x.abs().median()
            scale = 1e9 if m > 1e17 else 1e6 if m > 1e14 else 1e3 if m > 1e11 else 1.0
        else:
            scale = {"s": 1.0, "ms": 1e3, "us": 1e6, "ns": 1e9}[unit]
        return x / scale
    dt = pd.to_datetime(col, errors="coerce", utc=True)
    return (dt - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()


def classify(s, strong, average, poor, strong_inclusive=False):
    """Numeric signal values -> Strong / Average / Poor / No Signal (NaN stays NaN)."""
    x = pd.to_numeric(s, errors="coerce")
    conds = [x >= strong if strong_inclusive else x > strong, x >= average, x >= poor, x < poor]
    out = pd.Series(np.select(conds, ["Strong", "Average", "Poor", "No Signal"], default=""),
                    index=x.index, dtype=object)
    return out.where(x.notna())


def mcs_to_modulation(mcs):
    """MCS values -> QPSK / 16QAM / 64QAM / Reserved (NaN if missing or outside 0-31)."""
    m = np.floor(pd.to_numeric(mcs, errors="coerce"))
    out = pd.Series(np.nan, index=m.index, dtype=object)
    for lo, hi, name in MCS_RANGES:
        out[(m >= lo) & (m <= hi)] = name
    return out, int((m.notna() & out.isna()).sum())


def find_col(df, name):
    """Case-insensitive column lookup (None if absent)."""
    for c in df.columns:
        if c.lower() == name.lower():
            return c
    return None


def retx_rate_per_second(df, rel, spec, missing):
    """Per second: sum new and retransmitted bytes, then retx / (new + retx) * 100.
    Seconds with no transmitted bytes have no defined rate and stay empty."""
    num = lambda c: pd.to_numeric(df[c], errors="coerce")
    if spec["kind"] == "rv":
        rv_c, size_c = find_col(df, spec["rv"]), find_col(df, spec["size"])
        absent = [n for n, c in ((spec["rv"], rv_c), (spec["size"], size_c)) if c is None]
        if absent:
            missing.extend(absent)
            return None
        rv, size = num(rv_c), num(size_c)
        new = size.where(rv == 0, 0.0)      # RV = 0 -> new transmission
        retx = size.where(rv > 0, 0.0)      # RV > 0 -> retransmitted
    else:
        new_c, retx_c = find_col(df, spec["new"]), find_col(df, spec["retx"])
        absent = [n for n, c in ((spec["new"], new_c), (spec["retx"], retx_c)) if c is None]
        if absent:
            missing.extend(absent)
            return None
        new, retx = num(new_c), num(retx_c)

    g = pd.DataFrame({"new": new.values, "retx": retx.values}).groupby(rel.values).sum()
    total = g["new"] + g["retx"]
    return (g["retx"] / total.where(total > 0) * 100).rename(RATE_COL)


def phy_throughput_per_second(df, rel, spec, missing):
    """Per second: sum all transport-block bytes (new + retransmitted) -> Mbps."""
    size_c = find_col(df, spec["size"])
    if size_c is not None:
        size = pd.to_numeric(df[size_c], errors="coerce")
    elif spec.get("fallback"):
        cols = [find_col(df, n) for n in spec["fallback"]]
        if any(c is None for c in cols):
            missing.append(spec["size"])
            return None
        log(f"    note: '{spec['size']}' not found, using {' + '.join(spec['fallback'])}")
        size = sum(pd.to_numeric(df[c], errors="coerce").fillna(0) for c in cols)
    else:
        missing.append(spec["size"])
        return None
    return (size.groupby(rel.values).sum(min_count=1) * 8 / 1e6).rename(TPUT_COL)


# ───────────────────────────── loaders ─────────────────────────────
def load_phy(path, spec, unit):
    """5 ms rows -> per-second table indexed 0..N-1 (seconds since the file's first sample)."""
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    lower = {c.lower(): c for c in df.columns}
    tcol = next((lower[c] for c in PHY_TIME_CANDIDATES if c in lower), df.columns[0])
    t = to_seconds(df[tcol], unit)
    ok = t.notna()
    if not ok.any():
        log(f"    ! {path.name}: no usable timestamps in '{tcol}'")
        return None, 0, None
    df, t = df.loc[ok], t[ok]
    rel = np.floor(t - t.min()).astype(int)
    n_rows = int(rel.max()) + 1
    log(f"    {path.name}: time col '{tcol}', median spacing {t.diff().abs().median():.4f}s, "
        f"{n_rows} s of data")

    parts = []
    num_src = [c for c in spec["cols"] if c in df.columns]
    missing = [c for c in spec["cols"] if c not in df.columns]
    if num_src:
        vals = df[num_src].apply(pd.to_numeric, errors="coerce")
        agg = {c: PHY_AGG_OVERRIDE.get(c, PHY_AGG_DEFAULT) for c in num_src}
        parts.append(vals.groupby(rel.values).agg(agg).rename(columns=spec["cols"]))

    if spec["mcs"] in df.columns:
        mcs_vals = pd.to_numeric(df[spec["mcs"]], errors="coerce")
        parts.append(mcs_vals.groupby(rel.values).mean().rename("MCS"))   # mean MCS per second
        mod, n_bad = mcs_to_modulation(mcs_vals)
        if n_bad:
            log(f"    ! {n_bad} rows have MCS outside 0-31 -> left empty")
        d = pd.DataFrame({"rel": rel.values, "mod": mod.values}).dropna()
        if not d.empty:
            counts = pd.crosstab(d["rel"], d["mod"]).reindex(columns=MOD_ORDER, fill_value=0)
            parts.append(counts.idxmax(axis=1).rename("Modulation"))   # most frequent per second
    else:
        missing.append(spec["mcs"])
    tput = phy_throughput_per_second(df, rel, spec["tput"], missing)
    if tput is not None:
        parts.append(tput)
    rate = retx_rate_per_second(df, rel, spec["retx"], missing)
    if rate is not None:
        parts.append(rate)
    if missing:
        log(f"    ! {path.name}: missing columns {missing}")

    phy = pd.concat(parts, axis=1) if parts else pd.DataFrame(index=pd.Index([], dtype=int))
    phy = phy.reindex(range(n_rows))
    phy.index.name = "_rel"
    return phy, n_rows, (t.min() if t.median() > 1e8 else None)   # epoch start, if absolute


def load_signal(cap_dir):
    """Signal log: first row = 0 s, then cumulative HH:MM:SS differences; values -> levels."""
    if cap_dir is None:
        return None, None
    files = []
    for pattern in SIGNAL_GLOBS:
        files = sorted(cap_dir.glob(pattern))
        if files:
            break
    if not files:
        return None, None
    if len(files) > 1:
        log(f"    ! {len(files)} signal logs found, using {files[0].name}")
    df = pd.read_csv(files[0], na_values=["N/A", "NA", ""])
    df.columns = [c.strip() for c in df.columns]

    secs = pd.to_timedelta(df["time"].astype(str).str.strip(), errors="coerce").dt.total_seconds()
    df = df.loc[secs.notna()].copy()
    secs = secs[secs.notna()].to_numpy()
    d = np.diff(secs, prepend=secs[0])
    d[d < 0] += 86400  # midnight rollover
    rel = np.floor(np.cumsum(d)).astype(int) + int(SIGNAL_OFFSET_S)

    sig = pd.DataFrame({"_rel": rel})
    for c, thr in SIG_LEVELS.items():
        sig[c] = classify(df[c].reset_index(drop=True), **thr)
    sig = sig.sort_values("_rel")

    step = int(np.ceil(np.median(np.diff(rel)))) if len(rel) > 1 else 5
    return sig, int(rel.max()) + step      # last second the final sample is still considered valid


# ───────────────────────────── build ───────────────────────────────
def load_throughput(cap_dir, tcol, phy_t0):
    """Per-second measured throughput, indexed by seconds since QMDL start."""
    if cap_dir is None:
        return None
    files = sorted(cap_dir.glob("capture_*.csv"))
    if not files:
        log(f"    ! no throughput CSV in {cap_dir}")
        return None
    df = pd.read_csv(files[0])
    df.columns = [c.strip() for c in df.columns]
    if TPUT_TIME_COL not in df.columns or tcol not in df.columns:
        log(f"    ! {files[0].name}: needs columns '{TPUT_TIME_COL}' and '{tcol}'")
        return None

    df = df.assign(_t=to_seconds(df[TPUT_TIME_COL])).dropna(subset=["_t"])
    df = df.sort_values("_t").reset_index(drop=True)
    val = pd.to_numeric(df[tcol], errors="coerce")

    if phy_t0 is not None and df["_t"].median() > 1e8:
        base, mode = phy_t0, "absolute time"
    else:
        base, mode = df["_t"].iloc[0], "relative (first sample = 0)"
    log(f"    {files[0].name}: {len(df)} rows, aligned to QMDL by {mode}")

    out = pd.DataFrame({"_rel": np.floor(df["_t"] - base).astype(int), tcol: val})
    return out.groupby("_rel").mean()               # one value per second


def build(phy, n_rows, sig, sig_end, phy_cols_out, tput=None):
    out = pd.DataFrame({"_rel": np.arange(n_rows)})
    out = out.merge(phy, left_on="_rel", right_index=True, how="left")
    if tput is not None:
        out = out.merge(tput, left_on="_rel", right_index=True, how="left")
    for c in ["MCS", "Modulation"] + phy_cols_out:
        if c not in out.columns:
            out[c] = np.nan

    if sig is not None:
        out = pd.merge_asof(out, sig, on="_rel", direction="backward")
        stale = out["_rel"] > sig_end
        if stale.any():
            log(f"    ! signal log ends ~{sig_end}s but QMDL has {n_rows}s -> "
                f"{int(stale.sum())} trailing rows left empty")
            out.loc[stale, SIG_COLS] = np.nan
    else:
        for c in SIG_COLS:
            out[c] = np.nan

    out["Timestamp"] = out["_rel"]
    out = out[["Timestamp", "MCS", "Modulation"] + phy_cols_out + SIG_COLS].round(4)
    if "MIMO (layers)" in out.columns:
        out["MIMO (layers)"] = out["MIMO (layers)"].round().astype("Int64")
    return out


def find_in_location_tree(sig_root, operator, date, key):
    """Locate the capture in a <root>/<operator>/<location>/<date>/capture_* tree;
    returns (location, capture_dir)."""
    op_dir = ci_child(sig_root, operator)
    if op_dir is None:
        return None, None
    hits = []
    for loc in sorted(p for p in op_dir.iterdir() if p.is_dir()):
        cd = find_capture_dir(ci_child(loc, date), key)
        if cd is not None:
            hits.append((loc.name, cd))
    if len(hits) > 1:
        log(f"    ! capture found under several locations {[h[0] for h in hits]}, using {hits[0][0]}")
    return hits[0] if hits else (None, None)


def process_capture(cap_dir, phy_dir, operator, date):
    """cap_dir: the capture_* folder (its name carries the capture id used to match the other
    trees). phy_dir: folder holding the readable_b88x.csv files (cap_dir or cap_dir/speedtest).
    The location is looked up in the signal (or throughput) tree."""
    key = capture_key(cap_dir.name)
    sig_location, sig_dir = find_in_location_tree(SIG_ROOT, operator, date, key)
    tp_location, tp_dir = (find_in_location_tree(TPUT_ROOT, operator, date, key)
                           if INCLUDE_THROUGHPUT else (None, None))
    location = sig_location or tp_location
    if LOCATION and (location or "").lower() != LOCATION.lower():
        return
    log(f"\n[{operator}/{location or 'unknown_location'}/{date}/{cap_dir.name}]")
    if sig_dir is None:
        log("    ! no matching signal capture -> signal columns empty")
    if INCLUDE_THROUGHPUT and tp_dir is None:
        log("    ! no matching throughput capture -> throughput columns empty")
    if location is None:
        log("    ! location unknown")
        location = "unknown_location"

    sig, sig_end = load_signal(sig_dir)
    if sig is None and sig_dir is not None:
        log("    ! no signal log in the matching capture folder")

    out_dir = OUT_ROOT / operator / location / date
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, spec in (("downlink", DL_PHY), ("uplink", UL_PHY)):
        path = find_phy_file(phy_dir, spec["files"])
        if path is None:
            log(f"    ! none of {spec['files']} found in {phy_dir} -> no {name} file")
            continue
        phy, n_rows, phy_t0 = load_phy(path, spec, PHY_TIME_UNIT)
        if phy is None:
            continue
        cols_out = list(spec["cols"].values()) + [TPUT_COL, RATE_COL]
        tput = None
        if INCLUDE_THROUGHPUT:
            tcol = TPUT_SRC_COLS[name]
            cols_out += [tcol]
            tput = load_throughput(tp_dir, tcol, phy_t0)
        df = build(phy, n_rows, sig, sig_end, cols_out, tput)
        dest = out_dir / f"capture_{key}_{name}.csv"
        df.to_csv(dest, index=False)
        cov = {c: f"{df[c].notna().mean():.0%}" for c in df.columns[1:]}
        log(f"    -> {dest}  ({len(df)} rows, non-empty: {cov})")


def main():
    # job = (capture folder, folder with the readable_b88x.csv files, operator, date)
    jobs = []
    for op_dir in subdirs(PHY_ROOT):
        if OPERATOR and op_dir.name.lower() != OPERATOR.lower():
            continue
        for date_dir in subdirs(op_dir):
            if DATE and date_dir.name != DATE:
                continue
            for cap in subdirs(date_dir, "capture_*"):
                phy_dir = cap / "speedtest" if USE_SPEEDTEST_PATH else cap
                if phy_dir.is_dir():
                    jobs.append((cap, phy_dir, op_dir.name, date_dir.name))

    if not jobs:
        layout = ("<operator>/<date>/capture_*/speedtest" if USE_SPEEDTEST_PATH
                  else "<operator>/<date>/capture_*")
        sys.exit(f"No capture folders found under {PHY_ROOT.resolve()} "
                 f"(expected {layout}; USE_SPEEDTEST_PATH={USE_SPEEDTEST_PATH})")
    log(f"Found {len(jobs)} capture(s)")

    failed = 0
    for cap, phy_dir, op, date in jobs:
        try:
            process_capture(cap, phy_dir, op, date)
        except Exception:
            failed += 1
            log(f"    !! failed on {cap}")
            traceback.print_exc()
    log(f"\nDone. {len(jobs) - failed} ok, {failed} failed.")


if __name__ == "__main__":
    main()