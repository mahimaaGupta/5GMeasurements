#!/usr/bin/env python3

"""
Create separate box plots for Download and Upload throughput by operator.

Reads speedtest CSVs for each operator and creates two separate figures:
  - Download Speed (Mbit/s) across operators
  - Upload Speed (Mbit/s) across operators

Here, we're taking the entire distribution of speeds for each operator and plotting them as box plots. 

Each figure shows box plots with median, quartiles, min-max range, and means.
"""

from pathlib import Path
import os, glob, matplotlib
import pandas as pd
import matplotlib.pyplot as plt
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Setting Graph Specifications
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    "font.serif": ["Times"],
    "font.size": 10,
    "figure.figsize": (3.125, 1.56),  # Squashed height
    "legend.fontsize": 8,
    "legend.fancybox": True,
    "axes.linewidth": 0.5,
    "axes.prop_cycle": plt.cycler(color=[
        "#348ABD",  # blue
        "#A60628",  # red
        "#7A68A6",  # purple
        "#467821",  # green
        "#CF4457",  # pink
        "#188487",  # turquoise
        "#E24A33"   # orange
    ]),
    "patch.linewidth": 0.5,
    "lines.linewidth": 1.0,
    "grid.linewidth": 0.25,
    "xtick.major.width": 0.25,
    "xtick.minor.width": 0.25,
    "ytick.major.width": 0.25,
    "ytick.minor.width": 0.25,
    "ps.usedistiller": "xpdf",
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})



# Configuration
OPERATORS = ["Airtel", "Jio", "Vodafone"]
RESULT_DIR = "results/Throughput"
GRAPHS_DIR = "graphs/dummyVC/BoxPlots"
LOCATION = "Bharti501"
DATE = "20261006"

# 1. Read and combine data from all operators
combined_data = []

for op in OPERATORS:
    csv_dir = os.path.join(RESULT_DIR, op, LOCATION, DATE)
    csv_pattern = os.path.join(csv_dir, "capture_*", "capture_*.csv")
    csv_files = sorted(glob.glob(csv_pattern))
    
    if csv_files:
        for csv_path in csv_files:
            try:
                df = pd.read_csv(csv_path)
                df["Operator"] = op
                combined_data.append(df)
                print(f"[✓] Loaded {csv_path}: {len(df)} records")
            except Exception as e:
                print(f"[!] Error loading {csv_path}: {e}")
    else:
        print(f"[!] No files found matching: {csv_pattern}")

