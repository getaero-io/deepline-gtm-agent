#!/usr/bin/env bash
set -euo pipefail

echo "Deepline Hermes MCP setup"
echo "This script is intentionally conservative."
echo

if ! command -v hermes >/dev/null 2>&1; then
  echo "hermes not found in PATH. Install Hermes before running this."
  exit 1
fi

echo "Hermes version/check:"
hermes doctor || true

echo
echo "Available MCP catalog entries:"
hermes mcp catalog || true

echo
echo "Recommended manual installs/configures:"
cat <<'CMDS'

# P0: Deepline itself.
# Use Deepline CLI/API/session tooling for GTM provider access, workflow execution,
# logging, usage, and output lineage. Do not duplicate this through broad SaaS MCPs.
deepline --version
deepline tools search --categories admin --search_terms "session,logs,usage" || true

# P0: filesystem, but ONLY scoped to this repo/workspace.
# If catalog install is unavailable, add a filesystem MCP manually and restrict paths.
hermes mcp install filesystem || true
hermes mcp configure filesystem

# P1: GitHub for repo/PR workflows only when needed.
hermes mcp install github || true
hermes mcp configure github

# P2: Composio or app-specific MCPs.
# Install only when Deepline is not the right system for the action.
# Configure read/search/draft scopes first. Avoid send/delete/admin/bulk tools.
# hermes mcp install composio || true
# hermes mcp configure composio
# hermes mcp install slack || true
# hermes mcp install google-drive || true
# hermes mcp install hubspot || true
# hermes mcp install gmail || true

CMDS

echo
echo "Use Deepline as the GTM access/logging/observability layer."
echo "Do not enable send/delete/admin/bulk tools unless Jai explicitly approves."
