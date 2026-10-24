#!/bin/bash
# Captures PCAP and QMDL logs strictly for the duration of a speedtest and dummy VC experiment
# while running Network Logger Application in the foreground.
#
# Usage: bash capture_diag_pcaps_speedtest.sh [output_dir] [Device ID]
#

# ==============================================================================
#                                   CONFIGURATION
# ==============================================================================
set -e
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR=$1
DEVICEID=$2
MAX_SIZE=1000  # MB
PACKAGE_NAME="com.example.networklogger"
MAIN_ACTIVITY="com.example.networklogger.MainActivity"
STARTBUTTON_X=500
STARTBUTTON_Y=2455
STOPBUTTON_X=788
STOPBUTTON_Y=2455

# Micro-container variables (on the device)
WORKDIR="/data/local/tmp"
ROOTFS="$WORKDIR/fakeroot"
DIAG_DIR_MAIN="/sdcard/diag_temp_VS"
NETWORK_LOGGER_APP_DIR="/sdcard/Download/NetworkLogger"


# ==============================================================================
#           ---- Helpers for starting/stopping the QMDL logger ----
# ==============================================================================

 
start_qmdl_logger() {
    # $1 = on-device output directory for this session
    local out_dir="$1"
    adb -s $DEVICEID shell su -c "mkdir -p $out_dir"
    adb -s $DEVICEID shell su -c "/vendor/bin/diag_mdlog -o $out_dir -s ${MAX_SIZE} -f /vendor/odm/etc/modem_rf.cfg -c" &>/dev/null &
}
 
is_qmdl_logger_running() {
    if adb -s $DEVICEID shell su -c 'pgrep -x diag_mdlog' 2>/dev/null | grep -q .; then
        return 0
    fi
    adb -s $DEVICEID shell su -c 'ps -A 2>/dev/null | grep -v grep | grep -q diag_mdlog'
}
 
stop_qmdl_logger_graceful() {
    adb -s "$DEVICEID" shell su -c 'pkill -INT diag_mdlog' 2>/dev/null || true
    local waited=0
    local max_wait=15
    while [ "$waited" -lt "$max_wait" ] && is_qmdl_logger_running; do
        sleep 1
        waited=$((waited + 1))
    done
    
    # Allow buffer flushing to disk
    sleep 5
    
    if is_qmdl_logger_running; then
        echo -e "${YELLOW}[!]${NC} diag_mdlog did not exit cleanly within ${max_wait}s; forcing exit."
        adb -s "$DEVICEID" shell su -c 'pkill -9 diag_mdlog' 2>/dev/null || true
    fi
}
kill_qmdl_logger() {
    adb -s $DEVICEID shell su -c 'pkill -9 diag_mdlog' 2>/dev/null || true
}


# ==============================================================================
#                              ---- Set Up Loggers ----
# ==============================================================================

echo -e "${GREEN}═════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  OnePlus 11R DIAG & PCAP Capture (Dummy VS with Network Logger)${NC}"
echo -e "${GREEN}═════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if device is connected & rooted
echo -e "${YELLOW}[*]${NC} Checking for connected device and root access..."
if ! adb -s $DEVICEID devices | grep -q -w "device"; then
    echo -e "${RED}[✗]${NC} No device found! Please connect via USB."
    exit 1
fi
if ! adb -s $DEVICEID shell su -c 'id' 2>/dev/null | grep -q "uid=0"; then
    echo -e "${RED}[✗]${NC} Root access not available on device!"
    exit 1
fi
echo -e "${GREEN}[✓]${NC} Device connected and rooted"

# Start DIAG router
echo -e "${YELLOW}[*]${NC} Clearing any stale diag_mdlog sessions..."
adb -s $DEVICEID shell su -c 'pkill -9 diag_mdlog' 2>/dev/null || true
sleep 1
echo -e "${YELLOW}[*]${NC} Starting DIAG router service..."
adb -s $DEVICEID shell su -c 'start vendor.diag-router' >/dev/null 2>&1
sleep 1
if ! adb -s $DEVICEID shell su -c 'getprop init.svc.vendor.diag-router' | grep -q "running"; then
    echo -e "${RED}[✗]${NC} Failed to start DIAG router service"
    exit 1
fi

# Clean up old logs & Set up directories
echo -e "${YELLOW}[*]${NC} Preparing directories and Micro-Container..."
adb -s $DEVICEID shell su -c "rm -rf $DIAG_DIR_MAIN" >/dev/null 2>&1 || true
adb -s $DEVICEID shell su -c "mkdir -p $DIAG_DIR_MAIN"
mkdir -p "$OUTPUT_DIR"

# ==============================================================================
#                         ---- Setup Microcontainer  ----
# ==============================================================================

# Build the micro-container for the speedtest binary via adb -s $DEVICEID using a Here-Doc
adb -s $DEVICEID shell su <<EOF
umount $ROOTFS/dev 2>/dev/null
umount $ROOTFS/proc 2>/dev/null
umount $ROOTFS/sys 2>/dev/null
rm -rf $ROOTFS

mkdir -p $ROOTFS/etc/ssl/certs $ROOTFS/dev $ROOTFS/proc $ROOTFS/sys
echo 'nameserver 8.8.8.8' > $ROOTFS/etc/resolv.conf

if [ ! -f $WORKDIR/cacert.pem ]; then
    curl -s -k -o $WORKDIR/cacert.pem https://curl.se/ca/cacert.pem
fi
cp $WORKDIR/cacert.pem $ROOTFS/etc/ssl/certs/ca-certificates.crt

chmod +x $WORKDIR/ndt7-client
cp $WORKDIR/speedtest $ROOTFS/

