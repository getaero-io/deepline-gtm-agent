# Example Prompts — Deepline GTM Agent

Copy-paste ready prompts for the most common GTM workflows.
Based on the patterns from ["How we built LangChain's GTM Agent"](https://blog.langchain.com/how-we-built-langchains-gtm-agent/), rebuilt here on Deepline's provider stack.

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

```
Which of these companies is growing fastest right now?
- Rippling
- Deel
- Remote

Use headcount trends and recent funding signals. Show your sources.
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

## Workflow 7 — Build a Target Account List

```
Build me a list of 20 B2B SaaS companies:
- 50–500 employees
- Headquartered in the US or Canada
- In the HR tech or people management space

For each: name, domain, headcount, and a one-line description of what they do.
I'll use this list to find contacts next.
```

```
Find me 15 fintech companies in New York with between 100 and 1000 employees.
I want to see their names, domains, headcount, and a brief description.
Flag any that look like they're in the payments or lending space specifically.
```

---

## Workflow 8 — C-Suite Lookup (web-first)

For C-suite titles, database providers often have stale data — the agent is prompted to run a live web search first.

```
Who is the current CEO and CRO of Rippling? Find their verified work emails.
```

```
Find the VP of Product at Linear. I need their LinkedIn URL and a verified email.
I'll be reaching out for a partnership conversation.
```

```
I want to reach the Head of Partnerships at Notion. Find them, verify their email,
and give me two sentences of context about their background I can reference.
```

---

## Tips

- **Be specific about company size, location, and title** — filters work best when they're precise. "VP of Sales at B2B SaaS, 200–500 employees, US" beats "sales leader at a tech company."
- **Chain workflows in one prompt** — "find 5 prospects, verify their emails, then draft openers" all works in a single message. The agent will call tools in sequence.
- **Ask for sources** — the agent always includes a Sources & Confidence section. If a result looks off, ask "how confident are you in this email?" and it'll explain which provider returned it and why.
- **Ask about confidence levels** — `find_linkedin` returns `"high"`, `"medium"`, or `"none"`. If it's medium, ask the agent to verify by cross-referencing the full name.
- **Use `web_research` explicitly for recent signals** — if you want hiring trends, recent news, or funding rounds, say so. The agent will call `web_research` which hits live web sources via Exa.
- **Start company research before contact search** — running `search_companies` first gives you domains, which makes `search_prospects` more precise (domain-level filtering is tighter than name matching).
