"""
End-to-end example: LinkedIn URL in → enriched contact + email verification out.

Run with:
    ANTHROPIC_API_KEY=... python example.py
"""

from deepline_gtm_agent import create_gtm_agent

# Create the agent — defaults to Claude Opus 4.6
agent = create_gtm_agent()

# ── Example 1: Enrich a single contact by LinkedIn URL ──────────────────────
print("=" * 60)
print("Example 1: Enrich contact from LinkedIn URL")
print("=" * 60)

result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": (
            "Enrich this contact and verify their email before reporting it: "
            "https://www.linkedin.com/in/reidhoffman/"
        ),
    }]
})

print(result["messages"][-1].content)


# ── Example 2: Find prospects matching an ICP ────────────────────────────────
print("\n" + "=" * 60)
print("Example 2: Find VP of Sales prospects in SaaS, 200-500 employees")
print("=" * 60)

result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": (
            "Find 5 VP of Sales at B2B SaaS companies with 200-500 employees "
            "based in the United States. Return name, title, company, and LinkedIn URL."
        ),
    }]
})

print(result["messages"][-1].content)


# ── Example 3: Research a target account ────────────────────────────────────
print("\n" + "=" * 60)
print("Example 3: Account research")
print("=" * 60)

result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": (
            "Research Rippling (rippling.com). I want to know their headcount, "
            "funding stage, tech stack, and why they might be a good fit for "
            "a sales intelligence tool."
        ),
    }]
})

print(result["messages"][-1].content)
