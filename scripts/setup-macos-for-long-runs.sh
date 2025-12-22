#!/bin/bash
# Setup macOS for Long-Running Autonomous Sessions
# This script configures macOS to prevent sleep and Docker throttling

set -e

echo "=========================================="
echo "macOS Configuration for Long-Running Sessions"
echo "=========================================="
echo ""

# Check if running as root (for sudo commands)
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please run as normal user (script will request sudo as needed)"
    exit 1
fi

echo "This script will configure your Mac to prevent:"
echo "  - System sleep"
echo "  - Display sleep"
echo "  - Power Nap"
echo "  - Screen lock"
echo "  - Scheduled sleep/wake events"
echo ""
echo "These settings are CRITICAL to prevent Docker Desktop from being throttled."
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "📋 Current sleep settings:"
pmset -g | grep -i sleep || true
echo ""

echo "🔧 Disabling system sleep..."
sudo pmset -a disablesleep 1

echo "🔧 Disabling display sleep..."
sudo pmset -a displaysleep 0

echo "🔧 Disabling Power Nap..."
sudo pmset -a powernap 0

echo "🔧 Cancelling scheduled sleep/wake events..."
sudo pmset schedule cancelall

echo "🔧 Disabling screen lock..."
sudo sysadminctl -screenLock off 2>/dev/null || {
    echo "⚠️  Could not disable screen lock via command line."
    echo "   Please manually set: System Settings → Lock Screen → 'Require password' → Never"
}

echo ""
echo "✅ Configuration complete!"
echo ""
echo "📋 New sleep settings:"
pmset -g | grep -i sleep || true
echo ""

echo "💡 To re-enable sleep when done, run:"
echo "   ./scripts/restore-macos-sleep.sh"
echo ""
echo "🐳 Docker Desktop should now run without throttling during long sessions."
echo ""
