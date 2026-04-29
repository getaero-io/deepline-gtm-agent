"""
Cost optimization utilities borrowed from Claude Code patterns.

Key optimizations:
1. Truncate large tool results with preview
2. Short error stacks (5 frames max)
3. Budget-aware skill descriptions
"""

import json
from typing import Any


MAX_TOOL_RESULT_CHARS = 8000
PREVIEW_SIZE = 2000


def truncate_tool_result(result: Any, max_chars: int = MAX_TOOL_RESULT_CHARS) -> Any:
    """Truncate large tool results to save tokens. Returns preview with indicator."""
    if isinstance(result, str):
        if len(result) <= max_chars:
            return result
        return f"{result[:PREVIEW_SIZE]}\n\n... (truncated, {len(result)} chars total)"

    if isinstance(result, dict):
        text = json.dumps(result, indent=2, default=str)
        if len(text) <= max_chars:
            return result
        return {
            "_truncated": True,
            "_original_size": len(text),
            "preview": text[:PREVIEW_SIZE] + "...",
        }

    if isinstance(result, list):
        text = json.dumps(result, indent=2, default=str)
        if len(text) <= max_chars:
            return result
        return {
            "_truncated": True,
            "_count": len(result),
            "_original_size": len(text),
            "first_items": result[:5] if len(result) > 5 else result,
        }

    return result


def short_error_stack(e: Exception, max_frames: int = 5) -> str:
    """Extract short error message with truncated stack trace."""
    import traceback
    lines = traceback.format_exception(type(e), e, e.__traceback__)
    if len(lines) <= max_frames + 1:
        return "".join(lines)

    header = lines[0]
    frames = [l for l in lines[1:-1] if l.strip().startswith("File ")]
    footer = lines[-1]

    if len(frames) <= max_frames:
        return "".join(lines)

    return header + "".join(frames[:max_frames]) + f"  ... ({len(frames) - max_frames} more frames)\n" + footer


def error_message(e: Exception) -> str:
    """Safe error message extraction."""
    return str(e) if e else "Unknown error"


def format_bytes(size: int) -> str:
    """Human-readable byte size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


SKILL_BUDGET_PERCENT = 0.01  # 1% of context window
MAX_SKILL_DESC_CHARS = 250


def truncate_skill_description(desc: str, max_chars: int = MAX_SKILL_DESC_CHARS) -> str:
    """Truncate skill descriptions to save context window space."""
    if len(desc) <= max_chars:
        return desc
    return desc[:max_chars - 3] + "..."
