"""Managed Agent session client.

Creates sessions, uploads resources, sends messages, streams events.
Used by the server and CLI. No framework dependencies.
"""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

import anthropic
import httpx

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / ".agent_config.json"

# Asset paths — resolved at import time, overridable via env vars.
DEEPLINE_BIN = Path(os.environ.get("DEEPLINE_BIN", shutil.which("deepline") or ""))
DEEPLINE_AUTH = Path(
    os.environ.get("DEEPLINE_AUTH", Path.home() / ".local/deepline/code-deepline-com/.env")
)
GTM_SKILL_DIR = Path(os.environ.get("GTM_SKILL_DIR", Path.home() / ".claude/skills/gtm-meta-skill"))


# Bootstrap: install CLI + auth + fix the container's DNS/proxy issue so
# Python (used by deepline CLI) can reach code.deepline.com.
BOOTSTRAP_MSG = (
    "Bootstrap the deepline CLI. Run ALL of these commands in a single bash call:\n\n"
    "```bash\n"
    "mkdir -p ~/.local/bin ~/.local/deepline/code-deepline-com\n"
    "cp /mnt/session/uploads/workspace/deepline ~/.local/bin/deepline\n"
    "chmod +x ~/.local/bin/deepline\n"
    "export PATH=\"$HOME/.local/bin:$PATH\"\n"
    "cp /mnt/session/uploads/workspace/deepline-auth.env ~/.local/deepline/code-deepline-com/.env\n"
    "\n"
    "# Fix DNS: the container uses an HTTP proxy that curl respects but Python doesn't.\n"
    "# Resolve the IP via curl and add to /etc/hosts so Python can reach the API.\n"
    "IP=$(curl -sI https://code.deepline.com 2>&1 | grep -i 'location\\|HTTP' | head -1 | grep -oP '\\d+\\.\\d+\\.\\d+\\.\\d+' || true)\n"
    "if [ -z \"$IP\" ]; then\n"
    "  IP=$(getent hosts code.deepline.com 2>/dev/null | awk '{print $1}' || true)\n"
    "fi\n"
    "if [ -z \"$IP\" ]; then\n"
    "  # Last resort: resolve via the proxy\n"
    "  IP=$(curl -sf --max-time 5 -o /dev/null -w '%{remote_ip}' https://code.deepline.com/ 2>/dev/null || true)\n"
    "fi\n"
    "if [ -n \"$IP\" ]; then\n"
    "  echo \"$IP code.deepline.com\" >> /etc/hosts\n"
    "fi\n"
    "\n"
    "# Also set NODE_OPTIONS for the playground backend used by deepline enrich\n"
    "export NODE_OPTIONS=\"--use-env-proxy\"\n"
    "export NODE_TLS_REJECT_UNAUTHORIZED=0\n"
    "\n"
    "deepline auth status\n"
    "```\n"
    "\n"
    "Do NOT output anything about the bootstrap. Just run it silently and move on to the user's task."
)

# File extensions worth uploading from skill docs.
_DOC_SUFFIXES = {".md", ".json", ".py", ".csv", ".txt", ".mjs"}

# --- Skill docs CDN (same source as LangGraph version) ---
SKILLS_BASE = "https://code.deepline.com/.well-known/skills/gtm-meta-skill"
CORE_SKILL_DOCS = [
    "SKILL.md",
    "finding-companies-and-contacts.md",
    "enriching-and-researching.md",
    "writing-outreach.md",
    "recipes/build-tam.md",
    "recipes/linkedin-url-lookup.md",
    "recipes/portfolio-prospecting.md",
    "provider-playbooks/apollo.md",
    "provider-playbooks/crustdata.md",
    "provider-playbooks/dropleads.md",
    "provider-playbooks/hunter.md",
    "provider-playbooks/leadmagic.md",
    "provider-playbooks/deepline_native.md",
    "provider-playbooks/lemlist.md",
    "provider-playbooks/instantly.md",
    "provider-playbooks/smartlead.md",
    "provider-playbooks/heyreach.md",
    "provider-playbooks/zerobounce.md",
    "provider-playbooks/exa.md",
    "provider-playbooks/firecrawl.md",
    "provider-playbooks/apify.md",
    "provider-playbooks/forager.md",
    "provider-playbooks/icypeas.md",
    "provider-playbooks/prospeo.md",
    "provider-playbooks/peopledatalabs.md",
    "provider-playbooks/ai_ark.md",
    "provider-playbooks/attio.md",
    "provider-playbooks/hubspot.md",
    "provider-playbooks/salesforce.md",
    "provider-playbooks/serper.md",
    "provider-playbooks/parallel.md",
    "provider-playbooks/deeplineagent.md",
]

