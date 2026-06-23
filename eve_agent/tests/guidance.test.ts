import assert from "node:assert/strict";
import test from "node:test";
import { buildGuidedPrompt } from "../agent/lib/guidance.js";

test("bulk prospect lists get native v2 list and approval guidance", () => {
  const prompt = buildGuidedPrompt("Build a CSV prospect list of 20 VP Engineering contacts.");
  assert.match(prompt, /^Bulk prospect\/list requests/);
  assert.match(prompt, /native v2 list-building workflow/);
  assert.match(prompt, /pilot\/sample first/);
  assert.match(prompt, /Production GTM agent requests must use this operating loop/);
});

test("production GTM agent requests get source verify approve writeback loop", () => {
  const prompt = buildGuidedPrompt("Build a GTM agent that researches accounts and writes back to Salesforce.");
  assert.match(prompt, /^Production GTM agent requests must use this operating loop/);
  assert.match(prompt, /Approval gate/);
  assert.match(prompt, /Write back/);
  assert.match(prompt, /Composio: tool use needs auth/);
});

test("Snowflake requests get read-only SQL guidance", () => {
  const prompt = buildGuidedPrompt("Use Snowflake to query product usage for churn risk.");
  assert.match(prompt, /^Snowflake\/warehouse query requests must use this read-only operating loop/);
  assert.match(prompt, /Use read-only SELECT queries only/);
  assert.match(prompt, /Never run INSERT/);
  assert.match(prompt, /approval before CRM writeback/);
});

test("plain one-off requests pass through unchanged", () => {
  assert.equal(
    buildGuidedPrompt("Find the LinkedIn URL for Jensen Huang at NVIDIA."),
    "Find the LinkedIn URL for Jensen Huang at NVIDIA.",
  );
});
