.pragma library

var translationsDe = {
    "Token Monitor for Claude Code": "Token Monitor für Claude Code",
    "Loading data…": "Lade Daten…",
    "Session (5h): %1% | Weekly: %2%": "Session (5h): %1% | Weekly: %2%",
    "JSON parse error": "JSON-Parse-Fehler",
    "Daemon unreachable (port 48291)": "Daemon nicht erreichbar (Port 48291)",
    "Daemon request timed out": "Timeout bei Daemon-Abfrage",
    "Daemon connection failed": "Verbindung zu Daemon fehlgeschlagen",
    "API rate limit active (HTTP 429) — Next retry in %1s (Click 🔄 to retry now)": "API-Rate-Limit aktiv (HTTP 429) — Nächster Versuch in %1s (Klick auf 🔄 erzwingt sofortigen Neuversuch)",
    "API paused (429: %1s left)": "API pausiert (429: noch %1s)",
    "API paused (%1s)": "API pausiert (%1s)",
    "No exhaustion": "Keine Erschöpfung",
    "Refresh now": "Jetzt neu laden",
    "Tip: Run './install.sh' or 'systemctl --user start token-monitor'": "Tipp: './install.sh' ausführen oder 'systemctl --user start token-monitor'",
    "Start Background Service": "Hintergrunddienst starten",
    "Starting service…": "Dienst wird gestartet…",
    "Auto-starts and enables systemd user service 'token-monitor.service'": "Startet und aktiviert automatisch den systemd-Dienst 'token-monitor.service'",
    "5-Hour Session": "5-Stunden Session",
    "Target Pace: %1%": "Soll-Pace: %1%",
    "Reset: %1 (in %2)": "Reset: %1 (in %2)",
    "Reset in: %1": "Reset in: %1",
    "Burn: %1%/h (%2)": "Burn: %1%/h (%2)",
    "idle": "inaktiv",
    "low": "niedrig",
    "moderate": "moderat",
    "high": "hoch",
    "critical": "kritisch",
    "100% in ~%1": "100% in ~%1",
    "Safe before reset ✓": "Sicher vor Reset ✓",
    "Weekly Limit (7 Days)": "Wochen-Limit (7 Tage)",
    "Model Breakdown": "Modell-Aufschlüsselung",
    "By Model (Weekly)": "Nach Modell (Wöchentlich)",
    "Burn: %1%/h": "Burn: %1%/h",
    "Limit reached before reset!": "Limit vor Reset erreicht!",
    "Limit in %1 · reset in %2": "Limit in %1 erreicht · Reset erst in %2",
    "Limit reached before reset": "Limit wird vor dem Reset erreicht",
    "Over budget · limit in %1": "Tempo über Budget · Limit in %1",
    "Over budget": "Tempo über Budget",
    "Sufficient until reset ✓": "Reicht bis Reset ✓",
    "Updated: %1": "Aktualisiert: %1",
    "☕ Buy Me a Coffee": "☕ Buy Me a Coffee",
    "Color Scheme / Style:": "Farbschema / Stil:",
    "Plasma Theme (Default)": "Plasma Theme (Standard)",
    "Light (Breeze Light)": "Hell (Breeze Light)",
    "Dark (Breeze Dark)": "Dunkel (Breeze Dark)",
    "Transparent (No Card)": "Transparent (Ohne Kachel)",
    "Modern Glass (Frosted)": "Modernes Glas (Milchglas)",
    "Taskbar / Panel Style:": "Leisten-Anzeigestil:",
    "Text (Default)": "Text (Standard)",
    "Progress Ring (Compact)": "Fortschrittsring (Kompakt)",
    "Combined (Ring + Text)": "Kombiniert (Ring + Text)",
    "Refresh Interval:": "Aktualisierungsintervall:",
    "15 seconds": "15 Sekunden",
    "30 seconds": "30 Sekunden",
    "1 minute (Default)": "1 Minute (Standard)",
    "2 minutes": "2 Minuten",
    "5 minutes": "5 Minuten",
    "Support & Donations": "Unterstützung & Spenden",
    "Desktop Notifications:": "Desktop-Benachrichtigungen:",
    "Enable native KDE Plasma notifications on limit hazard": "Native KDE Plasma Benachrichtigungen bei Limit-Gefahr aktivieren",
    "Thresholds & Warning Levels": "Schwellen- & Warnwerte",
    "Burn Rate Warning:": "Burn-Rate-Warnung:",
    "Alert when current pace exhausts limit before reset (100% projected)": "Warnen, wenn aktuelles Tempo das Limit vor Reset aufbraucht (100 % prognostiziert)",
    "Warning Threshold 1:": "Warnstufe 1:",
    "Critical Threshold 2:": "Kritische Warnstufe 2:",
    "Alert at": "Warnen ab",
    "(Default: 85%)": "(Standard: 85 %)",
    "(Default: 95%)": "(Standard: 95 %)",
    "Diagnostics & Test": "Diagnose & Test",
    "Test Notification:": "Test-Benachrichtigung:",
    "🔔 Send Test Notification": "🔔 Test-Benachrichtigung senden",
    "Test notification sent ✓": "Test-Benachrichtigung gesendet ✓",
    "Error sending notification": "Fehler beim Senden",
    "Notifications": "Benachrichtigungen",
    "Buy me a coffee:": "Kaffee spendieren:",
    "Appearance": "Erscheinungsbild",
    "Language:": "Sprache:",
    "System Default": "Systemstandard",
    "Now": "Jetzt",
    "Start": "Start",
    "Reset": "Reset",
    "Credits & Acknowledgments": "Danksagung & Credits",
    "Inspiration:": "Inspiration:",
    "CLI tool by JuanjoFuchs": "CLI-Tool von JuanjoFuchs"
};

function tr(text, languageMode, arg1, arg2) {
    var isDe = (languageMode === 2) || (languageMode === 0 && (Qt.locale().name.indexOf("de") === 0));
    var res = text;
    if (languageMode === 1) {
        res = text;
    } else if (isDe) {
        res = (translationsDe[text] !== undefined) ? translationsDe[text] : text;
    } else {
        res = text;
    }
    if (arg1 !== undefined) res = res.replace("%1", arg1);
    if (arg2 !== undefined) res = res.replace("%2", arg2);
    return res;
}
