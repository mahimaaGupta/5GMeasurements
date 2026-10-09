#!/usr/bin/env python3
"""
Create separate box plots for Download and Upload throughput by operator.

Reads speedtest CSVs for each operator and creates two separate figures:
  - Download Speed (Mbit/s) across operators
  - Upload Speed (Mbit/s) across operators

Each figure shows box plots with median, quartiles, min-max range, and means.
"""

from pathlib import Path
import os, re
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Configuration
DATA_DIR = "/Volumes/Untitled/5G_Measurements/data"
OPERATORS = ["Airtel", "Jio", "Vodafone"]
DATE="20261006"
LOCATION="Bharti501"
RESULT_DIR = "results/speedtest/"
GRAPHS_DIR= "graphs/speedtest"

# Plotting convention
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    "font.serif": ["Times"],
    "font.size": 10,
    "figure.figsize": (10, 6),
    "legend.fontsize": 10,
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
    "lines.linewidth": 0.75,
    "grid.linewidth": 0.25,
    "xtick.major.width": 0.25,
    "ytick.major.width": 0.25,
    "ps.usedistiller": "xpdf",
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})

# 1. Parse text files and generate CSV for each operator
def parse_csv():
    for op in OPERATORS:
        op_dir = os.path.join(DATA_DIR, op, LOCATION, DATE)
        if not os.path.exists(op_dir):
            print("Path Issue")
            continue

        records = []
        
        # Traverse through operator and date subdirectories
        for root, _, files in os.walk(op_dir):
            for file in files:
                if file.startswith("ndt7_speedtest") and file.endswith(".txt"):
                    file_path = os.path.join(root, file)
                    
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract Timestamp, Download, and Upload
                    ts_match = re.search(r"^Timestamp\s*:\s*(.+)$", content, re.MULTILINE)
                    dl_match = re.search(r"^Download\s*:\s*(.+)$", content, re.MULTILINE)
                    ul_match = re.search(r"^Upload\s*:\s*(.+)$", content, re.MULTILINE)

                    if ts_match and dl_match and ul_match:
                        timestamp = ts_match.group(1).strip()
                        
                        # Extract numeric floating values for plotting
                        dl_speed = float(re.search(r"([\d.]+)", dl_match.group(1).strip()).group(1))
                        ul_speed = float(re.search(r"([\d.]+)", ul_match.group(1).strip()).group(1))

                        records.append({
                            "Timestamp": timestamp,
                            "Download Speed (Mbit/s)": dl_speed,
                            "Upload Speed (Mbit/s)": ul_speed
                        })

        # Save to CSV per operator
        df_op = pd.DataFrame(records)
        csv_filename = f"{DATE}_speedtest.csv"
        csv_path = os.path.join(RESULT_DIR, op, LOCATION, csv_filename)
        csv_dir = os.path.dirname(csv_path)
        # Create the directory if it doesn't already exist
        os.makedirs(csv_dir, exist_ok=True)
        df_op.to_csv(csv_path, index=False)
        print(f"Saved {len(df_op)} records to {csv_path}")

# 2. Read and combine data from all operators
parse_csv()
combined_data = []
for op in OPERATORS:
    csv_filename = f"{DATE}_speedtest.csv"
    csv_path = os.path.join(RESULT_DIR, op, LOCATION, csv_filename)
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        df["Operator"] = op
        combined_data.append(df)
        print(f"[✓] Loaded {op}: {len(df)} records")
    else:
        print(f"[!] File not found: {csv_path}")

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
    df_download = full_df[["Operator", "Download Speed (Mbit/s)"]].copy()
    df_download.columns = ["Operator", "Speed (Mbit/s)"]
    df_download["Type"] = "Download"
    df_download = df_download[df_download["Speed (Mbit/s)"] > 0]
    
    df_upload = full_df[["Operator", "Upload Speed (Mbit/s)"]].copy()
    df_upload.columns = ["Operator", "Speed (Mbit/s)"]
    df_upload["Type"] = "Upload"
    df_upload = df_upload[df_upload["Speed (Mbit/s)"] > 0]
    
    # Combine both datasets
    df_combined = pd.concat([df_download, df_upload], ignore_index=True)
    
    # Create figure with 2 subplots side by side
    plot_dir = f"{GRAPHS_DIR}/{LOCATION}/{DATE}"
    os.makedirs(plot_dir, exist_ok=True)
    plot_path = f"{plot_dir}/throughput_combined.png"
    title = f"Throughput by Provider"
    # make_combined_boxplot(df_combined, title=title, out_path=plot_path)
    create_separate_plots(df_combined, title=title, out_path=plot_path)
    print(f"[✓] Combined throughput box plot saved to: {plot_path}")

