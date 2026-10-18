#!/usr/bin/env bash
# Automated installation & setup script for Token Monitor for Claude Code
# Works on systems with KDE Plasma 6 and Python 3
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLET_ID="com.buellsunited.TokenMonitor"
TARGET_DIR="$HOME/.local/share/plasma/plasmoids/$APPLET_ID"
BACKEND_TARGET_DIR="$HOME/.local/share/token-monitor"
LEGACY_BACKEND_DIR="$HOME/.local/share/kde-claude-stat"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
DBUS_USER_DIR="$HOME/.local/share/dbus-1/services"

WITH_HOOK=false
for arg in "$@"; do
    case "$arg" in
        --with-hook)
            WITH_HOOK=true
            ;;
        --help|-h)
            echo "Usage: ./install.sh [--with-hook]"
            echo "  --with-hook   Integrate collector into ~/.claude/settings.json statusline"
            exit 0
            ;;
    esac
done

echo "=========================================================="
echo "  Token Monitor for Claude Code Installation & Setup"
echo "=========================================================="

# 0. Pre-check prerequisites
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python 3 is required but not found in PATH!" >&2
    exit 1
fi

if [ ! -f "$HOME/.claude/.credentials.json" ] && [ -z "${CLAUDE_CONFIG_DIR:-}" ]; then
    echo "NOTE: No Claude credentials found at ~/.claude/.credentials.json."
    echo "The widget requires an active login to Claude Code ('claude login')."
    echo ""
fi

# 1. Build translations
if [ -x "$SCRIPT_DIR/build_translations.sh" ]; then
    echo "--> 1. Building translations (gettext)..."
    "$SCRIPT_DIR/build_translations.sh"
fi

# 2. Register widget in KDE Plasma
echo "--> 2. Installing plasmoid to: $TARGET_DIR"
LEGACY_APPLET_ID="com.buellsunited.claudestat"
rm -rf "$HOME/.local/share/plasma/plasmoids/$LEGACY_APPLET_ID"
rm -f "$HOME/.local/share/locale/de/LC_MESSAGES/plasma_applet_$LEGACY_APPLET_ID.mo"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/$LEGACY_APPLET_ID.svg"

# Migrate legacy plugin ID in plasma config if present
if [ -f "$HOME/.config/plasma-org.kde.plasma.desktop-appletsrc" ]; then
    sed -i "s/plugin=$LEGACY_APPLET_ID/plugin=$APPLET_ID/g" "$HOME/.config/plasma-org.kde.plasma.desktop-appletsrc" 2>/dev/null || true
fi
if [ -f "$HOME/.config/plasmawindowedrc" ]; then
    sed -i "s/plugin=$LEGACY_APPLET_ID/plugin=$APPLET_ID/g" "$HOME/.config/plasmawindowedrc" 2>/dev/null || true
fi

# Sync backend and scripts into package for complete autarky
rm -rf "$SCRIPT_DIR/package/contents/backend"
cp -r "$SCRIPT_DIR/backend" "$SCRIPT_DIR/package/contents/"
rm -rf "$SCRIPT_DIR/package/contents/backend/__pycache__"
cp "$SCRIPT_DIR/collect.sh" "$SCRIPT_DIR/package/contents/collect.sh"
chmod +x "$SCRIPT_DIR/package/contents/collect.sh"
chmod +x "$SCRIPT_DIR/package/contents/scripts/start_daemon.sh"

mkdir -p "$(dirname "$TARGET_DIR")"
rm -rf "$TARGET_DIR"
cp -r "$SCRIPT_DIR/package" "$TARGET_DIR"

# Optional registration in user locale directory for KDE KI18n
USER_LOCALE_DIR="$HOME/.local/share/locale/de/LC_MESSAGES"
DOMAIN="plasma_applet_$APPLET_ID"
if [ -f "$SCRIPT_DIR/package/contents/locale/de/LC_MESSAGES/$DOMAIN.mo" ]; then
    mkdir -p "$USER_LOCALE_DIR"
    cp "$SCRIPT_DIR/package/contents/locale/de/LC_MESSAGES/$DOMAIN.mo" "$USER_LOCALE_DIR/$DOMAIN.mo"
fi

# Register icon in user icon theme (for Plasma Widget Explorer)
USER_ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
if [ -f "$SCRIPT_DIR/icons/$APPLET_ID.svg" ]; then
    echo "--> Installing applet icon to: $USER_ICON_DIR"
    mkdir -p "$USER_ICON_DIR"
    cp "$SCRIPT_DIR/icons/$APPLET_ID.svg" "$USER_ICON_DIR/$APPLET_ID.svg"
    if command -v kbuildsycoca6 >/dev/null 2>&1; then
        kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    fi
