// AUTO-GENERATED FILE. DO NOT EDIT.
// Source: deepline-api/src/lib/onboard/recipes.json
export default {
  "skipSuffix": " This is a quickstart run (≤ 5 rows) — skip the pilot/approval gate and run directly.",
  "recipes": [
    {
      "id": "find_email",
      "title": "Waterfall Email Lookup",
      "iconName": "Mail",
      "difficulty": "easy",
      "group": "primary",
      "lines": [
        [
          {
            "type": "text",
            "value": "Find 5 "
          },
          {
            "type": "slot",
            "name": "role",
            "hint": "CTOs"
          },
          {
            "type": "text",
            "value": " in "
          },
          {
            "type": "slot",
            "name": "location",
            "hint": "NYC"
          },
          {
            "type": "text",
            "value": " and get their work emails"
          }
        ],
        [
          {
            "type": "text",
            "value": "Waterfall across providers — 90%+ hit rate, pay only for hits"
          }
        ]
      ],
      "promptTemplate": "/deepline-quickstart Find 5 {role} in {location} and get their verified work emails.",
      "noSkipSuffix": true,
      "slotDefaults": {
        "role": "CTOs",
        "location": "NYC"
      }
    },
    {
      "id": "signal_outbound",
      "title": "Signal-Based Outbound",
      "iconName": "Radar",
      "difficulty": "hard",
      "group": "primary",
      "lines": [
        [
          {
            "type": "text",
            "value": "Find 5 leads engaging with "
          },
          {
            "type": "slot",
            "name": "competitor",
            "hint": "Gong"
          },
          {
            "type": "text",
            "value": "’s competitors on LinkedIn"
          }
        ],
        [
          {
            "type": "text",
            "value": "Score against "
          },
          {
            "type": "slot",
            "name": "icp",
            "hint": "CMO or VP of Marketing"
          },
          {
            "type": "text",
            "value": ", waterfall the emails"
          }
        ],
        [
          {
            "type": "text",
            "value": "Sequence-ready list, first lines included"
          }
        ]
      ],
      "promptTemplate": "/deepline-gtm Find 5 leads engaging with {competitor}'s competitors on LinkedIn. Score against {icp}. Waterfall enrich their emails. Build a sequence-ready list with personalized first lines.",
      "slotDefaults": {
        "competitor": "Gong",
        "icp": "CMO or VP of Marketing"
      }
    },
    {
      "id": "portfolio_scrape",
      "title": "VC Portfolio Scrape",
      "iconName": "Briefcase",
      "difficulty": "hard",
      "group": "primary",
      "lines": [
        [
          {
            "type": "text",
            "value": "Pull 5 companies from "
          },
          {
            "type": "slot",
            "name": "investor",
            "hint": "Y Combinator W26"
          }
        ],
        [
          {
            "type": "text",
            "value": "Find the "
          },
          {
            "type": "slot",
            "name": "role",
            "hint": "Head of Marketing or VP Sales"
          },
          {
            "type": "text",
            "value": " at each one"
          }
        ],
        [
          {
            "type": "text",
            "value": "Waterfall their emails, write a first line"
          }
        ]
      ],
      "promptTemplate": "/deepline-gtm Pull 5 companies from {investor}. Find the {role} at each one. Waterfall their emails and write a personalized first line.",
      "slotDefaults": {
        "investor": "Y Combinator W26",
        "role": "Head of Marketing or VP Sales"
      }
    },
    {
      "id": "pre_research_source_plan",
      "title": "Pre-Research Source Plan",
      "iconName": "SearchCheck",
      "difficulty": "medium",
      "group": "primary",
      "lines": [
        [
          {
            "type": "text",
            "value": "Find the best data sources for "
          },
          {
            "type": "slot",
            "name": "research_goal",
            "hint": "PLG signup scoring"
          }
        ],
        [
          {
            "type": "text",
            "value": "Public, private, paid, and proprietary coverage"
          }
        ],
        [
          {
            "type": "text",
            "value": "No-scrape provider/key plan before execution"
          }
        ]
      ],
      "promptTemplate": "/deepline-pre-research Build a V2 SDK source plan for {research_goal}. Prefer managed external APIs and private connectors over scraping. Include public datasets, private/paid/proprietary datasets, Reddit, X/Twitter, web search, required providers/API keys, Deepline credit approval gate, and the exact `curl` call to `/api/v2/pre-research/plan` that an agent can run.",
      "noSkipSuffix": true,
      "slotDefaults": {
        "research_goal": "PLG signup scoring and activation workflow data"
      }
    },
    {
      "id": "chat",
      "title": "In your own words",
      "iconName": "MessageCircle",
      "difficulty": "hard",
      "group": "more",
      "lines": [
        [
          {
            "type": "freeform",
            "hint": "I need to build a list of ..."
          }
        ]
      ],
      "promptTemplate": "{freeform}",
      "slotDefaults": {},
      "noSkipSuffix": true
    },
    {
      "id": "competitor_intel",
      "title": "Competitor Intel",
      "iconName": "Search",
      "difficulty": "medium",
      "group": "more",
      "lines": [
        [
          {
            "type": "text",
            "value": "Who competes with "
          },
          {
            "type": "slot",
            "name": "companies",
            "hint": "Anthropic, OpenAI"
          },
          {
            "type": "text",
            "value": "?"
          }
        ],
        [
          {
            "type": "text",
            "value": "Funding, headcount, stack, positioning — one pass"
          }
        ]
      ],
      "promptTemplate": "/deepline-gtm Find 5 direct competitors for {companies}. For each: funding stage, headcount, tech stack, and positioning.",
      "slotDefaults": {
        "companies": "Anthropic, OpenAI"
      }
    },
    {
      "id": "personalized_outbound",
      "title": "Cold Outbound",
      "iconName": "Pen",
      "difficulty": "medium",
      "group": "more",
      "lines": [
        [
          {
            "type": "text",
            "value": "Research "
          },
          {
            "type": "slot",
            "name": "outbound_icp",
            "hint": "Series A AI startups in SF"
          },
          {
            "type": "text",
            "value": " for buying signals"
          }
        ],
        [
          {
            "type": "text",
            "value": "Write a first line that doesn’t read like a template"
          }
        ],
        [
          {
            "type": "text",
            "value": "Push straight to Instantly or Smartlead"
          }
        ]
      ],
      "promptTemplate": "/deepline-gtm Find 5 leads matching {outbound_icp}. Research buying signals and recent news. Write a personalized cold email first line per lead. Push to Instantly when done.",
      "slotDefaults": {
        "outbound_icp": "Series A AI startups in SF"
      }
    }
  ]
} as const;
