#!/usr/bin/env bash
# ============================================================
# OSINT Intelligence System — Archive Script
# ============================================================
# Creates a distributable ZIP archive of the entire project.
#
# Usage:
#   chmod +x archive.sh
#   ./archive.sh
#
# Output: osint-intelligence-YYYY-MM-DD.zip in the parent directory
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="osint-intelligence"
DATE_TAG=$(date +%Y-%m-%d)
ARCHIVE_NAME="${PROJECT_NAME}-${DATE_TAG}.zip"
OUTPUT_PATH="$(dirname "$SCRIPT_DIR")/${ARCHIVE_NAME}"

echo "=============================================="
echo "  OSINT Intelligence System — Archive Builder"
echo "=============================================="
echo ""
echo "  Project : $SCRIPT_DIR"
echo "  Output  : $OUTPUT_PATH"
echo ""

cd "$SCRIPT_DIR"

# Patterns to exclude from the archive
EXCLUDES=(
    "*.pyc"
    "*/__pycache__/*"
    "*/.git/*"
    "*/.env"
    "*/logs/*"
    "*/.DS_Store"
    "*/Thumbs.db"
    "*/.pytest_cache/*"
    "*/.mypy_cache/*"
    "*/.ruff_cache/*"
    "*/node_modules/*"
    "*.egg-info/*"
    "*/dist/*"
    "*/build/*"
    "*/.venv/*"
    "*/venv/*"
    "*/env/*"
    "*/htmlcov/*"
    "*/${ARCHIVE_NAME}"
)

EXCLUDE_ARGS=()
for pattern in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS+=("--exclude=${pattern}")
done

# Check zip is available
if ! command -v zip &>/dev/null; then
    echo "ERROR: 'zip' command not found."
    echo "Install it with: sudo apt-get install zip  (Debian/Ubuntu)"
    echo "                 brew install zip           (macOS)"
    exit 1
fi

echo "Building archive..."
zip -r "$OUTPUT_PATH" . "${EXCLUDE_ARGS[@]}" -q

ARCHIVE_SIZE=$(du -sh "$OUTPUT_PATH" | cut -f1)
FILE_COUNT=$(unzip -l "$OUTPUT_PATH" | tail -1 | awk '{print $2}')

echo ""
echo "✅  Archive created successfully!"
echo ""
echo "  File  : $OUTPUT_PATH"
echo "  Size  : $ARCHIVE_SIZE"
echo "  Files : $FILE_COUNT"
echo ""
echo "Deployment commands:"
echo "  scp ${ARCHIVE_NAME} user@your-vps:/opt/"
echo "  ssh user@your-vps 'cd /opt && unzip ${ARCHIVE_NAME} -d osint-intelligence'"
echo ""