fi

# 3. Install backend files persistently to ~/.local/share/token-monitor/
echo "--> 3. Installing backend to: $BACKEND_TARGET_DIR"
mkdir -p "$BACKEND_TARGET_DIR"

# Auto-migrate database from legacy location if present
if [ -f "$LEGACY_BACKEND_DIR/history.db" ] && [ ! -f "$BACKEND_TARGET_DIR/history.db" ]; then
    echo "--> Migrating database from $LEGACY_BACKEND_DIR/history.db to $BACKEND_TARGET_DIR/history.db..."
    cp -p "$LEGACY_BACKEND_DIR/history.db" "$BACKEND_TARGET_DIR/history.db"
fi
if [ -f "$LEGACY_BACKEND_DIR/notification_config.json" ] && [ ! -f "$BACKEND_TARGET_DIR/notification_config.json" ]; then
    cp -p "$LEGACY_BACKEND_DIR/notification_config.json" "$BACKEND_TARGET_DIR/notification_config.json"
fi

rm -rf "$BACKEND_TARGET_DIR/backend"
cp -r "$SCRIPT_DIR/backend" "$BACKEND_TARGET_DIR/"
cp "$SCRIPT_DIR/collect.sh" "$BACKEND_TARGET_DIR/"
chmod +x "$BACKEND_TARGET_DIR/collect.sh"

# Set up CLI statusline collector in ~/.local/bin (with legacy fallback symlink)
mkdir -p "$HOME/.local/bin"
ln -sf "$BACKEND_TARGET_DIR/collect.sh" "$HOME/.local/bin/token-monitor-collect"
ln -sf "$BACKEND_TARGET_DIR/collect.sh" "$HOME/.local/bin/kde-claude-stat-collect"

# Clean up legacy D-Bus on-demand activation service file if present
rm -f "$DBUS_USER_DIR/$APPLET_ID.service"

# 4. Set up systemd user service
echo "--> 4. Setting up systemd user service..."
mkdir -p "$SYSTEMD_USER_DIR"
PYTHON_BIN="$(command -v python3 || echo "/usr/bin/python3")"
cat << EOF > "$SYSTEMD_USER_DIR/token-monitor.service"
[Unit]
Description=Token Monitor for Claude Code Daemon for Claude Code Limits & Burn Rate
After=network.target

[Service]
Type=simple
ExecStart=$PYTHON_BIN -m backend.cli serve --port 48291
WorkingDirectory=$BACKEND_TARGET_DIR
Environment=PYTHONPATH=$BACKEND_TARGET_DIR
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Clean up legacy systemd service
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user stop kde-claude-stat.service 2>/dev/null || true
    systemctl --user disable kde-claude-stat.service 2>/dev/null || true
fi
rm -f "$SYSTEMD_USER_DIR/kde-claude-stat.service"

# 5. Reload systemd user daemon and start service
if command -v systemctl >/dev/null 2>&1; then
    echo "--> 5. Reloading systemd user daemon and enabling service..."
    systemctl --user daemon-reload
    systemctl --user enable --now token-monitor.service || true
fi

# 6. Statusline hook integration (optional)
if [ "$WITH_HOOK" = true ]; then
    echo "--> 6. Integrating collector into Claude Code statusline (~/.claude/settings.json)..."
    PYTHONPATH="$BACKEND_TARGET_DIR" python3 -m backend.cli install-hook || true
elif [ -t 0 ]; then
    echo ""
    read -r -p "Claude Code statusline Hook (~/.claude/settings.json) automatisch einrichten? [y/N]: " answer || true
    if [[ "${answer:-}" =~ ^[yY] ]]; then
        echo "--> 6. Integrating collector into Claude Code statusline..."
        PYTHONPATH="$BACKEND_TARGET_DIR" python3 -m backend.cli install-hook || true
    else
        echo "--> 6. Statusline-Hook übersprungen (kann mit './install.sh --with-hook' aktiviert werden)."
    fi
else
    echo "--> 6. Statusline-Hook übersprungen (kann mit './install.sh --with-hook' aktiviert werden)."
fi

echo ""
echo "=========================================================="
echo "  Installation completed successfully!"
echo "  The widget is now available in KDE Widget Explorer:"
echo "  'Token Monitor for Claude Code'"
echo "=========================================================="

