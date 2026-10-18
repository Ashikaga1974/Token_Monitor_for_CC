#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="${SCRIPT_DIR}/package"
OUTPUT_DIR="${HOME}/Downloads"
PLASMOID_NAME="com.buellsunited.TokenMonitor.plasmoid"
OUTPUT_FILE="${OUTPUT_DIR}/${PLASMOID_NAME}"

echo "==> 1. Compiling translations..."
"${SCRIPT_DIR}/build_translations.sh"

echo "==> 2. Syncing backend into Plasmoid package for KDE Store autarky..."
rm -rf "${PACKAGE_DIR}/contents/backend"
cp -r "${SCRIPT_DIR}/backend" "${PACKAGE_DIR}/contents/"
rm -rf "${PACKAGE_DIR}/contents/backend/__pycache__"
cp "${SCRIPT_DIR}/collect.sh" "${PACKAGE_DIR}/contents/collect.sh"
chmod +x "${PACKAGE_DIR}/contents/collect.sh"
chmod +x "${PACKAGE_DIR}/contents/scripts/start_daemon.sh"

echo "==> 3. Building Plasmoid package for KDE Store..."
mkdir -p "${OUTPUT_DIR}"

python3 - <<EOF
import os
import zipfile
from pathlib import Path

package_dir = Path("${PACKAGE_DIR}")
output_file = Path("${OUTPUT_FILE}")

if output_file.exists():
    output_file.unlink()

with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(package_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file == ".DS_Store" or file.endswith(".pyc"):
                continue
            full_path = Path(root) / file
            rel_path = full_path.relative_to(package_dir)
            zipf.write(full_path, arcname=str(rel_path))

print(f"==> Plasmoid successfully packaged: {output_file} ({output_file.stat().st_size} bytes)")
EOF

ls -lh "${OUTPUT_FILE}"
