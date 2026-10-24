#!/bin/bash
# Last Modifed: 2026-10-07
# masterScript.sh
#
# Runs one "round" of captures across all ISPs, then repeats.
# Around each round's Airtel run, it:
#   1. Waits 25s after first run starts for a device, then SSHes into a remote
#      server and starts a script there (in the background).
#   2. Waits for all ISPs to finish their run for this round.
#   3. Sends Ctrl+C (SIGINT) to the remote script.
#   4. Moves to the next round, repeating the SSH start/stop.

#  ------------------------- #  ------------------------- 
# Usage : Run this script from the root of the repo,
# Script name - followed by number of rounds. 
# e.g. `./scripts/dataCollectionScripts/masterScript_dummyVS.sh 2 Bharti501`
#

#
#  ------------------------- New User, please fill these in -------------------------
#

DATA_DIR="/Volumes/Untitled/5G_Measurements/data" #Replace "Volumes" with the appropriate path to your external drive
ROUNDS=${1:-1}   # how many rounds to run;
LOCATION=${2:-indoor_Shubham_JiaSarai}

#  ------------------------- Configuration -------------------------
SSH_USER="apple"
SSH_HOST="34.131.126.205"
SSH_KEY="scripts/dataCollectionScripts/gcp_key_nopass"          # reuse your existing key path if applicable
REMOTE_SCRIPT="/home/tmangla/5GMeasurements/v3_multiport/dummyConference.py"    # path to the script ON the remote server
REMOTE_VS_SCRIPT="/home/tmangla/5GMeasurements/v3_multiport/dummyStreaming.py"    # path to the VS script ON the remote server
REMOTE_SCRIPT_ARGS=""                    
REMOTE_PID_FILE="/tmp/remote_capture_script.pid"
REMOTE_LOG_FILE="/tmp/remote_capture_script.log"
DATE=$(date +%Y%m%d)
SSH_KEY_PASSPHRASE="apple"
SSH_CMD_TIMEOUT=30 
# ----------------------

ISP=('Airtel' 'Jio' 'Vodafone')
SSH_DELAY=25 


GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ------------------------- Pre-flight checks -------------------------
# Git does not preserve file permissions, so a freshly cloned key is usually
# 0644, which SSH refuses to use. Fix it here so it works on any laptop.
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}[SSH]${NC} Key not found at $SSH_KEY (run this script from the repo root)."
    exit 1
fi
chmod 600 "$SSH_KEY"

ssh_cmd() {
    local remote_cmd="$1"
    local ssh_opts=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)
 
    ssh "${ssh_opts[@]}" "$SSH_USER@$SSH_HOST" "$remote_cmd" &
    local cmd_pid=$!
 
    # Watcher: if cmd_pid is still alive after SSH_CMD_TIMEOUT seconds, kill it.
    (
        sleep "$SSH_CMD_TIMEOUT"
        kill -TERM "$cmd_pid" 2>/dev/null
    ) &
    local watcher_pid=$!
 
    wait "$cmd_pid" 2>/dev/null
    local exit_status=$?
 
    # Command finished (or was killed) — the watcher is no longer needed.
    kill "$watcher_pid" 2>/dev/null
    wait "$watcher_pid" 2>/dev/null
 
    return $exit_status
}

start_remote_script() {
    local round=$1
    echo -e "${YELLOW}[SSH]${NC} Round $round: starting remote script on $SSH_HOST"
    ssh_cmd "nohup python3 $REMOTE_SCRIPT $REMOTE_SCRIPT_ARGS > $REMOTE_LOG_FILE 2>&1 & echo \$! > $REMOTE_PID_FILE"
}

stop_remote_script() {
    local round=$1
    echo -e "${YELLOW}[SSH]${NC} Round $round: stopping remote script on $SSH_HOST (SIGINT)"
    ssh_cmd "pkill -9 -f dummyConference.py"
}