else:
    print("[!] No data files found.")

# if combined_data:
#     full_df = pd.concat(combined_data, ignore_index=True)
#     print(f"\n[i] Total records: {len(full_df)}")

#     # ---- DOWNLINK (Download Speed) ----
#     print("\n[*] Creating Downlink (Download) plot...")
    
#     df_download = full_df[["Operator", "Download Speed (Mbit/s)"]].copy()
#     df_download.columns = ["Operator", "Speed (Mbit/s)"]
#     df_download = df_download[df_download["Speed (Mbit/s)"] > 0]  # Remove zero/negative values
    
#     fig_dl, ax_dl = plt.subplots(figsize=(10, 6))
    
#     sns.boxplot(
#         x="Operator",
#         y="Speed (Mbit/s)",
#         data=df_download,
#         color="#348ABD",  # Blue
#         showfliers=False,
#         showmeans=True,
#         meanprops={
#             "marker": "^",
#             "markerfacecolor": "green",
#             "markeredgecolor": "green",
#             "markersize": 8
#         },
#         ax=ax_dl,
#         width=0.6
#     )
    
#     ax_dl.set_title("Downlink Throughput Distribution by Operator", fontweight="bold", fontsize=12)
#     ax_dl.set_xlabel("Operator", fontweight="bold")
#     ax_dl.set_ylabel("Speed (Mbit/s)", fontweight="bold")
    
#     # Styling
#     ax_dl.tick_params(axis="both", which="both")
#     for label in ax_dl.get_xticklabels() + ax_dl.get_yticklabels():
#         label.set_fontweight("bold")
    
#     ax_dl.grid(True, which="major", linestyle="--", alpha=0.6, axis="y")
#     ax_dl.grid(True, which="minor", linestyle=":", alpha=0.3, axis="y")
    
#     fig_dl.tight_layout()
    
#     # Save downlink plot
#     dl_graph_path = GRAPHS_DIR + LOCATION + "/" + DATE +"/download_throughput_boxplot.png"
#     os.makedirs(os.path.dirname(dl_graph_path), exist_ok=True)
#     fig_dl.savefig(dl_graph_path, dpi=300, bbox_inches="tight")
#     plt.close(fig_dl)
#     print(f"[✓] Downlink plot saved to: {dl_graph_path}")

#     # ---- UPLINK (Upload Speed) ----
#     print("\n[*] Creating Uplink (Upload) plot...")
    
#     df_upload = full_df[["Operator", "Upload Speed (Mbit/s)"]].copy()
#     df_upload.columns = ["Operator", "Speed (Mbit/s)"]
#     df_upload = df_upload[df_upload["Speed (Mbit/s)"] > 0]  # Remove zero/negative values
    
#     fig_ul, ax_ul = plt.subplots(figsize=(10, 6))
    
#     sns.boxplot(
#         x="Operator",
#         y="Speed (Mbit/s)",
#         data=df_upload,
#         color="#E24A33",  # Orange
#         showfliers=False,
#         showmeans=True,
#         meanprops={
#             "marker": "^",
#             "markerfacecolor": "green",
#             "markeredgecolor": "green",
#             "markersize": 8
#         },
#         ax=ax_ul,
#         width=0.6
#     )
    
#     ax_ul.set_title("Uplink Throughput Distribution by Operator", fontweight="bold", fontsize=12)
#     ax_ul.set_xlabel("Operator", fontweight="bold")
#     ax_ul.set_ylabel("Speed (Mbit/s)", fontweight="bold")
    
#     # Styling
#     ax_ul.tick_params(axis="both", which="both")
#     for label in ax_ul.get_xticklabels() + ax_ul.get_yticklabels():
#         label.set_fontweight("bold")
    
#     ax_ul.grid(True, which="major", linestyle="--", alpha=0.6, axis="y")
#     ax_ul.grid(True, which="minor", linestyle=":", alpha=0.3, axis="y")
    
#     fig_ul.tight_layout()
    
#     # Save uplink plot
#     ul_graph_path = GRAPHS_DIR + LOCATION + "/" + DATE +"/upload_throughput_boxplot.png"
#     os.makedirs(os.path.dirname(ul_graph_path), exist_ok=True)
#     fig_ul.savefig(ul_graph_path, dpi=300, bbox_inches="tight")
#     plt.close(fig_ul)
#     print(f"[✓] Uplink plot saved to: {ul_graph_path}")
    
#     print(f"\n[✓] Done. Both plots created successfully.")

# else:
#     print("[!] No data files found.")