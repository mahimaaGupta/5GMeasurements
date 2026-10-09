#
# Usage : python3 scripts/analyzeThroughput.py
#

import os, re
import glob
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP

SERVER_IP = "34.131.126.205"

def process_pcap(pcap_path):
    """
    Reads a PCAP file and computes 1-second throughput separately for
    download (server -> client) and upload (client -> server).

    Returns a DataFrame with:
        Timestamp
        Download (Mbps)
        Upload (Mbps)
    """

    download_records = []
    upload_records = []

    with PcapReader(str(pcap_path)) as pcap:
        for pkt in pcap:

            if IP not in pkt:
                continue

            if not hasattr(pkt, "time"):
                continue
            timestamp = float(pkt.time)
            length = pkt.wirelen if hasattr(pkt, "wirelen") and pkt.wirelen else len(pkt)

            ip = pkt[IP]
            # Download: server -> client
            if ip.src == SERVER_IP:
                download_records.append(
                    {
                        "timestamp": timestamp,
                        "length": length,
                    }
                )

            # Upload: client -> server
            elif ip.dst == SERVER_IP:
                upload_records.append(
                    {
                        "timestamp": timestamp,
                        "length": length,
                    }
                )
    if not download_records and not upload_records:
        return pd.DataFrame(
            columns=[
                "Timestamp",
                "Download (Mbps)",
                "Upload (Mbps)",
            ]
        )

    # -------------------------
    # Download throughput
    # -------------------------
    if download_records:
        df_download = pd.DataFrame(download_records)
        df_download["datetime"] = pd.to_datetime(
            df_download["timestamp"], unit="s"
        )
        df_download.set_index("datetime", inplace=True)

        download = (
            df_download["length"]
            .resample("1s")
            .sum()
            * 8
            / 1_000_000
        )
    else:
        download = pd.Series(dtype=float)

    # -------------------------
    # Upload throughput
    # -------------------------
    if upload_records:
        df_upload = pd.DataFrame(upload_records)
        df_upload["datetime"] = pd.to_datetime(
            df_upload["timestamp"], unit="s"
        )
        df_upload.set_index("datetime", inplace=True)

        upload = (
            df_upload["length"]
            .resample("1s")
            .sum()
            * 8
            / 1_000_000
        )
    else:
        upload = pd.Series(dtype=float)

    # Merge both series
    result = pd.concat(
        [download.rename("Download (Mbps)"),
         upload.rename("Upload (Mbps)")],
        axis=1,
    ).fillna(0)

    result = result.reset_index()
    result.rename(columns={"datetime": "Timestamp"}, inplace=True)

    # Convert to elapsed seconds from the beginning of the capture
    result["Timestamp"] = ( result["Timestamp"] - result["Timestamp"].iloc[0]).dt.total_seconds().astype(int)

    return result

def parse_ndt_log(file_content):
    """
    Parses NDT speed test text content and extracts key metrics into a structured dictionary.
    """
    # 1. Extract Header Metadata & Summary
    download = re.search(r"^Download\s*:\s*(.+)$", file_content, re.MULTILINE).group(1).strip()
    upload = re.search(r"^Upload\s*:\s*(.+)$", file_content, re.MULTILINE).group(1).strip()

    return download, upload


def analyzeThroughput(isp):
    LOCATION = "Bharti501"
    DATE="20261006"
    data_dir = Path("/Volumes/Untitled/5G_Measurements/data/" + isp + "/" + LOCATION + "/" + DATE)
    results_dir = Path("results/Throughput/" + isp + "/" + LOCATION + "/" + DATE)
    graphs_dir = Path("graphs/Throughput/" + isp + "/" + LOCATION + "/" + DATE)
    

    pcap_files = glob.glob(
        os.path.join(data_dir, "**","*.pcap"),
        # os.path.join(data_dir, "*.pcap"),
        recursive=True,
    )
    txt_files = glob.glob(
        os.path.join(data_dir, "**", "*.txt"),
        # os.path.join(data_dir, "*.txt"),
        recursive=True,
    )

    if not pcap_files:
        print(f"No PCAP files found in {data_dir}")
        return

    print(f"Found {len(pcap_files)} PCAP file(s).\n")

    for pcap_str_path in pcap_files:

        pcap_path = Path(pcap_str_path)
        down, up = 0, 0
        rel_path = pcap_path.relative_to(data_dir)

        csv_out_path = (
            results_dir
            / rel_path.parent
            / f"{pcap_path.stem}.csv"
        )

        graph_out_path = (
            graphs_dir
            / rel_path.parent
            / f"{pcap_path.stem}.png"
        )

        csv_out_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        graph_out_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        match = re.search(r"\d{8}_\d{6}", pcap_path.stem)
        speedtest_result_path = str(data_dir) + '/' + str(rel_path.parent) + '/ndt7_speedtest_' + match.group(0) + '.txt'
        if speedtest_result_path in txt_files:
            path = Path(speedtest_result_path)
            content = path.read_text()
            down, up = parse_ndt_log(content)

        print(f"Processing: {pcap_path}")

        try:
            df = process_pcap(pcap_path)
        
        except Exception as e:
            print(f"\n[!] ERROR encountered while processing PCAP: {pcap_path}")
            print(f"    Details: {type(e).__name__}: {e}\n")
            continue

        if df.empty:
            print(
                f"  -> Warning: No IP packets found in {pcap_path.name}"
            )
            continue

        df.to_csv(csv_out_path, index=False)

        print(f"  -> CSV saved: {csv_out_path}")

        avg_download = df["Download (Mbps)"].mean()
        avg_upload = df["Upload (Mbps)"].mean()

        plt.figure(figsize=(12, 5))

        plt.plot(
            df["Timestamp"],
            df["Download (Mbps)"],
            label="Download" + f" (avg = {avg_download:.2f} Mbps)",
            linewidth=2,
            marker="o",
            markersize=3,
        )

        plt.plot(
            df["Timestamp"],
            df["Upload (Mbps)"],
            label="Upload" + f" (avg = {avg_upload:.2f} Mbps)",
            linewidth=2,
            marker="s",
            markersize=3,
        )

        plt.title(
            f"{pcap_path}\n"
            f"Download = {down} | "
            f"Upload = {up}"
        )
        plt.xlabel("Timestamp")
        plt.ylabel("Throughput (Mbps)")
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.legend()
        plt.xlim(0,310)
        plt.ylim(0,6)

        if len(df) > 20:
            step = max(1, len(df) // 10)
            plt.xticks(
                ticks=range(0, len(df), step),
                labels=df["Timestamp"].iloc[::step],
                ha="right",
            )
        else:
            plt.xticks(rotation=45, ha="right")

        plt.tight_layout()
        plt.savefig(graph_out_path, dpi=300)
        plt.close()

        print(f"  -> Graph saved: {graph_out_path}\n")

    print("Processing complete!")


if __name__ == "__main__":
    ISPs = ["Airtel", "Jio", "Vodafone"]
    # ISPs = [ "Jio", "Vodafone"]
    for isp in ISPs:
        analyzeThroughput(isp=isp)