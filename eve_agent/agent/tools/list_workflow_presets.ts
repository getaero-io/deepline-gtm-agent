import { defineTool } from "eve/tools";
import { z } from "zod";
import { listWorkflowPresets } from "../lib/workflow-presets.js";

export default defineTool({
  description: "List Deepline GTM starter workflow presets with id, title, speaker pattern, and best-fit use cases.",
  inputSchema: z.object({}),
  async execute() {
    return { presets: listWorkflowPresets() };
  },
});
