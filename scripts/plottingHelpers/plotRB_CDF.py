#!/usr/bin/env python3
"""
CDF of Resource Blocks per operator, one plot for downlink and one for uplink.

  in : results/speedtest/allMetrics/<operator>/combined_downlink.csv
       results/speedtest/allMetrics/<operator>/combined_uplink.csv
  out: graphs/speedtest/Ratio_plots/<DATE>/DL_ResourceBlocks_CDF.png
       graphs/speedtest/Ratio_plots/<DATE>/UL_ResourceBlocks_CDF.png
       and, if PLOT_RATIO is True, the same CDFs with RB as % of N_rb:
       graphs/speedtest/Ratio_plots/<DATE>/DL_ResourceBlocks_Ratio_CDF.png
       graphs/speedtest/Ratio_plots/<DATE>/UL_ResourceBlocks_Ratio_CDF.png

Each plot has one line per operator (empirical CDF over every record in the CSV).
Raw RB counts are not directly comparable across operators with different bandwidth
(Vi has N_rb = 133, Jio/Airtel 273), so the ratio version (RB / N_rb * 100) is also saved.

Usage: edit the CONFIG block, then run  python plot_rb_cdf.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ───────────────────────────── CONFIG ──────────────────────────────
IN_ROOT = Path("results/speedtest/allMetrics")
DATE = "20261006"
OUT_DIR = Path("graphs/speedtest/Ratio_plots") / DATE

DIRECTIONS = {"DL": "combined_downlink.csv", "UL": "combined_uplink.csv"}
RB_COL = "Resource Blocks"

PLOT_RATIO = True                   # also save RB / N_rb (%) CDFs
N_RB = {"jio": 273, "airtel": 273, "vi": 133, "vodafone": 133, "vodafone idea": 133, "vodafoneidea": 133}

OPERATOR_ORDER = ["Airtel", "Jio", "Vodafone"]   # legend order; others follow alphabetically
# Same operator colours and markers as the other plots (colour-blind-safe palette)
STYLES = [("#2a78d6", "-"), ("#eb6834", "--"), ("#1baf7a", "-."), ("#4a3aa7", ":"), ("#e87ba4", "-")]

DPI = 300
# ───────────────────────────────────────────────────────────────────

plt.rcParams.update({
    "font.size": 15, "axes.labelsize": 16, "xtick.labelsize": 14, "ytick.labelsize": 14,
    "legend.fontsize": 14, "axes.linewidth": 1.2, "lines.linewidth": 2.2,
    "savefig.bbox": "tight",
})
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    "font.serif": ["Times"],
})


def log(msg):
    print(msg, flush=True)


def order_ops(ops):
    rank = {o.lower(): i for i, o in enumerate(OPERATOR_ORDER)}
    return sorted(ops, key=lambda o: (rank.get(o.lower(), len(rank)), o.lower()))


def load(file_name):
    """Returns {operator: numpy array of RB values}."""
    out = {}
    for op_dir in sorted(p for p in IN_ROOT.iterdir() if p.is_dir()):
        src = op_dir / file_name
        if not src.exists():
            log(f"    {op_dir.name}: {file_name} not found, skipping")
            continue
        df = pd.read_csv(src)
        df.columns = [" ".join(c.split()) for c in df.columns]
        if RB_COL not in df.columns:
            log(f"    {op_dir.name}: no '{RB_COL}' column, skipping")
            continue
        rb = pd.to_numeric(df[RB_COL], errors="coerce").dropna().to_numpy()
        if rb.size:
            out[op_dir.name] = rb
    return out


def plot_cdf(data, xlabel, title, dest, xlim=None):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, op in enumerate(order_ops(data)):
        x = np.sort(data[op])
        y = np.arange(1, x.size + 1) / x.size
        color, ls = STYLES[i % len(STYLES)]
        ax.step(x, y, where="post", color=color, linestyle=ls, label=f"{op}")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("CDF")
    ax.set_ylim(0, 1.02)
    if xlim:
        ax.set_xlim(*xlim)
    ax.grid(True, color="#b0b0b0", linewidth=0.9)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=len(data), frameon=False,
              fontsize=13, handlelength=2.5)
    fig.savefig(dest, dpi=DPI)
    plt.close(fig)
    log(f"    -> {dest}")


def main():
    if not IN_ROOT.is_dir():
        sys.exit(f"{IN_ROOT} not found")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for tag, file_name in DIRECTIONS.items():
        log(f"[{tag}]")
        data = load(file_name)
        if not data:
            log(f"    no data for {tag}")
            continue
        for op, v in data.items():
            log(f"    {op}: {v.size} records, median RB = {np.median(v):g}")
        name = "Downlink" if tag == "DL" else "Uplink"

        x_max = max(v.max() for v in data.values())
        plot_cdf(data, "Resource Blocks", f"{name}: Resource Blocks",
                 OUT_DIR / f"{tag}_ResourceBlocks_CDF.png", xlim=(0, x_max * 1.03))


if __name__ == "__main__":
    main()