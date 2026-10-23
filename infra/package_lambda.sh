#!/usr/bin/env bash
# ContextFuse – Package Backend for AWS Lambda
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build/lambda"
ZIP_FILE="${ROOT_DIR}/dist/contextfuse-lambda.zip"

echo "=== Packaging ContextFuse Backend for AWS Lambda ==="
rm -rf "${BUILD_DIR}" "${ZIP_FILE}"
mkdir -p "${BUILD_DIR}" "$(dirname "${ZIP_FILE}")"

# Install production dependencies into build directory
echo "Installing dependencies..."
pip install -r "${ROOT_DIR}/backend/requirements.txt" \
  --target "${BUILD_DIR}" \
  --platform manylinux2014_x86_64 \
  --only-binary=:all: \
  --upgrade \
  --quiet

# Copy application source code
echo "Copying application code..."
cp -r "${ROOT_DIR}/backend/app" "${BUILD_DIR}/"

# Package into zip
echo "Creating deployment artifact: ${ZIP_FILE}..."
cd "${BUILD_DIR}"
zip -qr "${ZIP_FILE}" .

echo "=== Lambda package created successfully: ${ZIP_FILE} ($(du -h "${ZIP_FILE}" | cut -f1)) ==="
