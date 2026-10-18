"""Tests for process and VS Code detection."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.process import (
    is_claude_cmdline,
    is_vscode_process,
    has_claude_vscode_extension,
)
from backend.storage import StorageDB
from datetime import datetime, timezone


class TestProcessDetection(unittest.TestCase):
    def test_native_claude_cli(self):
        self.assertTrue(is_claude_cmdline(["/usr/local/bin/claude"]))
        self.assertTrue(is_claude_cmdline(["claude", "task", "run"]))
        self.assertTrue(is_claude_cmdline(["/home/user/.local/share/claude/versions/1.0/claude"]))

    def test_vscode_extension_args(self):
        self.assertTrue(is_claude_cmdline([
            "node",
            "/home/user/.vscode/extensions/anthropic.claude-code-2.1.295/dist/server.js"
        ]))
        self.assertTrue(is_claude_cmdline([
            "/usr/lib/code/code",
            "--type=extensionHost",
            "--extensionId=anthropic.claude-code"
        ]))

    def test_node_wrapper(self):
        self.assertTrue(is_claude_cmdline(["node", "/usr/bin/claude"]))
        self.assertTrue(is_claude_cmdline(["bun", "/path/to/claude.js"]))

    def test_exclusions(self):
        self.assertFalse(is_claude_cmdline(["token-monitor-collect"]))
        self.assertFalse(is_claude_cmdline(["kde-claude-stat-collect"]))
        self.assertFalse(is_claude_cmdline(["/usr/bin/python3", "-m", "backend.cli"]))
        self.assertFalse(is_claude_cmdline(["claude", "--chrome-native-host"]))
        self.assertFalse(is_claude_cmdline(["ccburn", "--status"]))

    def test_vscode_detection(self):
        self.assertTrue(is_vscode_process(["/usr/lib/code/code"]))
        self.assertTrue(is_vscode_process(["code-oss", "."]))
        self.assertTrue(is_vscode_process(["codium", "--type=extensionHost"]))
        self.assertFalse(is_vscode_process(["python3", "script.py"]))

    @patch("backend.process.has_claude_vscode_extension", return_value=True)
    def test_vscode_active_with_extension(self, mock_has_ext):
        self.assertTrue(is_claude_cmdline(["/usr/lib/code/code", "--type=extensionHost"]))

    @patch("backend.process.has_claude_vscode_extension", return_value=False)
    def test_vscode_active_without_extension(self, mock_has_ext):
        self.assertFalse(is_claude_cmdline(["/usr/lib/code/code", "--type=extensionHost"]))


class TestStorageLatestSnapshot(unittest.TestCase):
    def test_get_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = StorageDB(db_path)
            self.assertIsNone(db.get_latest_snapshot())

            now = datetime.now(timezone.utc)
            db.insert_snapshot(
                five_hour_util=0.45,
                five_hour_resets=now,
                seven_day_util=0.80,
                seven_day_resets=now,
                timestamp=now,
            )

            latest = db.get_latest_snapshot()
            self.assertIsNotNone(latest)
            self.assertAlmostEqual(latest.five_hour_utilization, 0.45)
            self.assertAlmostEqual(latest.seven_day_all_utilization, 0.80)
