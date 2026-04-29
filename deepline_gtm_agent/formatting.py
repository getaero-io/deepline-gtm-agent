"""
Unified Markdown to Slack mrkdwn converter.

Single source of truth for all Slack formatting. Import this everywhere.
"""

import re

def md_to_slack(text: str) -> str:
    """Convert Markdown to Slack mrkdwn. Minimal, predictable transformations."""
    if not text:
        return ""

    # Preserve code blocks (don't transform inside them)
    code_blocks: list[str] = []
    def stash_code(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"__CB_{len(code_blocks) - 1}__"
    text = re.sub(r"```[\s\S]*?```", stash_code, text)

    # Ensure headers have preceding newline (fixes "Done.## Title" → "Done.\n\n*Title*")
    text = re.sub(r"([^\n])(#{1,6}\s)", r"\1\n\n\2", text)

    # Headers: ## Title → *Title*
    text = re.sub(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", r"*\1*", text, flags=re.MULTILINE)

    # Bold: **text** → *text*
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"*\1*", text)
    text = re.sub(r"__([^_\n]+)__", r"*\1*", text)

    # Strikethrough: ~~text~~ → ~text~
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)

    # Links: [text](url) → <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)

    # Bullets: - item or * item → • item
    text = re.sub(r"^[ \t]*[-*]\s+", "• ", text, flags=re.MULTILINE)

    # Horizontal rules: --- → (remove)
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Blockquotes: > text → text
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        text = text.replace(f"__CB_{i}__", block)

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def truncate_for_slack(text: str, max_len: int = 3900) -> list[str]:
    """Split text into Slack-safe chunks (max 4000 chars, we use 3900 for safety)."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 > max_len:
            if current.strip():
                chunks.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks
