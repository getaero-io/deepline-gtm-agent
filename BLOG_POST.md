# Building a Production GTM Agent: What We Learned

We built a GTM agent that connects to Deepline's sales and marketing integrations through the v2 native agent/chat and API layer. The main lesson: the agent layer should be boring and API-native; most product complexity lives in chat delivery, formatting, permissions, and operational guardrails.

## Architecture

The production shape is:

1. A thin FastAPI broker for Slack, REST, and web chat.
2. Deepline v2 native agent/chat for GTM reasoning and tool routing.
3. Deepline v2 SDK/API calls for enrichment, research, CRM, outreach, and provider workflows.

This avoids managed-session bootstrapping. API keys live in environment variables or the deployment secret store, and the production boundary stays at the v2 API.

## What Worked Well

### Deepline-native tool routing

The best GTM workflows were provider-aware: start with low-cost or high-confidence providers, fall back only when needed, and always return sources. Deepline's v2 catalog made that easier to centralize behind API calls instead of duplicating tool definitions across chat surfaces.

### Skill docs as operating context

Provider playbooks and workflow recipes were still valuable. They helped keep prompts grounded in exact provider capabilities, common parameter shapes, and known failure modes.

### Thin chat broker

Keeping Slack, REST, and web chat as adapters made the system easier to deploy. The broker should authenticate requests, preserve conversation context, stream responses, and hand the GTM work to Deepline.

## What Did Not Work

### Chat formatting was harder than agent reasoning

Slack markdown, streaming chunks, retries, duplicate events, and long-running status updates produced more bugs than the GTM workflows themselves. Tables, headers, and partial updates all need explicit formatting rules.

### Unstructured output is fragile

Free-form markdown is fine for human summaries, but enrichment data should be structured. Emails, phone numbers, LinkedIn URLs, provider names, and confidence values should be returned as fields before being rendered for chat.

### Long-running work needs guardrails

Batch enrichment should run a pilot first, show estimated cost and provider behavior, and require approval before the full job. Users need visibility into progress and credit usage.

## What We Would Do Differently

### Use the v2 agent/chat API as the default

New deployments should call Deepline's native agent/chat or SDK/API directly. Shelling out to a CLI can be useful for local debugging, but it should not be the production integration boundary.

### Separate data from presentation

The agent should return structured data plus a concise summary. Slack, REST, and web chat can then render the same result appropriately for each surface.

### Track cost per request

Deepline operations consume credits. Production agents should show estimates before large jobs, record actual usage, and enforce per-user or per-workspace limits.

## Conclusion

The agent layer was not the bottleneck. Deepline plus provider playbooks can handle complex GTM workflows when the integration is API-native and the output contract is clear.

The harder work is product infrastructure: chat delivery, structured rendering, error recovery, approval gates, and cost visibility.

---

Built with [Deepline](https://code.deepline.com).
