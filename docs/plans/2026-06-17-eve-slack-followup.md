# Eve Slack Follow-Up

The additive Eve port intentionally leaves Slack on the existing Python broker for the first working release. That keeps the faster Vercel deployment path focused on Eve web sessions while preserving the current Slack behavior.

## Goal

Add an Eve Slack channel after the Eve web path is verified with production model credentials and Deepline API credentials.

## Scope

- map the existing Python Slack event flow to Eve's Slack channel primitives
- preserve Slack signing/token requirements and thread history behavior
- reuse the Eve Deepline tools, guidance, and workflow presets added in `eve_agent/`
- add Slack-specific evals for DM, mention, thread continuation, and failure handling
- document migration steps from the Python Slack broker to Eve Slack

## Non-Goals

- replacing the Python broker before the Eve web path is fully verified
- changing Deepline v2 execution contracts
- removing the existing Railway Slack setup

## Acceptance Criteria

- Eve Slack can respond to DMs and mentions with the same Deepline GTM guidance as the Python broker
- Slack thread context is preserved across turns
- Slack auth/signing failures fail closed
- the Python Slack path remains documented until an explicit migration decision is made
