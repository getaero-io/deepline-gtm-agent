"""Transcript-derived GTM agent workflow presets.

These presets are intentionally simple data structures so they can power docs,
API discovery, UI dropdowns, or future generated examples without creating a
second agent runtime.
"""

from __future__ import annotations

from typing import Any


WORKFLOW_PRESETS: dict[str, dict[str, Any]] = {
    "inbound_lead_approval": {
        "title": "Inbound lead research + rep approval",
        "speaker_pattern": "LangChain / Vishnu Suresh",
        "why": (
            "A lead should not go straight from CRM to outreach. The agent should "
            "research, check reasons not to act, draft with sources, and route to "
            "a rep for approval."
        ),
        "best_for": [
            "high-intent inbound",
            "contact-sales forms",
            "trust-center or compliance leads",
            "rep-approved outbound drafts",
        ],
        "prompt": (
            "Research this inbound lead, decide whether we should act, draft the "
            "next best outreach, and ask for rep approval before sending or CRM "
            "writeback. Show sources, reasons not to act, and missing context."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 8,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "lead/account summary",
            "reasons to act",
            "reasons not to act",
            "source-backed draft",
            "approval question",
            "writeback fields after approval",
        ],
        "human_approval_required_for": [
            "sending outreach",
            "sequence enrollment",
            "CRM writeback",
        ],
    },
    "account_digest": {
        "title": "Weekly account intelligence digest",
        "speaker_pattern": "LangChain / Vishnu Suresh",
        "why": (
            "Reps with 80+ accounts need a ranked Monday digest, not another tab. "
            "The agent should combine CRM, product usage, web events, and meeting "
            "signals into the top actions for the week."
        ),
        "best_for": [
            "territory prioritization",
            "post-sales meeting prep",
            "renewal risk review",
            "account owner Q&A",
        ],
        "prompt": (
            "Create a weekly account digest for this territory. Rank accounts by "
            "what changed, source every signal, and return the top 3 actions. "
            "Do not write back without approval."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 12,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "ranked accounts",
            "new signals",
            "product/customer context",
            "top 3 recommended actions",
            "missing data",
        ],
        "human_approval_required_for": [
            "task creation",
            "owner reassignment",
            "CRM field updates",
        ],
    },
    "self_serve_support_agent": {
        "title": "Self-serve support and onboarding agent",
        "speaker_pattern": "AssemblyAI / Matt Lawler",
        "why": (
            "Support/onboarding agents need current markdown docs, fast retrieval, "
            "visible progress, escalation rules, and a feedback loop into docs and "
            "product experience."
        ),
        "best_for": [
            "API signup onboarding",
            "docs Q&A",
            "pricing triage",
            "support deflection",
        ],
        "prompt": (
            "Answer this onboarding/support question using current docs and known "
            "policy context. Stream progress, cite the source, and escalate if the "
            "answer touches legal, pricing exceptions, or live pairing."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 6,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "direct answer",
            "source docs",
            "code/config example when useful",
            "escalation decision",
            "self-serve gap to improve",
        ],
        "human_approval_required_for": [
            "pricing exceptions",
            "legal terms",
            "account-specific commitments",
        ],
    },
    "web_context_research": {
        "title": "Agent-native web context research",
        "speaker_pattern": "Exa / Scott Langille",
        "why": (
            "Search should return workflow-ready claims, not a pile of links. The "
            "agent needs extracted facts, source URLs, freshness, confidence, and "
            "a recommended next action."
        ),
        "best_for": [
            "account research",
            "market mapping",
            "entity verification",
            "web-native prospecting",
        ],
        "prompt": (
            "Research this account from web sources. Return source-backed claims, "
            "freshness, relevance to GTM, confidence, missing context, and the next "
            "safe workflow. Do not enrich contacts or write to CRM."
        ),
        "suggested_tool_bounds": {
            "enabledToolIds": ["deeplineagent", "firecrawl_search", "exa_search"],
            "maxToolCalls": 6,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "source-backed claims",
            "source URLs",
            "freshness",
            "GTM relevance",
            "confidence",
            "next workflow",
        ],
        "human_approval_required_for": [
            "enrichment",
            "CRM writeback",
            "outreach",
        ],
    },
    "bounded_tool_action": {
        "title": "Scoped tool/action workflow",
        "speaker_pattern": "Composio / Sujay Choubey",
        "why": (
            "The useful part of tool access is not the number of integrations. It "
            "is discovery, auth, scopes, execution boundaries, audit trails, and "
            "revocation."
        ),
        "best_for": [
            "agent tool selection",
            "CRM/Gmail/Slack action flows",
            "permission-sensitive workflows",
            "MCP-style action surfaces",
        ],
        "prompt": (
            "Before using any tool, state the tool, why it is needed, whether it "
            "creates a side effect, and whether approval is required. Use the "
            "minimum tool set and return an audit trail."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 5,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "selected tool",
            "reason for tool choice",
            "auth/scope assumption",
            "side-effect risk",
            "audit trail",
            "next safe step",
        ],
        "human_approval_required_for": [
            "external sends",
            "record creation",
            "record mutation",
            "sequence enrollment",
        ],
    },
    "closed_loop_gtm_workflow": {
        "title": "Closed-loop GTM workflow",
        "speaker_pattern": "Deepline / Jai Toor",
        "why": (
            "The useful loop is context, action, insight. Combine first-party and "
            "third-party context, take an approved action, then store what happened "
            "so the next run improves."
        ),
        "best_for": [
            "lead magnet personalization",
            "event follow-up",
            "provider waterfall testing",
            "Claude Code / Slack GTM workflows",
        ],
        "prompt": (
            "Combine first-party and third-party context, recommend the next GTM "
            "action, ask for approval, and after approval write back the result and "
            "the learning signal. Report provider misses and marginal cost signals."
        ),
        "suggested_tool_bounds": {
            "maxToolCalls": 10,
            "side_effects_require_approval": True,
        },
        "expected_output": [
            "first-party context",
            "third-party context",
            "recommended action",
            "approval question",
            "writeback result",
            "learning signal",
            "provider/cost notes",
        ],
        "human_approval_required_for": [
            "spend escalation",
            "CRM writeback",
            "outreach send",
        ],
    },
}


def list_workflow_presets() -> list[dict[str, Any]]:
    """Return compact preset metadata for discovery UIs."""
    return [
        {
            "id": preset_id,
            "title": preset["title"],
            "speaker_pattern": preset["speaker_pattern"],
            "best_for": preset["best_for"],
        }
        for preset_id, preset in WORKFLOW_PRESETS.items()
    ]


def get_workflow_preset(preset_id: str) -> dict[str, Any] | None:
    """Return one workflow preset with its id included."""
    preset = WORKFLOW_PRESETS.get(preset_id)
    if not preset:
        return None
    return {"id": preset_id, **preset}
