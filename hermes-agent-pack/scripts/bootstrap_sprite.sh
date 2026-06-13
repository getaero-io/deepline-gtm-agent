#!/usr/bin/env bash
set -euo pipefail

SPRITE_NAME="${1:-spawn-k2qb}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v sprite >/dev/null 2>&1; then
  echo "sprite CLI not found. Install with:"
  echo "curl -fsSL https://sprites.dev/install.sh | sh"
  exit 1
fi

echo "Using Sprite: ${SPRITE_NAME}"
sprite use "${SPRITE_NAME}" || true

echo "Verifying remote runtime..."
sprite exec -s "${SPRITE_NAME}" -- bash -lc 'pwd; command -v hermes || true; hermes --help | head -40 || true'

echo "Creating workspace on Sprite..."
sprite exec -s "${SPRITE_NAME}" -- bash -lc 'mkdir -p ~/deepline-hermes-repo'

cat <<'NEXT'

Next manual step:

Upload or git clone this repo into ~/deepline-hermes-repo on the Sprite, then run:

  cd ~/deepline-hermes-repo
  bash scripts/install_hermes_mcps.sh

Then paste prompts/00_seed_hermes.md into Hermes.

NEXT

