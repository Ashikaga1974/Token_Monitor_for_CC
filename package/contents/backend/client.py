"""OAuth client and credentials handling for Claude Code Anthropic API."""

import json
import logging
import os
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/api/oauth/usage"
API_BETA_HEADER = "oauth-2025-04-20"


def get_claude_credentials_path() -> Path:
    """Returns the path to Claude Code's .credentials.json."""
    env_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if env_dir:
        return Path(env_dir).expanduser() / ".credentials.json"
    return Path.home() / ".claude" / ".credentials.json"


def read_oauth_token() -> str:
    """Reads the OAuth token from local Claude configuration."""
    creds_path = get_claude_credentials_path()
    if not creds_path.is_file():
        raise FileNotFoundError(f"Claude credentials not found at: {creds_path}")

    with open(creds_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check for claudeAiOauth block
    oauth_info = data.get("claudeAiOauth", {})
    token = oauth_info.get("accessToken")
    if not token:
        raise ValueError("No accessToken found in claudeAiOauth object.")
    return token


import time

_rate_limited_until: float = 0.0
_consecutive_rate_limits: int = 0


def get_rate_limit_remaining_seconds() -> float:
    """Returns the remaining backoff wait time after an HTTP 429 response (in seconds)."""
    global _rate_limited_until
    sim_file = Path.home() / ".local" / "share" / "token-monitor" / "simulate_rate_limit"
    if not sim_file.exists():
        sim_file = Path.home() / ".local" / "share" / "kde-claude-stat" / "simulate_rate_limit"
    if sim_file.exists():
        try:
            val = float(sim_file.read_text().strip())
            rem = val - time.time()
            if rem > 0:
                return rem
            sim_file.unlink(missing_ok=True)
        except Exception:
            return 120.0
    rem = _rate_limited_until - time.time()
    return max(0.0, rem)


def reset_rate_limit() -> None:
    """Resets any active rate limit backoff (e.g. on manual user refresh)."""
    global _rate_limited_until, _consecutive_rate_limits
    _rate_limited_until = 0.0
    _consecutive_rate_limits = 0
    for folder in ("token-monitor", "kde-claude-stat"):
        sim_file = Path.home() / ".local" / "share" / folder / "simulate_rate_limit"
        if sim_file.exists():
            try:
                sim_file.unlink(missing_ok=True)
            except OSError:
                pass


def is_rate_limited() -> bool:
    """Checks whether an active HTTP 429 backoff is currently in effect."""
    return get_rate_limit_remaining_seconds() > 0.0


def fetch_usage_api(timeout: int = 10) -> Dict[str, Any]:
    """Queries current usage directly from the Anthropic OAuth Usage API."""
    global _rate_limited_until
    rem = get_rate_limit_remaining_seconds()
    if rem > 0.0:
        logger.warning(
            f"Rate limit active (HTTP 429). Request skipped. Wait time: {int(rem)}s."
        )
        raise urllib.error.HTTPError(
            API_URL, 429, f"Rate limited. Backoff active for {int(rem)}s", {}, None
        )

    token = read_oauth_token()
    req = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "anthropic-beta": API_BETA_HEADER,
            "User-Agent": "Token Monitor for Claude Code/1.0",
        },
    )

    global _consecutive_rate_limits
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read().decode("utf-8")
            _consecutive_rate_limits = 0
            return json.loads(raw_body)
    except urllib.error.HTTPError as err:
        if err.code == 429:
            _consecutive_rate_limits += 1
            retry_header = err.headers.get("Retry-After") if err.headers else None
            try:
                seconds = int(retry_header) if retry_header else 0
            except ValueError:
                seconds = 0

            # Exponentieller Backoff: 60s -> 120s -> 240s -> 300s (Deckel 5 Min)
            exp_backoff = min(60 * (2 ** (_consecutive_rate_limits - 1)), 300)
            effective_backoff = max(exp_backoff, seconds)
            effective_backoff = min(max(60, effective_backoff), 300)

            _rate_limited_until = time.time() + effective_backoff
            logger.warning(
                f"HTTP 429 Rate Limit (#{_consecutive_rate_limits}) von Anthropic. Pause aktiv für {effective_backoff}s."
            )
        else:
            logger.error(f"HTTP error during usage API request: {err.code} {err.reason}")
        raise
    except urllib.error.URLError as err:
        logger.error(f"Network error during usage API request: {err.reason}")
        raise

