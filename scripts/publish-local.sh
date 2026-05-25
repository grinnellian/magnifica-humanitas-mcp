#!/usr/bin/env bash
set -euo pipefail

# Publish npm + PyPI from a local Docker container.
# Usage: ./scripts/publish-local.sh
# Requires: NPM_TOKEN and PYPI_TOKEN env vars (or pass interactively)

VERSION=$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)
echo "Publishing v${VERSION}..."

# PyPI
echo "==> PyPI"
docker run --rm -v "$(pwd)":/app -w /app \
  -e TWINE_USERNAME=__token__ \
  -e TWINE_PASSWORD="${PYPI_TOKEN:?Set PYPI_TOKEN}" \
  python:3.12-slim bash -c "
    pip install -q build twine &&
    python -m build &&
    twine upload dist/*
  "

# npm
echo "==> npm"
docker run --rm -v "$(pwd)":/app -w /app \
  node:20-slim bash -c "
    echo '//registry.npmjs.org/:_authToken=${NPM_TOKEN:?Set NPM_TOKEN}' > ~/.npmrc &&
    npm publish --access public
  "

echo "Done. Tag and push to trigger Docker + MCP registry via CI."
