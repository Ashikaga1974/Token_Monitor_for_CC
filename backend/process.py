"""Process detection for active Claude Code sessions (CLI and VS Code extension)."""

import os
from pathlib import Path
from typing import List

# Monitoring-Tools und Browser-Hosts ausschließen
EXCLUDED_KEYWORDS = ("kde-claude", "token-monitor", "ccburn", "--chrome-native-host")



def has_claude_vscode_extension() -> bool:
    """Prüft, ob die offizielle Claude Code Erweiterung in VS Code installiert ist."""
    candidate_dirs = [
        Path.home() / ".vscode" / "extensions",
        Path.home() / ".vscode-insiders" / "extensions",
        Path.home() / ".vscode-oss" / "extensions",
    ]
    for ext_dir in candidate_dirs:
        if not ext_dir.is_dir():
            continue
        try:
            for child in ext_dir.iterdir():
                if child.name.lower().startswith("anthropic.claude-code"):
                    return True
        except (PermissionError, FileNotFoundError):
            continue
    return False


def is_vscode_process(parts: List[str]) -> bool:
    """Erkennt laufende VS Code / Code-OSS / VSCodium Prozesse."""
    if not parts:
        return False
    exe = Path(parts[0]).name.lower()
    if exe in ("code", "code-oss", "codium", "vscodium"):
        return True
    line = " ".join(parts).lower()
    return "/code/code" in line or "/vscode/" in line or "--type=extensionhost" in line


def is_claude_cmdline(parts: List[str]) -> bool:
    """Bewertet, ob Befehlszeilen-Argumente zu einer aktiven Claude-Sitzung gehören."""
    if not parts:
        return False

    line = " ".join(parts).lower()

    # Monitoring-Tools und Chrome Native Messaging Host ignorieren
    for excluded in EXCLUDED_KEYWORDS:
        if excluded in line:
            return False

    exe = parts[0]
    exe_name = Path(exe).name.lower()

    # 1. Natives claude CLI Binary oder lokaler Versionspfad
    if exe_name == "claude" or "/.local/share/claude/versions/" in exe.lower():
        return True

    # 2. Direkter Verweis auf Claude Code Extension oder npm-Paket in den Argumenten
    if "anthropic.claude-code" in line or "claude-code" in line:
        return True

    # 3. Node/Bun/Deno Wrapper für Claude Skripte
    if exe_name in ("node", "bun", "deno", "electron"):
        for arg in parts[1:]:
            arg_lower = arg.lower()
            if "claude" in arg_lower and not any(ex in arg_lower for ex in EXCLUDED_KEYWORDS):
                return True

    # 4. VS Code läuft und Claude Code Erweiterung ist installiert
    if is_vscode_process(parts) and has_claude_vscode_extension():
        return True

    return False


def is_claude_process_running() -> bool:
    """Prüft, ob eine aktive Claude-Code- oder VS-Code-Sitzung auf dem Linux-System läuft."""
    fake_flag = Path.home() / ".local" / "share" / "token-monitor" / "fake_active"
    if not fake_flag.exists():
        fake_flag = Path.home() / ".local" / "share" / "kde-claude-stat" / "fake_active"
    if fake_flag.exists():
        return True


    proc_path = Path("/proc")
    if not proc_path.exists():
        return False

    current_pid = os.getpid()
    for pid_dir in proc_path.iterdir():
        if not pid_dir.name.isdigit():
            continue
        try:
            pid = int(pid_dir.name)
            if pid == current_pid:
                continue

            cmdline_file = pid_dir / "cmdline"
            if not cmdline_file.exists():
                continue

            raw = cmdline_file.read_bytes()
            if not raw:
                continue

            parts = [p.decode("utf-8", errors="ignore") for p in raw.split(b"\x00") if p]
            if is_claude_cmdline(parts):
                return True
        except (PermissionError, ProcessLookupError, FileNotFoundError):
            continue

    return False

