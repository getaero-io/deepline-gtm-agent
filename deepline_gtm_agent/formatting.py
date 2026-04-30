"""
Unified Markdown to Slack mrkdwn converter.

Single source of truth for all Slack formatting. Import this everywhere.
"""

import re


def _is_table_separator(line: str) -> bool:
    """Check if line is a markdown table separator like |---|---|"""
    stripped = line.strip().strip("|").strip()
    return bool(re.match(r"^[\s\-:|]+$", stripped)) and "---" in stripped


def _convert_table(m: re.Match) -> str:
    """Convert markdown table to readable Slack text."""
    lines = [l.strip() for l in m.group(0).strip().split("\n") if l.strip()]
    rows = []
    for line in lines:
        if _is_table_separator(line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return m.group(0)

    headers = rows[0]
    data_rows = rows[1:]

    # For small tables (<=3 cols), use key:value pairs
    if len(headers) <= 3 and data_rows:
        parts = []
        for row in data_rows:
            pair = " | ".join(
                f"*{headers[i]}:* {row[i]}" if i < len(headers) else row[i]
                for i in range(len(row))
            )
            parts.append(pair)
        return "\n".join(parts)

    # For wider tables: bold header row + data rows
    parts = [" | ".join(f"*{h}*" for h in headers)]
    for row in data_rows:
        parts.append(" | ".join(row))
    return "\n".join(parts)


def md_to_slack(text: str) -> str:
    """Convert Markdown to Slack mrkdwn. Handles tables, headers, formatting."""
    if not text:
        return ""

    # Preserve code blocks (don't transform inside them)
    code_blocks: list[str] = []
    def stash_code(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"__CB_{len(code_blocks) - 1}__"
    text = re.sub(r"```[\s\S]*?```", stash_code, text)

    # Tables: convert before other transformations
    # Match tables with | at edges
    text = re.sub(r"(?:^\|.+\|$\n?){2,}", _convert_table, text, flags=re.MULTILINE)
    # Match tables WITHOUT | at edges
    text = re.sub(r"(?:^[^\n|]+\|[^\n]+$\n?){2,}", _convert_table, text, flags=re.MULTILINE)

    # Ensure headers have preceding newline (fixes "Done.## Title" → "Done.\n\n*Title*")
    text = re.sub(r"([^\n])(#{1,6}\s)", r"\1\n\n\2", text)

    # Headers: ## Title → *Title* (but not table rows with |)
    def convert_header(m: re.Match) -> str:
        content = m.group(1)
        if "|" in content:
            return m.group(0)
        return f"*{content}*"
    text = re.sub(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", convert_header, text, flags=re.MULTILINE)

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
