"""Automatic integration for Claude Code statusline hook."""

import json
import logging
import os
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

COLLECTOR_CMD = "$HOME/.local/bin/token-monitor-collect"
LEGACY_COLLECTOR_CMD = "$HOME/.local/bin/kde-claude-stat-collect"


def get_claude_settings_path() -> Path:
    """Returns the path to Claude Code's settings.json."""
    env_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if env_dir:
        return Path(env_dir).expanduser() / "settings.json"
    return Path.home() / ".claude" / "settings.json"


def is_hook_installed() -> bool:
    """Checks whether token-monitor-collect is registered in Claude's statusline."""
    path = get_claude_settings_path()
    if not path.is_file():
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        status_line = data.get("statusLine")
        if isinstance(status_line, dict):
            cmd = status_line.get("command", "")
            return "token-monitor-collect" in cmd or "kde-claude-stat-collect" in cmd
        elif isinstance(status_line, str):
            return "token-monitor-collect" in status_line or "kde-claude-stat-collect" in status_line
    except Exception:
        pass
    return False


def install_statusline_hook() -> Tuple[bool, str]:
    """
    Prepends kde-claude-stat-collect to existing statusline in settings.json.
    Works as a transparent passthrough filter in the pipeline.
    """
    path = get_claude_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            return False, f"Error reading {path}: {e}"

    status_line = data.get("statusLine")

    if status_line is None:
        data["statusLine"] = {
            "type": "command",
            "command": COLLECTOR_CMD,
        }
    elif isinstance(status_line, dict):
        curr_cmd = status_line.get("command", "").strip()
        matched_cmd = None
        for candidate in ("token-monitor-collect", "kde-claude-stat-collect"):
            if candidate in curr_cmd:
                matched_cmd = candidate
                break

        if matched_cmd:
            if " | " in curr_cmd and "--passthrough" not in curr_cmd:
                status_line["command"] = curr_cmd.replace(
                    matched_cmd, f"{matched_cmd} --passthrough"
                )
            else:
                return True, "Hook is already configured in statusline."
        elif curr_cmd:
            status_line["command"] = f"{COLLECTOR_CMD} --passthrough | {curr_cmd}"
        else:
            status_line["command"] = COLLECTOR_CMD
    elif isinstance(status_line, str):
        if "token-monitor-collect" in status_line or "kde-claude-stat-collect" in status_line:
            return True, "Hook is already configured in statusline."
        data["statusLine"] = {
            "type": "command",
            "command": f"{COLLECTOR_CMD} --passthrough | {status_line}",
        }

    # Create backup before writing
    if path.is_file():
        bak_path = path.with_suffix(".json.bak")
        try:
            bak_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass

    # Atomic write
    tmp_path = path.with_suffix(".json.tmp")
    try:
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp_path.replace(path)
    except Exception as e:
        return False, f"Error writing {path}: {e}"

    return True, f"Token Monitor for Claude Code successfully prepended to statusline in {path}."


def remove_statusline_hook() -> Tuple[bool, str]:
    """Removes kde-claude-stat-collect cleanly from statusline in settings.json."""
    path = get_claude_settings_path()
    if not path.is_file():
        return False, "settings.json not found."

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"Error reading {path}: {e}"

    status_line = data.get("statusLine")
    if not status_line:
        return True, "No statusline configured."

    if isinstance(status_line, dict):
        cmd = status_line.get("command", "")
        # Resolve pipeline command patterns for both new and legacy command
        for cmd_pattern in (COLLECTOR_CMD, LEGACY_COLLECTOR_CMD):
            cmd = cmd.replace(f"{cmd_pattern} --passthrough | ", "")
            cmd = cmd.replace(f"{cmd_pattern} --passthrough|", "")
            cmd = cmd.replace(f"{cmd_pattern} --passthrough", "").strip()
            cmd = cmd.replace(f"{cmd_pattern} | ", "")
            cmd = cmd.replace(f"{cmd_pattern}|", "")
            cmd = cmd.replace(cmd_pattern, "").strip()

        if cmd:
            status_line["command"] = cmd
        else:
            del data["statusLine"]

    # Atomic write
    tmp_path = path.with_suffix(".json.tmp")
    try:
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp_path.replace(path)
    except Exception as e:
        return False, f"Error writing {path}: {e}"

    return True, "Token Monitor for Claude Code cleanly removed from statusline."
