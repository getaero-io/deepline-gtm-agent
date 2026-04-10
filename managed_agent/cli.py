"""CLI runner — same as run_session.py but cleaned up.

Usage:
    python cli.py "your prompt here"
    python cli.py --eval smoke
    python cli.py --no-bootstrap "deepline auth status"
"""

import json
import re
import sys
from pathlib import Path

import anthropic

from session import run_prompt

EVALS_YML = Path.home() / "dev/deepline-api/docs/evals.yml"


def resolve_eval_prompt(eval_id: str) -> str:
    content = EVALS_YML.read_text()
    pattern = rf'-\s+id:\s+{re.escape(eval_id)}\b(.*?)(?=\n  -\s+id:|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        sys.exit(f"Eval '{eval_id}' not found in {EVALS_YML}")
    block = match.group(1)

    prompt_match = re.search(r'prompt:\s*>\s*\n((?:\s{6,}.*\n?)+)', block)
    if prompt_match:
        lines = prompt_match.group(1).strip().split('\n')
        return ' '.join(line.strip() for line in lines)

    prompt_match = re.search(r'prompt:\s*[>|]\s*\n((?:\s+.*\n?)+)', block)
    if not prompt_match:
        sys.exit(f"No prompt found for eval '{eval_id}'")

    raw = prompt_match.group(1)
    indent = len(raw) - len(raw.lstrip())
    lines = raw.rstrip('\n').split('\n')
    return '\n'.join(line[indent:] if len(line) >= indent else line.strip() for line in lines)


def main() -> None:
    args = sys.argv[1:]
    bootstrap = True
    eval_id = None
    prompt_parts = []

    i = 0
    while i < len(args):
        if args[i] == "--no-bootstrap":
            bootstrap = False
            i += 1
        elif args[i] == "--eval":
            eval_id = args[i + 1]
            i += 2
        else:
            prompt_parts.append(args[i])
            i += 1

    if eval_id:
        prompt = resolve_eval_prompt(eval_id).replace("${OUTPUT_DIR}", "/mnt/session/outputs")
        print(f"[eval: {eval_id}]")
    elif prompt_parts:
        prompt = " ".join(prompt_parts)
    else:
        prompt = "Run deepline auth status and tell me which org I'm connected to."

    client = anthropic.Anthropic()
    for evt in run_prompt(client, prompt, bootstrap=bootstrap, title=eval_id or prompt[:60]):
        if evt["type"] == "text":
            print(evt["text"], end="", flush=True)
        elif evt["type"] == "tool":
            cmd = evt.get("command", evt.get("name", ""))[:200]
            print(f"\n$ {cmd}", flush=True)
        elif evt["type"] == "done":
            print(f"\n\n[{evt['reason']}]")


if __name__ == "__main__":
    main()
