"""
Deepline ICP, personas, and messaging context.

Injected into the agent's system prompt so it can immediately answer
"why is this person/company a good fit for Deepline?" on any enrichment or
prospect search result.
"""

DEEPLINE_ICP_CONTEXT = """
*Deepline ICP & Fit Scoring*

Deepline is a unified GTM data API that replaces tool sprawl (Apollo, Clay, ZoomInfo, Clearbit, etc.)
with a single API routing across 30+ enrichment providers, plus AI-native workflow automation.

*Ideal customer profile:*
• B2B SaaS, 50–1000 employees, Series A–D
• Sales-led or PLG, $1M–$50M ARR
• Running outbound or building a GTM data pipeline
• Pain: too many data tools, inconsistent enrichment, engineers wasting time on data plumbing

*High-fit personas (direct buyers):*
• CRO / VP Sales / Head of Sales — owns outbound motion, feels the data quality pain
• RevOps / GTM Ops Lead — owns the stack, evaluates vendors, builds enrichment flows
• GTM Engineer / Growth Engineer — builds the tooling, wants a clean API, sick of stitching together Apollo + Hunter + Clay
• Head of Growth / VP Marketing — runs PLG motions, needs enrichment at activation/conversion

*Medium-fit (influencer / champion):*
• Account Executive, Enterprise — high-volume outbound user, feels bad data daily
• SDR Manager / BDR Lead — manages a team suffering from stale/incomplete data
• Founder/CTO at early-stage startup — building their first GTM stack

*Low-fit:*
• Consumer companies, non-SaaS, or companies with no outbound motion
• Enterprises with locked-in ZoomInfo contracts and no buying motion

*Competitor signals (high-intent trigger):*
• Uses Apollo, Clay, Clearbit, ZoomInfo, Lusha, Outreach, Salesloft — all integration + displacement opportunities
• Recently hired a RevOps or GTM Eng — likely evaluating new tooling
• Series A/B funding announcement — building out GTM team and tooling

*Messaging angles:*
• "One API, 30+ providers — stop paying for 6 tools to get 1 email"
• "Engineers: stop stitching together Apollo + Hunter. One call, best-of-breed waterfall."
• "RevOps: consolidate your enrichment stack and get better coverage for less"
• "Stripe/Brex/Rippling-style fintech + AI companies are Deepline's fastest-growing segment"

*When enriching or researching a contact*, always end the profile with:

*Deepline fit:* [1–2 sentences: why this person/company is or isn't a strong fit, using the above framework]
"""
