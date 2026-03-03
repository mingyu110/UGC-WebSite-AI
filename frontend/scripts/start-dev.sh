#!/bin/bash
# =============================================================================
# UGC AI Demo - Frontend Development Server Startup Script
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "========================================"
echo "  UGC AI Demo - Frontend Dev Server"
echo "========================================"
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "[*] Installing dependencies..."
    npm install
else
    echo "[*] Dependencies already installed"
fi

# Check for .env file, copy from .env.example if not exists
if [ ! -f ".env.local" ] && [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "[*] Creating .env.local from .env.example..."
        cp .env.example .env.local
    else
        echo "[*] Creating default .env.local..."
        cat > .env.local << EOF
MOCK_MODE=true
AGENT_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK=true
NEXT_PUBLIC_AGENT_URL=http://localhost:8000
EOF
    fi
fi

# Parse arguments
MOCK_MODE=${MOCK_MODE:-true}
PORT=${PORT:-3000}

while [[ $# -gt 0 ]]; do
    case $1 in
        --mock)
            MOCK_MODE=true
            shift
            ;;
        --no-mock)
            MOCK_MODE=false
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Export environment variables
export MOCK_MODE="$MOCK_MODE"
export NEXT_PUBLIC_USE_MOCK="$MOCK_MODE"

echo ""
echo "[*] Configuration:"
echo "    - Mock Mode: $MOCK_MODE"
echo "    - Port: $PORT"
echo "    - Agent URL: ${AGENT_URL:-http://localhost:8000}"
echo ""

# Start the development server
echo "[*] Starting Next.js development server..."
echo ""

npm run dev -- -p "$PORT"