start_remote_VS_script() {
    local round=$1
    echo -e "${YELLOW}[SSH]${NC} Round $round: starting remote script on $SSH_HOST"
    ssh_cmd "nohup python3 $REMOTE_VS_SCRIPT $REMOTE_SCRIPT_ARGS > $REMOTE_LOG_FILE 2>&1 & echo \$! > $REMOTE_PID_FILE"
}

stop_remote_VS_script() {
    local round=$1
    echo -e "${YELLOW}[SSH]${NC} Round $round: stopping remote script on $SSH_HOST (SIGINT)"
    ssh_cmd "pkill -9 -f dummyStreaming.py"
}

for ((round = 1; round <= ROUNDS; round++)); do
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ROUND $round starting  |  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"

    PIDS=()
    SSH_STARTER_PID=""
    for isp in "${ISP[@]}"; do
        if [ "$isp" == "Airtel" ]; then
            deviceid="4a16d593"
        elif [ "$isp" == "Jio" ]; then
            deviceid="af523908"
        elif [ "$isp" == "Vodafone" ]; then
            deviceid="74e9f2fb"
        fi
        echo -e "Starting run for ISP: $isp, Location: ${LOCATION[0]}, DeviceID: $deviceid"
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        RUN_DIR="${DATA_DIR}/${isp}/${LOCATION[0]}/${DATE}/capture_$(printf '%03d' $round)_${TIMESTAMP}"
        echo -e $isp
        bash scripts/dataCollectionScripts/capture_diag_pcap_nsg_speedtest.sh "$RUN_DIR" "$deviceid" &
        PIDS+=($!)
        echo $PIDS

        if [ $isp == "${ISP[0]}" ]; then
            (
                sleep 15
                start_remote_script "$round"
            ) &
            SSH_STARTER_PID=$!
        fi
        sleep 30
    done

    echo -e "${YELLOW}[*]${NC} Waiting for all ISP captures in round $round to finish..."
    wait "${PIDS[@]}"

    # Make sure the SSH-start subshell has finished before we try to stop it
    if [ -n "$SSH_STARTER_PID" ]; then
        wait "$SSH_STARTER_PID" 2>/dev/null
    fi

    stop_remote_script "$round"

    sleep 20

    echo -e "${GREEN} Starting dummy Video Streaming Application "

    PIDS=()
    SSH_STARTER_PID=""

       for isp in "${ISP[@]}"; do
        if [ "$isp" == "Airtel" ]; then
            deviceid="4a16d593"
        elif [ "$isp" == "Jio" ]; then
            deviceid="af523908"
        elif [ "$isp" == "Vodafone" ]; then
            deviceid="74e9f2fb"
        fi
        echo -e "Starting run for ISP: $isp, Location: ${LOCATION[0]}, DeviceID: $deviceid"
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        RUN_DIR="${DATA_DIR}/${isp}/${LOCATION[0]}/${DATE}/capture_$(printf '%03d' $round)_${TIMESTAMP}/dummyVS"
        echo -e $isp
        bash scripts/dataCollectionScripts/capture_dummyVS.sh "$RUN_DIR" "$deviceid" &
        PIDS+=($!)
        echo $PIDS

        if [ $isp == "${ISP[0]}" ]; then
            (
                sleep 2
                start_remote_VS_script "$round"
            ) &
            SSH_STARTER_PID=$!
        fi
        sleep 30
    done

    echo -e "${YELLOW}[*]${NC} Waiting for all ISP captures in round $round to finish..."
    wait "${PIDS[@]}"

    # Make sure the SSH-start subshell has finished before we try to stop it
    if [ -n "$SSH_STARTER_PID" ]; then
        wait "$SSH_STARTER_PID" 2>/dev/null
    fi

    stop_remote_VS_script "$round"


    echo -e "${GREEN}[✓]${NC} Round $round complete."
    echo ""

    if [ $((round % 4)) -eq 0 ]; then
        echo -e "${YELLOW}[*]${NC} Waiting 5 minutes before starting next round..."
        sleep 300
    fi
done

echo -e "${GREEN}[✓]${NC} All $ROUNDS round(s) completed."