# Cache: fetched once at server startup, reused across sessions.
_cached_skill_files: dict[str, bytes] = {}


def fetch_skill_docs_from_cdn() -> dict[str, bytes]:
    """Fetch all skill docs from the Deepline CDN. Returns {relative_path: content}."""
    global _cached_skill_files
    if _cached_skill_files:
        return _cached_skill_files

    results = {}
    with httpx.Client(timeout=15) as http:
        for path in CORE_SKILL_DOCS:
            try:
                resp = http.get(f"{SKILLS_BASE}/{path}")
                if resp.status_code == 200 and resp.content:
                    results[path] = resp.content
            except Exception as e:
                logger.warning("Failed to fetch skill doc %s: %s", path, e)

    logger.info("Fetched %d/%d skill docs from CDN", len(results), len(CORE_SKILL_DOCS))
    _cached_skill_files = results
    return results


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


def _upload_bytes(client: anthropic.Anthropic, content: bytes, name: str) -> str:
    """Upload raw bytes as a file."""
    with tempfile.NamedTemporaryFile(suffix=f"_{name}", delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        tmp.seek(0)
        return client.beta.files.upload(file=(name, tmp)).id


def _upload_resources(client: anthropic.Anthropic) -> list[dict]:
    """Upload deepline binary, auth, and skill docs. Returns resource list."""
    resources = []

    # 1. Deepline binary
    if DEEPLINE_BIN.exists():
        fid = _upload_file(client, DEEPLINE_BIN)
        resources.append({"type": "file", "file_id": fid, "mount_path": "/workspace/deepline"})
        logger.info("Uploaded deepline binary")
    else:
        logger.warning("Deepline binary not found at %s", DEEPLINE_BIN)

    # 2. Auth credentials
    if DEEPLINE_AUTH.exists():
        fid = _upload_file(client, DEEPLINE_AUTH, "deepline-auth.env")
        resources.append({"type": "file", "file_id": fid, "mount_path": "/workspace/deepline-auth.env"})
        logger.info("Uploaded deepline auth")
    else:
        logger.warning("Deepline auth not found at %s", DEEPLINE_AUTH)

    # 3. GTM skill docs — prefer local dir, fall back to CDN cache
    skill_count = 0
    if GTM_SKILL_DIR.exists():
        for fpath in sorted(GTM_SKILL_DIR.rglob("*")):
            if fpath.is_file() and fpath.suffix in _DOC_SUFFIXES:
                rel = fpath.relative_to(GTM_SKILL_DIR)
                try:
                    fid = _upload_file(client, fpath, fpath.name)
                    resources.append({
                        "type": "file",
                        "file_id": fid,
                        "mount_path": f"/workspace/gtm-meta-skill/{rel}",
                    })
                    skill_count += 1
                except Exception as e:
                    logger.warning("Failed to upload skill doc %s: %s", rel, e)
        logger.info("Uploaded %d skill docs from local dir", skill_count)
    else:
        # Fall back to CDN-cached skill docs
        skill_files = fetch_skill_docs_from_cdn()
        for path, content in skill_files.items():
            try:
                # Use just the filename for upload (no path separators)
                fname = path.replace("/", "_")
                fid = _upload_bytes(client, content, fname)
                resources.append({
                    "type": "file",
                    "file_id": fid,
                    "mount_path": f"/workspace/gtm-meta-skill/{path}",
                })
                skill_count += 1
            except Exception as e:
                logger.warning("Failed to upload CDN skill doc %s: %s", path, e)
        logger.info("Uploaded %d skill docs from CDN cache", skill_count)

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

    logger.info("Creating session with %d resources", len(resources))

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

    full_prompt = f"{BOOTSTRAP_MSG}\n\nThen do this:\n{prompt}" if bootstrap else prompt
    send_message(client, session_id, full_prompt)
    yield from stream_events(client, session_id)
