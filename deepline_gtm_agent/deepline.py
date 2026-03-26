"""
Thin wrapper around the Deepline CLI for executing provider operations.
"""

import json
import subprocess
from typing import Any


def deepline_execute(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a Deepline tool operation and return the parsed result.

    Calls `deepline tools execute <operation> --payload '<json>'` and parses stdout.

    Raises:
        RuntimeError: If the CLI exits with a non-zero code or returns an error.
    """
    cmd = [
        "deepline",
        "tools",
        "execute",
        operation,
        "--payload",
        json.dumps(payload),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"deepline execute failed ({operation}): {result.stderr.strip() or result.stdout.strip()}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # Some operations return plain text (e.g. validation verdicts)
        return {"raw": result.stdout.strip()}


def deepline_balance() -> dict[str, Any]:
    """Return current Deepline credit balance."""
    result = subprocess.run(
        ["deepline", "billing", "balance", "--json"],
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout.strip()}