def make_combined_boxplot(summary: pd.DataFrame, title: str, out_path: Path):
    providers = sorted(summary["Operator"].unique())
    dl_data = [summary.loc[(summary["Operator"] == p) & (summary["Type"] == "Download"), "Speed (Mbit/s)"].dropna().values for p in providers]
    ul_data = [summary.loc[(summary["Operator"] == p) & (summary["Type"] == "Upload"), "Speed (Mbit/s)"].dropna().values for p in providers]
    
    n = len(providers)
    centers = list(range(1, n + 1))
    pos_dl = [c - 0.2 for c in centers]
    pos_ul = [c + 0.2 for c in centers]
    width = 0.32

    dl_color = "#4C72B0"
    ul_color = "#DD8452"

    fig, ax = plt.subplots(figsize=(max(7, n * 2.2), 5.5))

    ax.boxplot(
        dl_data,
        positions=pos_dl,
        widths=width,
        patch_artist=True,
        showmeans=True,
        showfliers=False,
        boxprops=dict(facecolor=dl_color, alpha=0.8),
        medianprops=dict(color="black"),
        meanprops=dict(marker="^", markerfacecolor="green", markeredgecolor="green"),
    )
    ax.boxplot(
        ul_data,
        positions=pos_ul,
        widths=width,
        patch_artist=True,
        showmeans=True,
        showfliers=False,
        boxprops=dict(facecolor=ul_color, alpha=0.8),
        medianprops=dict(color="black"),
        meanprops=dict(marker="^", markerfacecolor="green", markeredgecolor="green"),
    )

    ax.set_xticks(centers)
    ax.set_xticklabels(providers)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontweight("bold")
    ax.set_xlim(0.5, n + 0.5)
    # ax.set_ylim(bottom=0)
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel("Operator")
    ax.set_ylabel("Throughput (Mbps)")
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    legend_handles = [
        Patch(facecolor=dl_color, alpha=0.8, label="Download"),
        Patch(facecolor=ul_color, alpha=0.8, label="Upload"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", title="Direction")

    # fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)

def create_separate_plots(summary: pd.DataFrame, title: str, out_path: Path):
    providers = sorted(summary["Operator"].unique())
    dl_data = [summary.loc[(summary["Operator"] == p) & (summary["Type"] == "Download"), "Speed (Mbit/s)"].dropna().values for p in providers]
    ul_data = [summary.loc[(summary["Operator"] == p) & (summary["Type"] == "Upload"), "Speed (Mbit/s)"].dropna().values for p in providers]
    
    n = len(providers)
    centers = list(range(1, n + 1))
    width = 0.5  

    dl_color = "#4C72B0"
    ul_color = "#DD8452"

    # Removed sharey=True so each plot scales independently
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(max(10, n * 3.5), 5.5))

    # --- Download Subplot ---
    ax1.boxplot(
        dl_data,
        positions=centers,
        widths=width,
        patch_artist=True,
        showmeans=True,
        showfliers=False,
        boxprops=dict(facecolor=dl_color, alpha=0.8),
        medianprops=dict(color="black"),
        meanprops=dict(marker="^", markerfacecolor="green", markeredgecolor="green"),
    )
    ax1.set_xticks(centers)
    ax1.set_ylim(0)
    ax1.set_xticklabels(providers)
    ax1.set_title("Download Speed", fontweight="bold")
    ax1.set_xlabel("Operator")
    ax1.set_ylabel("Throughput (Mbps)")
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    # --- Upload Subplot ---
    ax2.boxplot(
        ul_data,
        positions=centers,
        widths=width,
        patch_artist=True,
        showmeans=True,
        showfliers=False,
        boxprops=dict(facecolor=ul_color, alpha=0.8),
        medianprops=dict(color="black"),
        meanprops=dict(marker="^", markerfacecolor="green", markeredgecolor="green"),
    )
    ax2.set_xticks(centers)
    ax2.set_ylim(0)
    ax2.set_xticklabels(providers)
    ax2.set_title("Upload Speed", fontweight="bold")
    ax2.set_xlabel("Operator")
    ax2.set_ylabel("Throughput (Mbps)") # Added Y-label here since scales differ
    ax2.grid(axis="y", linestyle="--", alpha=0.5)

    # Apply bold formatting to tick labels for both axes
    for ax in [ax1, ax2]:
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontweight("bold")
        ax.set_xlim(0.5, n + 0.5)

    # Overall figure title
    fig.suptitle(title, fontweight="bold", fontsize=14)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


if combined_data:
    full_df = pd.concat(combined_data, ignore_index=True)
    print(f"\n[i] Total records: {len(full_df)}")

    # Prepare data for both download and upload
    df_download = full_df[["Operator", "Download (Mbps)"]].copy()
    df_download.columns = ["Operator", "Speed (Mbit/s)"]
    df_download["Type"] = "Download"
    df_download = df_download[df_download["Speed (Mbit/s)"] > 0]
    
    df_upload = full_df[["Operator", "Upload (Mbps)"]].copy()
    df_upload.columns = ["Operator", "Speed (Mbit/s)"]
    df_upload["Type"] = "Upload"
    df_upload = df_upload[df_upload["Speed (Mbit/s)"] > 0]
    
    # Combine both datasets
    df_combined = pd.concat([df_download, df_upload], ignore_index=True)
    
    # Create figure with 2 subplots side by side
    plot_dir = f"{GRAPHS_DIR}/{DATE}"
    os.makedirs(plot_dir, exist_ok=True)
    plot_path = f"{plot_dir}/{LOCATION}_throughput_combined.png"
    title = f"Throughput by Provider"
    # make_combined_boxplot(df_combined, title=title, out_path=plot_path)
    create_separate_plots(df_combined, title=title, out_path=plot_path)
    print(f"[✓] Combined throughput box plot saved to: {plot_path}")

else:
    print("[!] No data files found.")

