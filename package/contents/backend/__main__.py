"""Entrypoint for executing the backend package directly via `python3 path/to/backend`."""
import sys
from pathlib import Path

# Sicherstellen, dass das übergeordnete Verzeichnis im Suchpfad liegt, damit Importe funktionieren
pkg_dir = Path(__file__).resolve().parent
parent_dir = pkg_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from backend.cli import main

if __name__ == "__main__":
    main()
