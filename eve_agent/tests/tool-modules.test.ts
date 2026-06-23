import assert from "node:assert/strict";
import test from "node:test";

test("Eve tool modules can be imported", async () => {
  const modules = await Promise.all([
    import("../agent/tools/deepline_chat.js"),
    import("../agent/tools/deepline_execute_tool.js"),
    import("../agent/tools/list_workflow_presets.js"),
    import("../agent/tools/get_workflow_preset.js"),
  ]);
  for (const mod of modules) {
    assert.equal(typeof mod.default, "object");
  }
});
