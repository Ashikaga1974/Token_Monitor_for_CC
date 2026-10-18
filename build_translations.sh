#!/usr/bin/env bash
# Generate .pot template and compile gettext .mo files for KDE Plasma
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOMAIN="plasma_applet_com.buellsunited.TokenMonitor"
PO_DIR="$SCRIPT_DIR/po"
LOCALE_DIR="$SCRIPT_DIR/package/contents/locale"

mkdir -p "$PO_DIR"
mkdir -p "$LOCALE_DIR/de/LC_MESSAGES"

# 1. Extract strings from QML using relative paths (no absolute paths in POT)
if command -v xgettext >/dev/null 2>&1; then
    echo "--> Updating POT template ($PO_DIR/$DOMAIN.pot)..."
    (
        cd "$SCRIPT_DIR"
        find package/contents -name "*.qml" | sort | xargs xgettext --from-code=UTF-8 \
                 --language=JavaScript \
                 --keyword=i18n:1 \
                 --keyword=i18np:1,2 \
                 --output="$PO_DIR/$DOMAIN.pot"
    )
fi

# 2. Compile de.po to .mo
if [ -f "$PO_DIR/de.po" ] && command -v msgfmt >/dev/null 2>&1; then
    echo "--> Compiling de.po to $LOCALE_DIR/de/LC_MESSAGES/$DOMAIN.mo..."
    msgfmt "$PO_DIR/de.po" -o "$LOCALE_DIR/de/LC_MESSAGES/$DOMAIN.mo"
fi

echo "--> Translations built successfully."
