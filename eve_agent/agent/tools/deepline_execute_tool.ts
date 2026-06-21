import { defineTool } from "eve/tools";
import { z } from "zod";
import { DeeplineClient } from "../lib/deepline.js";

export default defineTool({
  description: "Execute one specific Deepline v2 tool by tool id and payload. Use only for bounded direct operations, not loops.",
  inputSchema: z.object({
    toolId: z.string().min(1),
    payload: z.record(z.string(), z.unknown()).default({}),
  }),
  async execute({ toolId, payload }) {
    return await new DeeplineClient().executeTool(toolId, payload);
  },
});
