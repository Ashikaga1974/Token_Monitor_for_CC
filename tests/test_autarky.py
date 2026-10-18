"""
Unit tests for Plasmoid autarky, backend packaging, and self-healing startup script.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class TestPlasmoidAutarky(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.backend_dir = self.repo_root / "backend"
        self.package_backend_dir = self.repo_root / "package" / "contents" / "backend"
        self.start_script = self.repo_root / "package" / "contents" / "scripts" / "start_daemon.sh"

    def test_backend_main_entrypoint(self):
        """Testet, dass backend/__main__.py direkt mit python3 path/to/backend ausführbar ist."""
        main_py = self.backend_dir / "__main__.py"
        self.assertTrue(main_py.is_file(), "backend/__main__.py muss existieren")

        # Ausführung von python3 backend --help prüfen
        res = subprocess.run(
            [sys.executable, str(self.backend_dir), "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.repo_root),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Token Monitor for Claude Code CLI Backend", res.stdout)

    def test_start_daemon_script_exists_and_executable(self):
        """Testet, dass start_daemon.sh existiert, ausführbar ist und syntaktisch fehlerfrei ist."""
        self.assertTrue(self.start_script.is_file(), "start_daemon.sh muss existieren")
        self.assertTrue(os.access(self.start_script, os.X_OK), "start_daemon.sh muss ausführbar sein")

        # Bash-Syntax-Check mit bash -n
        res = subprocess.run(
            ["bash", "-n", str(self.start_script)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Syntaxfehler in start_daemon.sh: {res.stderr}")

    def test_package_contents_backend_sync(self):
        """Testet, dass alle Python-Dateien aus backend/ auch in package/contents/backend/ vorliegen."""
        self.assertTrue(self.package_backend_dir.is_dir(), "package/contents/backend muss existieren")

        source_files = {p.name: p for p in self.backend_dir.glob("*.py")}
        target_files = {p.name: p for p in self.package_backend_dir.glob("*.py")}

        for fname, src_path in source_files.items():
            self.assertIn(fname, target_files, f"Datei {fname} fehlt in package/contents/backend/")
            # Inhalt vergleichen
            src_content = src_path.read_text(encoding="utf-8")
            target_content = target_files[fname].read_text(encoding="utf-8")
            self.assertEqual(src_content, target_content, f"Inhalt von {fname} weicht in package/contents/backend/ ab")


if __name__ == "__main__":
    unittest.main()
