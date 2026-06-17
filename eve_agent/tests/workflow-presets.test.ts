import assert from "node:assert/strict";
import test from "node:test";
import { getWorkflowPreset, listWorkflowPresets } from "../agent/lib/workflow-presets.js";

test("workflow presets expose the same core preset ids as Python broker", () => {
  const ids = new Set(listWorkflowPresets().map((preset) => preset.id));
  for (const id of [
    "inbound_lead_approval",
    "account_digest",
    "self_serve_support_agent",
    "web_context_research",
    "bounded_tool_action",
    "closed_loop_gtm_workflow",
    "snowflake_query_agent",
  ]) {
    assert.equal(ids.has(id), true, `${id} should be listed`);
  }
});

test("web_context_research includes tool bounds and output shape", () => {
  const preset = getWorkflowPreset("web_context_research");
  assert.equal(preset?.speaker_pattern, "Exa / Scott Langille");
  assert.deepEqual(preset?.suggested_tool_bounds.enabledToolIds, ["deeplineagent", "firecrawl_search", "exa_search"]);
  assert.equal(preset?.suggested_tool_bounds.maxToolCalls, 6);
  assert.ok(preset?.expected_output.includes("source-backed claims"));
});

test("unknown workflow preset returns null", () => {
  assert.equal(getWorkflowPreset("nope"), null);
});
