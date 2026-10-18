# Token Monitor for Claude Code

[![KDE Plasma 6](https://img.shields.io/badge/KDE%20Plasma-6.0%2B-1d99f3?style=flat-square&logo=kde&logoColor=white)](https://kde.org)
[![Python 3](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Version](https://img.shields.io/badge/Version-v0.0.8-orange?style=flat-square)](package/metadata.json)
[![Lizenz: GPL-3.0](https://img.shields.io/badge/Lizenz-GPL--3.0-blue?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-51%20bestanden-brightgreen?style=flat-square)](#)
[![Abhängigkeiten](https://img.shields.io/badge/Abh%C3%A4ngigkeiten-Zero%20(Stdlib)-success?style=flat-square)](#)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-CLI%20%26%20VS%20Code-purple?style=flat-square)](#)
[![Beiträge: Willkommen](https://img.shields.io/badge/Beitr%C3%A4ge-willkommen-brightgreen.svg?style=flat-square)](CONTRIBUTING.md)
[![Sicherheit: Policy](https://img.shields.io/badge/Sicherheit-Richtlinie-informational?style=flat-square)](SECURITY.md)
[![Spenden](https://img.shields.io/badge/Spenden-Kaffee%20ausgeben-yellow?style=flat-square&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/buellsunited)

[🇬🇧 Switch to English README](README.md)


KDE Plasma 6 Widget und Python-Backend zur Überwachung von **Claude Code Token-Limits, Burn-Rate & Budget-Pace** (nativ integriert in der KDE Plasma Leiste / Desktop).

---

## Screenshots

| Modernes Glas (Milchglas) | Breeze Dunkel | Einstellungen & Design |
| :---: | :---: | :---: |
| <img src="docs/screenshots/img/Normal.png" alt="Token Monitor for Claude Code Modern Glass Widget" width="280"> | <img src="docs/screenshots/img/High.png" alt="Token Monitor for Claude Code Breeze Dunkel Widget" width="280"> | <img src="docs/screenshots/img/Config.png" alt="Token Monitor for Claude Code Einstellungen" width="280"> |

---

## Features

- **Natives KDE Plasma 6 Widget** (Panel & Desktop):
  - **Zweisprachig (i18n)**: Englisch (Standard) & Deutsch via GNU Gettext / KI18n.
  - **Sprachumschalter in Einstellungen**: Direkt zwischen *Systemstandard*, *Englisch* und *Deutsch* wählbar.
  - **Duale Anzeigemodi (Leiste & Desktop)**:
    - **Kompakter Leistenmodus (`compactRepresentation`)**: Integriert sich nahtlos in horizontale oder vertikale KDE Plasma Leisten mit kontraststarken Statusfarben (Grün / Bernstein / Rot) für 5-Stunden- und 7-Tage-Limits.
    - **Interaktives Popup**: Klick auf das Leisten-Icon öffnet die vollständige Detailansicht als natives Plasma-Popup.
    - **Desktop-Widget**: Frei platzierbares und skalierbares Widget auf der Schreibtischoberfläche (`fullRepresentation`).
  - **Detaillierte Verbrauchsübersicht**: Fortschrittsbalken, sekundengenaue Reset-Timer, Soll-Pace-Vergleich, Burn-Rate (%/Stunde) und Erschöpfungsprognose (ETA).
  - **Interaktive Multi-Zeitfenster Burn-Charts**: Live-Visualisierung des Verbrauchsverlaufs und lineare Projektion mit umschaltbaren Zeiträumen (**7h**, **24h** und **7d**).
  - **Rate-Limit-Schutz & Feedback**: Live-Warnbanner mit Cooldown-Timer bei aktivem HTTP 429, automatisches Backoff und manueller Sofort-Retry per Klick (`🔄`).
  - **Theme-Modi**: Plasma Theme, Hell (Breeze Light), Dunkel (Breeze Dark), Transparent oder Modernes Glas (Milchglas) mit konfigurierbarem Intervall (15s bis 5m).
- **Python-Backend (Zero-Dependency außer Python 3)**:
  - **CLI- & VS-Code-Unterstützung**: Erkennt automatisch aktive Claude-Code-Sitzungen im Terminal sowie in der offiziellen VS Code Extension (`anthropic.claude-code`).
  - **Prozess-Erkennung**: Prüft laufende Claude Code Prozesse via `/proc`; pausiert API-Abfragen im Leerlauf und weist `0,0%/h (inaktiv)` aus, um unnötige Rate-Limits zu verhindern.
  - **Rate-Limit Backoff & Schutz**: Reagiert automatisch auf HTTP 429 `Retry-After` Header von Anthropic und hält einen 3-Minuten-Mindestabstand (180s) zwischen API-Abfragen ein.
  - **OAuth Usage API Client**: Fragt `https://api.anthropic.com/api/oauth/usage` mit Bearer Token aus `~/.claude/.credentials.json` ab.
  - **SQLite Snapshot History**: Speichert Snapshots für Trendanalysen unter `~/.local/share/token-monitor/history.db`.
  - **Mathematische Berechnung**: Lineare Regression (Least Squares) für Burn-Rate (%/h), Pace und Erschöpfungs-ETA.
  - **Lokaler HTTP-Server**: Leichtgewichtiger REST-Endpunkt (`127.0.0.1:48291/stats`) mit TTL-Caching zur Entlastung der API.
  - **Zero-API Statusline Pipeline**: Integriert sich transparent als Unix-Passthrough-Filter in Claude Codes `statusLine` (`~/.claude/settings.json`) für Terminal-Nutzung.

---

## Installation & Start

### Schnell-Installation (empfohlen)

```bash
./install.sh
```
Das Skript kompiliert automatisch die Übersetzungen, installiert das Plasmoid nach `~/.local/share/plasma/plasmoids/com.buellsunited.TokenMonitor`, installiert das Backend nach `~/.local/share/token-monitor/` und startet den systemd-User-Service.

Um zusätzlich den optionalen Zero-API Statusline-Hook in `~/.claude/settings.json` einzubinden:
```bash
./install.sh --with-hook
```

### Manuelle Widget-Installation

```bash
./install_widget.sh
```

Danach kann das Widget **"Token Monitor for Claude Code"** (bzw. **"Token Monitor für Claude Code"**) über den KDE Plasma Widget-Explorer zur Leiste oder auf den Schreibtisch hinzugefügt werden.

### Backend-Daemon starten

**Manuell im Terminal:**
```bash
python3 -m backend.cli serve --port 48291
```

**Oder als systemd User Service einrichten:**
```bash
mkdir -p ~/.config/systemd/user/
cp token-monitor.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now token-monitor.service
```

Status prüfen:
```bash
systemctl --user status token-monitor.service
```

---

## Übersetzungen (i18n)

Die Hauptsprache des Codes und Widgets ist Englisch. Deutsche Übersetzungen werden über GNU Gettext / KI18n bereitgestellt.

- Vorlage aktualisieren & kompilieren:
```bash
./build_translations.sh
```
- Die Sprachkataloge liegen unter `po/de.po` und werden nach `package/contents/locale/de/LC_MESSAGES/plasma_applet_com.buellsunited.TokenMonitor.mo` kompiliert.

---

## CLI-Nutzung

Aktuellen Status direkt im Terminal als JSON ausgeben:
```bash
python3 -m backend.cli status
```

Statusline-JSON von stdin passiv einspeisen:
```bash
echo '{"rate_limits": {...}}' | python3 -m backend.cli collect
```

---

## Tests & UI-Simulation

Python-Unit-Tests ausführen (19 Tests, 100 % Standardbibliothek):
```bash
python3 -m unittest discover tests
```

UI-Zustände und Grenzfälle ohne Token-Verbrauch testen (`manage_fake_data.py`):
```bash
# Moderate Testdaten injizieren
python3 scripts/manage_fake_data.py --inject

# Hohe Auslastung & kritische Burn-Rate simulieren
python3 scripts/manage_fake_data.py --high

# Aktive HTTP-429-API-Sperre simulieren (120s Cooldown-Banner)
python3 scripts/manage_fake_data.py --rate-limit 120

# Simulierte API-Sperre sofort beenden
python3 scripts/manage_fake_data.py --clear-rate-limit

# Original-Datenbank wiederherstellen und Fake-Modus beenden
python3 scripts/manage_fake_data.py --restore
```

---

## Unterstützung & Spenden

Wenn dir dieses Widget gefällt und deine Arbeit mit Claude Code erleichtert, freue ich mich über einen Kaffee!

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Donate-orange?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/buellsunited)

- **Website**: [kde.buells-united.com](https://kde.buells-united.com)
- **Spenden**: [buymeacoffee.com/buellsunited](https://buymeacoffee.com/buellsunited)

---

## Mitwirken & Beitragen (Contributing)

Beiträge, Fehlerberichte und Feature-Vorschläge sind herzlich willkommen! In [CONTRIBUTING.md](CONTRIBUTING.md) findest du ausführliche Hinweise zur Entwicklungsumgebung, den Test-Abläufen und Richtlinien für Pull Requests.

Bitte beachte unseren [Verhaltenskodex (Code of Conduct)](CODE_OF_CONDUCT.md).

---

## Sicherheit & Datenschutz (Security)

Sicherheit und Datenschutz stehen an erster Stelle. Details zu unserer gehärteten, lokalen Sicherheitsarchitektur und zum vertraulichen Melden von Sicherheitslücken findest du in unserer [Sicherheitsrichtlinie (SECURITY.md)](SECURITY.md).

---

## Danksagung & Inspiration

Inspired by [ccburn](https://github.com/JuanjoFuchs/ccburn) by JuanjoFuchs.

---

## Lizenz

Dieses Projekt steht unter der GNU General Public License v3.0 – siehe die Datei [LICENSE](LICENSE) für Details.

---

## Haftungsausschluss / Disclaimer

Dies ist ein inoffizielles Community-Projekt und steht in keiner Verbindung zu Anthropic PBC oder KDE e.V. "Claude" ist eine eingetragene Marke von Anthropic PBC. "KDE" und "KDE Plasma" sind eingetragene Marken des KDE e.V.


