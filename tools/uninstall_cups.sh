#!/usr/bin/env bash
# Uninstaller script for E210 Thermal Printer CUPS driver
set -euo pipefail

echo "=== E210 Thermal Printer CUPS Uninstaller ==="

if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (or with sudo)."
    echo "Usage: sudo $0"
    exit 1
fi

# Remove CUPS printer queue
if command -v lpadmin >/dev/null 2>&1; then
    echo "1. Removing CUPS printer queue 'E210'..."
    lpadmin -x E210 2>/dev/null || true
fi

echo "2. Removing driver files..."
rm -f /usr/lib/cups/filter/rastertoe210
rm -f /usr/lib/cups/backend/e210
rm -f /usr/share/cups/model/e210.ppd
rm -rf /usr/share/e210

# Restart CUPS service if running
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet cups.service || systemctl is-active --quiet cups; then
        echo "Restarting CUPS service..."
        systemctl restart cups || true
    fi
fi

echo "=== Uninstallation Complete ==="
