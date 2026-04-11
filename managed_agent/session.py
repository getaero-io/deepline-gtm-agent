"""Managed Agent session client.

Creates sessions, uploads resources, sends messages, streams events.
Used by the server and CLI. No framework dependencies.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Iterator

import anthropic

CONFIG_PATH = Path(__file__).parent / ".agent_config.json"

# Asset paths — resolved at import time, overridable via env vars.
DEEPLINE_BIN = Path(os.environ.get("DEEPLINE_BIN", shutil.which("deepline") or ""))
DEEPLINE_AUTH = Path(
    os.environ.get("DEEPLINE_AUTH", Path.home() / ".local/deepline/code-deepline-com/.env")
)
GTM_SKILL_DIR = Path(os.environ.get("GTM_SKILL_DIR", Path.home() / ".claude/skills/gtm-meta-skill"))


BOOTSTRAP_MSG = (
    "Bootstrap the deepline CLI: "
    "mkdir -p ~/.local/bin ~/.local/deepline/code-deepline-com && "
    "cp /mnt/session/uploads/workspace/deepline ~/.local/bin/deepline && "
    "chmod +x ~/.local/bin/deepline && "
    "export PATH=\"$HOME/.local/bin:$PATH\" && "
    "cp /mnt/session/uploads/workspace/deepline-auth.env ~/.local/deepline/code-deepline-com/.env && "
    "deepline auth status"
)

# File extensions worth uploading from skill docs.
_DOC_SUFFIXES = {".md", ".json", ".py", ".csv", ".txt", ".mjs"}


def _load_config() -> dict:
    """Load agent config from env vars (preferred) or .agent_config.json."""
    agent_id = os.environ.get("MANAGED_AGENT_ID")
    env_id = os.environ.get("MANAGED_ENVIRONMENT_ID")
    if agent_id and env_id:
        return {"agent_id": agent_id, "environment_id": env_id}
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"No {CONFIG_PATH} and MANAGED_AGENT_ID/MANAGED_ENVIRONMENT_ID not set. "
            "Run setup.py first or set env vars."
        )
    return json.loads(CONFIG_PATH.read_text())


def _upload_file(client: anthropic.Anthropic, path: Path, name: str | None = None) -> str:
    with open(path, "rb") as f:
        return client.beta.files.upload(file=(name or path.name, f)).id


def _upload_resources(client: anthropic.Anthropic) -> list[dict]:
    """Upload deepline binary, auth, and skill docs. Returns resource list."""
    resources = []

    if DEEPLINE_BIN.exists():
        fid = _upload_file(client, DEEPLINE_BIN)
        resources.append({"type": "file", "file_id": fid, "mount_path": "/workspace/deepline"})

    if DEEPLINE_AUTH.exists():
        fid = _upload_file(client, DEEPLINE_AUTH, "deepline-auth.env")
        resources.append({"type": "file", "file_id": fid, "mount_path": "/workspace/deepline-auth.env"})

    if GTM_SKILL_DIR.exists():
        for fpath in sorted(GTM_SKILL_DIR.rglob("*")):
            if fpath.is_file() and fpath.suffix in _DOC_SUFFIXES:
                rel = fpath.relative_to(GTM_SKILL_DIR)
                fid = _upload_file(client, fpath, fpath.name)
                resources.append({
                    "type": "file",
                    "file_id": fid,
                    "mount_path": f"/workspace/gtm-meta-skill/{rel}",
                })

    return resources


def create_session(
    client: anthropic.Anthropic,
    title: str = "Deepline GTM",
    extra_resources: list[dict] | None = None,
) -> str:
    """Create a new managed-agent session with all resources mounted. Returns session_id."""
    config = _load_config()
    resources = _upload_resources(client)
    if extra_resources:
        resources.extend(extra_resources)

    safe_title = title.replace("`", "").replace("\n", " ")[:80] or "Deepline GTM"
    session = client.beta.sessions.create(
        agent=config["agent_id"],
        environment_id=config["environment_id"],
        title=safe_title,
        resources=resources,
    )
    return session.id


def send_message(client: anthropic.Anthropic, session_id: str, text: str) -> None:
    """Send a user message to a session."""
    client.beta.sessions.events.send(
        session_id=session_id,
        events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
    )


def stream_events(client: anthropic.Anthropic, session_id: str) -> Iterator[dict]:
    """Yield simplified event dicts from the session stream.

    Each dict has: type, text|command|name (depending on event type).
    Stops on idle (non-requires_action) or terminated.
    """
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        for event in stream:
            etype = getattr(event, "type", None)

            if etype == "agent.message":
                for block in getattr(event, "content", []):
                    if getattr(block, "type", None) == "text":
                        yield {"type": "text", "text": block.text}

            elif etype == "agent.tool_use":
                name = getattr(event, "name", "?")
                inp = getattr(event, "input", {})
                if name == "bash":
                    yield {"type": "tool", "name": "bash", "command": inp.get("command", "")}
                else:
                    yield {"type": "tool", "name": name}

            elif etype == "session.status_idle":
                stop_reason = getattr(event, "stop_reason", None)
                stop_type = getattr(stop_reason, "type", None) if stop_reason else None
                if stop_type == "requires_action":
                    continue
                yield {"type": "done", "reason": stop_type or "unknown"}
                return

            elif etype == "session.status_terminated":
                yield {"type": "done", "reason": "terminated"}
                return


def run_prompt(
    client: anthropic.Anthropic,
    prompt: str,
    bootstrap: bool = True,
    title: str | None = None,
) -> Iterator[dict]:
    """Full lifecycle: create session, bootstrap, send prompt, stream results."""
    session_id = create_session(client, title=title or prompt[:60])

    full_prompt = f"{BOOTSTRAP_MSG}\n\nThen: {prompt}" if bootstrap else prompt
    send_message(client, session_id, full_prompt)
    yield from stream_events(client, session_id)
