# Example Prompts — Deepline GTM Agent

These are copy-paste ready prompts for the most common GTM workflows.
Each maps to a workflow from the LangChain GTM agent blog post, built on Deepline instead.

---

## Workflow 1 — Inbound Lead Processing

Trigger: new signup, form fill, or CRM entry. Agent researches and drafts outreach.

```
New inbound lead just came in:
- Name: Sarah Chen
- Company: Figma
- Title: Head of Revenue Operations
- Email: sarah.chen@figma.com

Research this person and their company. Then draft a short (3-sentence) personalized
first email from our VP of Sales. Focus on what's relevant to her role specifically,
not generic copy. Include your confidence level and which sources you pulled from.
```

```
I have a list of new leads from last week's webinar. Start with the first one:
Marcus Williams, Director of Sales Ops at HubSpot (mwilliams@hubspot.com).

1. Verify the email
2. Research his background and what HubSpot is working on
3. Draft a 2-sentence personalized opener based on something specific to him or HubSpot right now
```

---

## Workflow 2 — Prospect Discovery + Enrichment

Trigger: SDR needs a list of target contacts for a new campaign.

```
Find 10 VP of Sales or Director of Sales at B2B SaaS companies:
- 100–500 employees
- Based in the US
- Not in the CRM already

For each one: full name, title, company, LinkedIn URL, and work email if available.
Tell me which ones have verified emails vs. which ones need more enrichment.
```

```
I'm targeting CFOs at fintech companies that recently raised Series B or C.
Find 5 of them, verify their emails, and for each one write one personalized sentence
I could use as an email opener (based on their company or role specifically).
```

```
Find the Head of Engineering or CTO at these companies:
- Rippling (rippling.com)
- Notion (notion.so)
- Linear (linear.app)

For each: LinkedIn URL, email (verified), and one signal about what they're working on
that I could reference in outreach.
```

---

## Workflow 3 — Account Intelligence

Trigger: account review, QBR prep, renewal, or expansion motion.

```
Give me a quick account intelligence brief on Stripe (stripe.com):
- Current headcount and recent growth trend
- Key technologies in their stack
- What they're hiring for right now (signals for expansion or pain points)
- One paragraph on why a sales intelligence tool might matter to them specifically
```

```
I'm going into a call with Intercom tomorrow. Pull together:
1. Headcount (current + trend)
2. Tech stack highlights
3. Recent funding/news if available
4. 2–3 talking points tailored to their Head of Revenue profile
```

---

## Workflow 4 — Competitive Signal Monitoring

```
Research these 3 companies and tell me which one looks like the hottest prospect
right now based on hiring signals, growth, and tech stack:
- monday.com
- Asana
- ClickUp

Score them 1–10 on ICP fit and explain your reasoning.
```

---

## Workflow 5 — Email Personalization at Scale

```
I have 5 contacts to personalize outreach for. For each one, write a 1-sentence
personalized opener I can drop into a cold email template. Base it on something
specific (their role, their company's recent activity, or their LinkedIn).

1. Jenny Park, VP Sales at Rippling
2. Tom Nguyen, Head of RevOps at Notion
3. Alex Moore, Director of Sales at Linear
4. Rachel Kim, CTO at Retool
5. David Chen, VP Engineering at Figma

For each opener, note what signal you used and which data source it came from.
```

---

## Workflow 6 — Email Verification Before Send

```
Verify these emails and tell me which are safe to include in an outbound sequence:
- jsmith@salesforce.com
- m.johnson@hubspot.com
- alex@startupco.io
- ceo@bigcorp.com

For any that fail: tell me why (bounced, role-based, disposable, etc.) and
whether it's worth trying to find an alternative.
```

---

## Tips

- **Be specific about company size, location, and title** — the more specific, the better Apollo's filters work
- **Ask for sources** — the agent always includes a Sources & Confidence section; ask it to expand on any data point
- **Chain workflows** — "find 5 prospects, then verify their emails, then draft openers" all in one prompt
- **Ask about confidence** — if a result looks off, ask "how confident are you in this email?" and it'll explain
