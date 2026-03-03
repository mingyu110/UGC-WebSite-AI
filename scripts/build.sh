#!/bin/bash
# Build script for UGC AI Demo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Building UGC AI Demo ==="

# Build Python package
echo "Building Python package..."
cd "$PROJECT_ROOT"
pip install -e . --quiet

# Build CDK infrastructure
echo "Building CDK infrastructure..."
cd "$PROJECT_ROOT/infra"
npm install --quiet
npm run build

echo "=== Build complete ==="
