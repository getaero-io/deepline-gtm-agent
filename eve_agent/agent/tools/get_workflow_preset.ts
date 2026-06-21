import { defineTool } from "eve/tools";
import { z } from "zod";
import { getWorkflowPreset } from "../lib/workflow-presets.js";

export default defineTool({
  description: "Get one Deepline GTM workflow preset by id, including prompt, tool bounds, expected output, and approval requirements.",
  inputSchema: z.object({ presetId: z.string().min(1) }),
  async execute({ presetId }) {
    const preset = getWorkflowPreset(presetId);
    if (!preset) return { error: "Unknown workflow preset", presetId };
    return preset;
  },
});
