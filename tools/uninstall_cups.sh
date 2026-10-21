#!/usr/bin/env bash
# Uninstaller script for E210 Thermal Printer CUPS driver
set -euo pipefail

echo "=== E210 Thermal Printer CUPS Uninstaller ==="

if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (or with sudo)."
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

# Remove CUPS printer queue
if command -v lpadmin >/dev/null 2>&1; then
    echo "1. Removing CUPS printer queue 'E210'..."
    lpadmin -x E210 2>/dev/null || true
fi

echo "2. Removing driver files..."
if [ -n "$CUPS_SERVER_BIN" ]; then
    rm -f "$CUPS_SERVER_BIN/filter/rastertoe210"
    rm -f "$CUPS_SERVER_BIN/backend/e210"
fi
if [ -n "$CUPS_DATA_DIR" ]; then
    rm -f "$CUPS_DATA_DIR/model/e210.ppd"
fi
rm -rf /usr/share/e210

# Restart CUPS service if running
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet cups.service || systemctl is-active --quiet cups; then
        echo "Restarting CUPS service..."
        systemctl restart cups || true
    fi
fi

echo "=== Uninstallation Complete ==="
