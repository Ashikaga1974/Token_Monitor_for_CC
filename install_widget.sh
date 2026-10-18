#!/usr/bin/env bash
# Installation script for Token Monitor for Claude Code Plasma 6 Widget
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$SCRIPT_DIR/package"
APPLET_ID="com.buellsunited.TokenMonitor"
TARGET_DIR="$HOME/.local/share/plasma/plasmoids/$APPLET_ID"
USER_LOCALE_DIR="$HOME/.local/share/locale/de/LC_MESSAGES"

# Build translations
if [ -x "$SCRIPT_DIR/build_translations.sh" ]; then
    "$SCRIPT_DIR/build_translations.sh"
fi

echo "==> Installing KDE Plasma Widget: $APPLET_ID"
LEGACY_APPLET_ID="com.buellsunited.claudestat"
rm -rf "$HOME/.local/share/plasma/plasmoids/$LEGACY_APPLET_ID"
rm -f "$USER_LOCALE_DIR/plasma_applet_$LEGACY_APPLET_ID.mo"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/$LEGACY_APPLET_ID.svg"

# Migrate legacy plugin ID in plasma config if present
if [ -f "$HOME/.config/plasma-org.kde.plasma.desktop-appletsrc" ]; then
    sed -i "s/plugin=$LEGACY_APPLET_ID/plugin=$APPLET_ID/g" "$HOME/.config/plasma-org.kde.plasma.desktop-appletsrc" 2>/dev/null || true
fi
if [ -f "$HOME/.config/plasmawindowedrc" ]; then
    sed -i "s/plugin=$LEGACY_APPLET_ID/plugin=$APPLET_ID/g" "$HOME/.config/plasmawindowedrc" 2>/dev/null || true
fi

# Sync backend and scripts into package for complete autarky
rm -rf "$PACKAGE_DIR/contents/backend"
cp -r "$SCRIPT_DIR/backend" "$PACKAGE_DIR/contents/"
rm -rf "$PACKAGE_DIR/contents/backend/__pycache__"
cp "$SCRIPT_DIR/collect.sh" "$PACKAGE_DIR/contents/collect.sh"
chmod +x "$PACKAGE_DIR/contents/collect.sh"
chmod +x "$PACKAGE_DIR/contents/scripts/start_daemon.sh"

mkdir -p "$(dirname "$TARGET_DIR")"

# Remove existing installation if present
rm -rf "$TARGET_DIR"
cp -r "$PACKAGE_DIR" "$TARGET_DIR"

DOMAIN="plasma_applet_$APPLET_ID"
if [ -f "$PACKAGE_DIR/contents/locale/de/LC_MESSAGES/$DOMAIN.mo" ]; then
    mkdir -p "$USER_LOCALE_DIR"
    cp "$PACKAGE_DIR/contents/locale/de/LC_MESSAGES/$DOMAIN.mo" "$USER_LOCALE_DIR/$DOMAIN.mo"
fi

# Register icon in user icon theme (for Widget Explorer and About dialog)
USER_ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$USER_ICON_DIR"
if [ -f "$PACKAGE_DIR/contents/icons/$APPLET_ID.svg" ]; then
    cp "$PACKAGE_DIR/contents/icons/$APPLET_ID.svg" "$USER_ICON_DIR/$APPLET_ID.svg"
elif [ -f "$SCRIPT_DIR/icons/$APPLET_ID.svg" ]; then
    cp "$SCRIPT_DIR/icons/$APPLET_ID.svg" "$USER_ICON_DIR/$APPLET_ID.svg"
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo "==> Widget successfully copied to: $TARGET_DIR"
echo "==> Start daemon or configure systemd user service."

