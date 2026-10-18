#!/usr/bin/env bash
# Start- und Self-Healing-Skript für Token Monitor for Claude Code
# Wird vom KDE Plasma Widget aufgerufen, wenn Port 48291 nicht erreichbar ist.
set -e

PORT=48291
STATS_URL="http://127.0.0.1:${PORT}/stats"

# 1. Prüfen, ob der Daemon bereits läuft und antwortet
if command -v curl >/dev/null 2>&1; then
    if curl -s --max-time 1 "$STATS_URL" >/dev/null 2>&1; then
        echo "Token Monitor Daemon lauscht bereits auf Port ${PORT}."
        exit 0
    fi
fi

# 2. Python3 auffinden
PYTHON_BIN="$(command -v python3 || echo "/usr/bin/python3")"
if [ ! -x "$PYTHON_BIN" ]; then
    echo "Fehler: python3 nicht gefunden oder nicht ausführbar." >&2
    exit 1
fi

# 3. Pfade ermitteln (Skript liegt in package/contents/scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUNDLED_BACKEND="$CONTENTS_DIR/backend"
USER_DATA_DIR="$HOME/.local/share/token-monitor"
USER_BACKEND_DIR="$USER_DATA_DIR/backend"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/token-monitor.service"

mkdir -p "$USER_DATA_DIR"

# 4. Backend-Dateien bei Bedarf nach ~/.local/share/token-monitor/ synchronisieren
if [ -d "$BUNDLED_BACKEND" ]; then
    mkdir -p "$USER_BACKEND_DIR"
    cp -r "$BUNDLED_BACKEND"/* "$USER_BACKEND_DIR/"
    rm -rf "$USER_BACKEND_DIR/__pycache__"
fi

# collect.sh und Symlink bereitstellen
if [ -f "$CONTENTS_DIR/collect.sh" ]; then
    cp "$CONTENTS_DIR/collect.sh" "$USER_DATA_DIR/collect.sh"
    chmod +x "$USER_DATA_DIR/collect.sh"
    mkdir -p "$HOME/.local/bin"
    ln -sf "$USER_DATA_DIR/collect.sh" "$HOME/.local/bin/token-monitor-collect"
fi

# 5. systemd User Service einrichten und starten falls systemctl verfügbar ist
STARTED_VIA_SYSTEMD=false
if command -v systemctl >/dev/null 2>&1; then
    mkdir -p "$SYSTEMD_USER_DIR"
    if [ ! -f "$SERVICE_FILE" ]; then
        cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Token Monitor for Claude Code Daemon for Claude Code Limits & Burn Rate
After=network.target

[Service]
Type=simple
ExecStart=$PYTHON_BIN -m backend.cli serve --port $PORT
WorkingDirectory=$USER_DATA_DIR
Environment=PYTHONPATH=$USER_DATA_DIR
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
        systemctl --user daemon-reload 2>/dev/null || true
        systemctl --user enable token-monitor.service 2>/dev/null || true
    fi

    # Versuchen, den systemd-Dienst zu starten
    if systemctl --user start token-monitor.service 2>/dev/null; then
        STARTED_VIA_SYSTEMD=true
    fi
fi

# 6. Prüfen, ob der Dienst nach systemd-Start antwortet (bis zu 2 Sekunden)
if [ "$STARTED_VIA_SYSTEMD" = true ]; then
    for _ in 1 2 3 4; do
        if command -v curl >/dev/null 2>&1; then
            if curl -s --max-time 1 "$STATS_URL" >/dev/null 2>&1; then
                echo "Token Monitor Daemon erfolgreich via systemd gestartet."
                exit 0
            fi
        fi
        sleep 0.5
    done
fi

# 7. Fallback: Direkter Hintergrundstart falls systemd fehlschlägt oder nicht existiert
echo "Starte Daemon als Hintergrundprozess..."
cd "$USER_DATA_DIR"
PYTHONPATH="$USER_DATA_DIR" nohup "$PYTHON_BIN" -m backend.cli serve --port "$PORT" >/dev/null 2>&1 &

# Kurz warten und Verifikation
sleep 1
if command -v curl >/dev/null 2>&1; then
    if curl -s --max-time 1 "$STATS_URL" >/dev/null 2>&1; then
        echo "Token Monitor Daemon erfolgreich gestartet."
        exit 0
    fi
fi

echo "Token Monitor Daemon im Hintergrund gestartet."
exit 0
