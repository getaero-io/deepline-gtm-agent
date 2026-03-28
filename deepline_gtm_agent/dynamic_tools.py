"""
Dynamic Deepline tool registration.

Fetches the full Deepline tool catalog at startup and exposes a single
`deepline_call(tool_id, payload)` tool that gives the agent access to all
438+ Deepline integrations (HubSpot, Salesforce, Attio, Apollo, Instantly,
Lemlist, Smartlead, Crustdata, Firecrawl, Apify, ZeroBounce, etc.).

The catalog is cached to disk (~/.cache/deepline_agent/catalog.json) for 24h
so subsequent startups are instant.
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from deepline_gtm_agent.deepline import deepline_execute, DEEPLINE_API_BASE

logger = logging.getLogger(__name__)

CATALOG_CACHE_PATH = Path.home() / ".cache" / "deepline_agent" / "catalog.json"
CATALOG_TTL_SECONDS = 86_400  # 24 hours

# Skip utility / local-only tools that are not useful in a hosted agent context
_SKIP_TOOL_IDS = {"read_file", "run_javascript", "call_local_claude_code", "call_local_codex"}


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------


def _load_catalog_cache() -> Optional[list[dict]]:
    try:
        if CATALOG_CACHE_PATH.exists():
            raw = json.loads(CATALOG_CACHE_PATH.read_text())
            if time.time() - raw.get("cached_at", 0) < CATALOG_TTL_SECONDS:
                return raw["tools"]
    except Exception:
        pass
    return None


def _save_catalog_cache(tools: list[dict]) -> None:
    try:
        CATALOG_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CATALOG_CACHE_PATH.write_text(
            json.dumps({"cached_at": time.time(), "tools": tools})
        )
    except Exception as e:
        logger.warning("Could not cache tool catalog: %s", e)


def _fetch_catalog_from_cli() -> list[dict]:
    """Run `deepline tools list --json` and return the tools list."""
    try:
        result = subprocess.run(
            ["deepline", "tools", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("tools", data.get("integrations", []))
    except Exception as e:
        logger.warning("deepline tools list --json failed: %s", e)
    return []


def _fetch_catalog_from_api() -> list[dict]:
    """Try to fetch the catalog via the Deepline HTTP API."""
    api_key = os.environ.get("DEEPLINE_API_KEY", "")
    if not api_key:
        return []
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(
                f"{DEEPLINE_API_BASE}/api/v2/integrations/list",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tools", data.get("integrations", []))
    except Exception as e:
        logger.warning("Deepline API catalog fetch failed: %s", e)
    return []


def load_tool_catalog(force_refresh: bool = False) -> list[dict]:
    """
    Return the full Deepline tool catalog.

    Order of preference:
    1. Disk cache (if fresh and not force_refresh)
    2. Deepline HTTP API (if DEEPLINE_API_KEY is set)
    3. deepline CLI subprocess
    """
    if not force_refresh:
        cached = _load_catalog_cache()
        if cached is not None:
            logger.info("Loaded %d Deepline tools from disk cache", len(cached))
            return cached

    tools = _fetch_catalog_from_api() or _fetch_catalog_from_cli()
    tools = [t for t in tools if t.get("toolId") not in _SKIP_TOOL_IDS]

    if tools:
        _save_catalog_cache(tools)
        logger.info("Loaded and cached %d Deepline tools", len(tools))
    else:
        logger.warning("Could not load Deepline tool catalog — deepline_call will have no catalog")

    return tools


# ---------------------------------------------------------------------------
# Catalog → description text
# ---------------------------------------------------------------------------

# Human-readable category labels
_CATEGORY_LABELS = {
    "people_search": "People Search",
    "company_search": "Company Search",
    "people_enrich": "People Enrichment",
    "company_enrich": "Company Enrichment",
    "email_finder": "Email Finder",
    "email_verify": "Email Verification",
    "phone_finder": "Phone Finder",
    "research": "Web Research & Intelligence",
    "outbound_tools": "Outbound / Sequencing",
    "admin": "CRM & Admin (HubSpot, Salesforce, Attio, Lemlist, Instantly, Smartlead…)",
    "automation": "Automation & Scraping",
    "autocomplete": "Autocomplete / Lookup",
}

# High-priority providers — listed first in the catalog
_PRIORITY_PROVIDERS = {
    "hubspot", "salesforce", "attio", "instantly", "lemlist", "smartlead",
    "heyreach", "apollo", "crustdata", "hunter", "exa", "dropleads",
    "zerobounce", "firecrawl", "apify", "leadmagic", "peopledatalabs",
    "icypeas", "prospeo", "forager",
}


def _build_catalog_text(tools: list[dict]) -> str:
    """
    Build a compact, readable catalog text to embed in the deepline_call description.

    Format:
        ## Category
          tool_id — short description
    """
    by_category: dict[str, list[tuple[str, str, str]]] = {}  # cat → [(priority, tool_id, desc)]

    for t in tools:
        tool_id = t.get("toolId", "")
        provider = t.get("provider", "")
        cats = t.get("categories") or ["other"]
        cat = cats[0]

        raw_desc = t.get("description") or t.get("bestFor") or t.get("displayName") or ""
        if "|" in raw_desc:
            raw_desc = raw_desc.split("|")[0].strip()
        desc = raw_desc[:110] + "…" if len(raw_desc) > 110 else raw_desc

        priority = "0" if provider.lower() in _PRIORITY_PROVIDERS else "1"
        by_category.setdefault(cat, []).append((priority, tool_id, desc))

    lines: list[str] = []
    # Priority categories first
    priority_cats = ["admin", "outbound_tools", "people_search", "company_search",
                     "people_enrich", "company_enrich", "email_finder", "email_verify",
                     "phone_finder", "research", "automation"]
    ordered_cats = priority_cats + [c for c in sorted(by_category) if c not in priority_cats]

    for cat in ordered_cats:
        entries = by_category.get(cat)
        if not entries:
            continue
        entries.sort()  # priority first, then alphabetical
        label = _CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())
        lines.append(f"\n### {label}")
        for _, tool_id, desc in entries:
            lines.append(f"  {tool_id} — {desc}" if desc else f"  {tool_id}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LangChain tool factory
# ---------------------------------------------------------------------------


class _DeeplineCallInput(BaseModel):
    tool_id: str = Field(
        description=(
            "The Deepline tool ID — e.g. 'hubspot_create_contact', 'apollo_search_people', "
            "'instantly_add_to_campaign', 'salesforce_create_lead'. "
            "See the full catalog in this tool's description."
        )
    )
    payload: dict = Field(
        description=(
            "Tool-specific payload dict. Field names and types vary by tool. "
            "Consult the Deepline skill docs (injected in the system prompt) or the tool catalog "
            "description for the correct schema. When in doubt, include only the fields you know."
        ),
        default_factory=dict,
    )


def make_deepline_call_tool(catalog: Optional[list[dict]] = None) -> StructuredTool:
    """
    Build and return the `deepline_call` LangChain StructuredTool.

    Injects the full Deepline tool catalog into the tool description so Claude
    can discover available tools without a separate lookup step.
    """
    tools = catalog or []
    catalog_text = _build_catalog_text(tools) if tools else "(catalog unavailable — retry or use deepline CLI)"

    description = (
        "Call any Deepline integration by tool_id + payload.\n\n"
        "Use this for:\n"
        "• CRM writes/reads: HubSpot (contacts, companies, deals, notes, tasks), "
        "Salesforce (leads, contacts, accounts, opportunities), Attio (person/company/deal records)\n"
        "• Outreach: Instantly, Lemlist, Smartlead (campaigns, sequences, lead management), "
        "HeyReach (LinkedIn campaigns)\n"
        "• Advanced enrichment: Apollo, Crustdata, PDL, Icypeas, Prospeo, Forager, Dropleads, "
        "LeadMagic, Hunter, ZeroBounce\n"
        "• Research & scraping: Exa, Firecrawl, Apify, Serper, BuiltWith, Adyntel\n"
        "• Data warehouses: Snowflake, Cloudflare\n\n"
        "Tool catalog (tool_id — description):"
        + catalog_text
    )

    def _call(tool_id: str, payload: dict = {}) -> Any:
        try:
            return deepline_execute(tool_id, payload)
        except Exception as e:
            err_str = str(e)
            # Parse structured error codes from the Deepline API response
            structured = {}
            try:
                import json as _json
                # Error text may contain the JSON body after the prefix
                brace_idx = err_str.find("{")
                if brace_idx >= 0:
                    structured = _json.loads(err_str[brace_idx:])
            except Exception:
                pass

            code = structured.get("code", "")
            if code == "INTEGRATION_CREDENTIALS_MISSING":
                provider = structured.get("integration_provider", tool_id.split("_")[0])
                return {
                    "error": "credentials_missing",
                    "message": (
                        f"No {provider.upper()} account connected. "
                        f"Go to https://code.deepline.com/dashboard/billing to connect your {provider} account, "
                        "then retry this request."
                    ),
                    "tool_id": tool_id,
                    "action_required": "Connect account at https://code.deepline.com/dashboard/billing",
                }

            return {"error": err_str[:500], "tool_id": tool_id, "payload_keys": list(payload.keys())}

    return StructuredTool(
        name="deepline_call",
        description=description,
        func=_call,
        args_schema=_DeeplineCallInput,
    )