mount -o bind /dev $ROOTFS/dev
mount -o bind /proc $ROOTFS/proc
mount -o bind /sys $ROOTFS/sys
EOF
# ==============================================================================
#                    ---- Start Network Logger Application  ----
# ==============================================================================

echo -e "${YELLOW}[✓]${NC} Ensuring screen is awake..."
adb -s $DEVICEID shell input keyevent KEYCODE_WAKEUP
adb -s $DEVICEID shell wm dismiss-keyguard > /dev/null 2>&1
echo -e "${GREEN}[✓]${NC} Starting app: $PACKAGE_NAME..."
adb -s $DEVICEID shell am start -S -n "$PACKAGE_NAME/$MAIN_ACTIVITY" > /dev/null
sleep 3
adb -s $DEVICEID shell input swipe $STARTBUTTON_X $STARTBUTTON_Y 800 500 400
sleep 5
echo -e "${YELLOW}[✓]${NC} Tapping button at ($STARTBUTTON_X, $STARTBUTTON_Y)..."
adb -s $DEVICEID shell input tap $STARTBUTTON_X $STARTBUTTON_Y


# ==============================================================================
#                 ---- Run Dummy VS experiment & Capture QMDL logs----
# ==============================================================================

# Start Background PCAP
ACTIVE_IFACE=$(adb -s $DEVICEID shell su -c 'ip route get 8.8.8.8 2>/dev/null' | sed -n 's/.*dev \([^ ]*\).*/\1/p' | head -n 1 | tr -d '\r')
ACTIVE_IFACE=${ACTIVE_IFACE:-any}
echo -e "${GREEN}[✓]${NC} Starting PCAP on interface: $ACTIVE_IFACE"
PCAP_FILE="/sdcard/diag_temp_VS/capture_$TIMESTAMP.pcap"
adb -s $DEVICEID shell su -c "tcpdump -i $ACTIVE_IFACE -w $PCAP_FILE" &>/dev/null &
TCPDUMP_PID=$!

# Start Background DIAG Log
echo -e "${GREEN}[✓]${NC} Starting DIAG Modem Logger for dummy-conference session..."
start_qmdl_logger "$DIAG_DIR_MAIN"

# Run the Dummy Video Streaming Emulation in Background
echo -e "Starting Dummy Video Streaming Emulation in background..."
EMULATION_SCRIPT_PATH="/storage/emulated/0"
TERMUX_PREFIX="/data/data/com.termux/files/usr"
adb -s $DEVICEID shell "su -c 'env PATH=\$PATH:${TERMUX_PREFIX}/bin LD_LIBRARY_PATH=${TERMUX_PREFIX}/lib timeout 300 python ${EMULATION_SCRIPT_PATH}/dummyStreaming.py'" || true

# Stop Captures Immediately
echo -e "${YELLOW}[*]${NC} Dummy VC experiment complete. Stopping captures and apps..."
adb -s $DEVICEID shell su -c 'pkill -INT diag_mdlog' 2>/dev/null || true
sleep 1
adb -s $DEVICEID shell su -c 'pkill -9 diag_mdlog' 2>/dev/null || true
adb -s $DEVICEID shell su -c 'pkill tcpdump' 2>/dev/null || true
kill $TCPDUMP_PID 2>/dev/null || true
kill $DIAG_PID 2>/dev/null || true

# ==============================================================================
#                 ---- Stop & Kill Network Logger Application  ----
# ==============================================================================
adb -s $DEVICEID shell input swipe $STARTBUTTON_X $STARTBUTTON_Y 800 500 400
sleep 5
echo -e "${YELLOW}[✓]${NC} Tapping button at ($STOPBUTTON_X, $STOPBUTTON_Y)..."
adb -s $DEVICEID shell input tap $STOPBUTTON_X $STOPBUTTON_Y
sleep 5
# Force-close the application
echo -e "${GREEN}[✓]${NC} Killing app: $PACKAGE_NAME..."
adb -s $DEVICEID shell am force-stop "$PACKAGE_NAME"
adb -s $DEVICEID shell am stack remove "$PACKAGE_NAME" 2>/dev/null || true


# ==============================================================================
#                    ---- Tear Down Microcontainer & Pull Logs ----
# ==============================================================================

# Tear down the container safely
adb -s $DEVICEID shell su <<EOF
umount $ROOTFS/dev 2>/dev/null
umount $ROOTFS/proc 2>/dev/null
umount $ROOTFS/sys 2>/dev/null
EOF
 
# Pull remaining (dummy-streaming session) data
echo -e "${YELLOW}[*]${NC} Pulling dummy-streaming data from device..."
adb -s $DEVICEID pull "${DIAG_DIR_MAIN}/." "${OUTPUT_DIR}/" >/dev/null 2>&1
adb -s $DEVICEID pull "${NETWORK_LOGGER_APP_DIR}/." "${OUTPUT_DIR}/" >/dev/null 2>&1
adb -s $DEVICEID shell su -c "rm -rf $DIAG_DIR_MAIN" >/dev/null 2>&1
adb -s $DEVICEID shell su -c "rm -rf $NETWORK_LOGGER_APP_DIR" >/dev/null 2>&1

FILECOUNT=$(ls -1 "${OUTPUT_DIR}"/*.qmdl* 2>/dev/null | wc -l | tr -d ' ')
if [ "$FILECOUNT" -eq "0" ]; then
    echo -e "${RED}[✗]${NC} Warning: No DIAG files were saved successfully."
else
    echo -e "${GREEN}[✓]${NC} Data saved to: ${OUTPUT_DIR}/"
fi