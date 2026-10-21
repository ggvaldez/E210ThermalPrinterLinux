#!/usr/bin/env bash
# Installer script for E210 Thermal Printer CUPS driver
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== E210 Thermal Printer CUPS Installer ==="

# Check root privileges
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (or with sudo) to install files to CUPS system directories."
    echo "Usage: sudo $0"
    exit 1
fi

# Detect CUPS paths dynamically
CUPS_SERVER_BIN=""
CUPS_DATA_DIR=""

if command -v cups-config >/dev/null 2>&1; then
    CUPS_SERVER_BIN="$(cups-config --serverbin 2>/dev/null || true)"
    CUPS_DATA_DIR="$(cups-config --datadir 2>/dev/null || true)"
fi

if [ -z "$CUPS_SERVER_BIN" ] || [ ! -d "$CUPS_SERVER_BIN" ]; then
    for candidate in /usr/lib/cups /usr/libexec/cups /usr/local/lib/cups /usr/local/libexec/cups; do
        if [ -d "$candidate" ]; then
            CUPS_SERVER_BIN="$candidate"
            break
        fi
    done
fi

if [ -z "$CUPS_DATA_DIR" ] || [ ! -d "$CUPS_DATA_DIR" ]; then
    for candidate in /usr/share/cups /usr/local/share/cups; do
        if [ -d "$candidate" ]; then
            CUPS_DATA_DIR="$candidate"
            break
        fi
    done
fi

if [ -z "$CUPS_SERVER_BIN" ] || [ ! -d "$CUPS_SERVER_BIN" ]; then
    echo "Error: Could not detect CUPS serverbin directory."
    echo "Checked: cups-config --serverbin, /usr/lib/cups, /usr/libexec/cups"
    echo "Please ensure the CUPS package is installed."
    exit 1
fi

if [ -z "$CUPS_DATA_DIR" ] || [ ! -d "$CUPS_DATA_DIR" ]; then
    echo "Error: Could not detect CUPS datadir directory."
    echo "Checked: cups-config --datadir, /usr/share/cups, /usr/local/share/cups"
    echo "Please ensure the CUPS package is installed."
    exit 1
fi

SHARED_TOOLS_DIR="/usr/share/e210/tools"

echo "Detected CUPS paths:"
echo "  Server binaries: $CUPS_SERVER_BIN"
echo "  Data directory:  $CUPS_DATA_DIR"
echo ""

echo "1. Installing helper tools to $SHARED_TOOLS_DIR..."
mkdir -p "$SHARED_TOOLS_DIR"
cp "$REPO_DIR/tools/e210_raster.py" "$SHARED_TOOLS_DIR/"
cp "$REPO_DIR/tools/probe_bluez.py" "$SHARED_TOOLS_DIR/"
cp "$REPO_DIR/tools/print_png.py" "$SHARED_TOOLS_DIR/"
chmod 755 "$SHARED_TOOLS_DIR"/*

echo "2. Installing CUPS raster filter..."
mkdir -p "$CUPS_SERVER_BIN/filter"
cp "$REPO_DIR/cups/rastertoe210" "$CUPS_SERVER_BIN/filter/rastertoe210"
chmod 755 "$CUPS_SERVER_BIN/filter/rastertoe210"
chown root:root "$CUPS_SERVER_BIN/filter/rastertoe210"

echo "3. Installing CUPS Bluetooth backend..."
mkdir -p "$CUPS_SERVER_BIN/backend"
cp "$REPO_DIR/cups/e210" "$CUPS_SERVER_BIN/backend/e210"
chmod 755 "$CUPS_SERVER_BIN/backend/e210"
chown root:root "$CUPS_SERVER_BIN/backend/e210"

echo "4. Installing PPD file..."
mkdir -p "$CUPS_DATA_DIR/model"
cp "$REPO_DIR/ppd/e210.ppd" "$CUPS_DATA_DIR/model/e210.ppd"
chmod 644 "$CUPS_DATA_DIR/model/e210.ppd"

# Verify PPD with cupstestppd if available
if command -v cupstestppd >/dev/null 2>&1; then
    echo "Validating installed PPD with cupstestppd..."
    cupstestppd "$CUPS_DATA_DIR/model/e210.ppd"
fi

# Restart CUPS daemon or socket if running
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet cups.service || systemctl is-active --quiet cups; then
        echo "Restarting CUPS service..."
        systemctl restart cups || true
    fi
fi

# Add the printer queue
if command -v lpadmin >/dev/null 2>&1; then
    echo "5. Configuring CUPS printer queue 'E210'..."
    lpadmin -p E210 -E \
        -v e210://auto \
        -P "$CUPS_DATA_DIR/model/e210.ppd" \
        -D "E210 Bluetooth Thermal Printer" \
        -L "Bluetooth"
    echo "Printer queue 'E210' created and enabled."
    echo "Device URI: e210://auto"
fi

echo ""
echo "=== Installation Complete! ==="
echo "You can now print to 'E210' from any application or via CLI:"
echo "    lp -d E210 document.pdf"
echo "    lp -d E210 -o media=Label50x50mm -o Darkness=8 label.pdf"
