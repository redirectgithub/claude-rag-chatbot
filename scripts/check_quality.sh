#!/usr/bin/env bash
# Frontend code quality checks
# Usage: ./scripts/check_quality.sh [--fix]

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIX=false

for arg in "$@"; do
    case $arg in
        --fix) FIX=true ;;
    esac
done

echo "==> Running frontend quality checks..."

# Check node_modules exist
if [ ! -d "$ROOT/node_modules" ]; then
    echo "  Installing dev dependencies..."
    npm install --prefix "$ROOT" --silent
fi

# Prettier: format or check
if [ "$FIX" = true ]; then
    echo "  [Prettier] Formatting frontend files..."
    npx --prefix "$ROOT" prettier --write "$ROOT/frontend/**/*.{js,css,html}"
else
    echo "  [Prettier] Checking formatting..."
    npx --prefix "$ROOT" prettier --check "$ROOT/frontend/**/*.{js,css,html}"
fi

# ESLint
echo "  [ESLint]   Linting script.js..."
npx --prefix "$ROOT" eslint "$ROOT/frontend/script.js"

echo ""
echo "  All checks passed."
