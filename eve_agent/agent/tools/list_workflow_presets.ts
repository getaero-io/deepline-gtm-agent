import { defineTool } from "eve/tools";
import { z } from "zod";
import { listWorkflowPresets } from "../lib/workflow-presets.js";

export default defineTool({
  description: "List Deepline GTM starter workflow presets. When presenting results to the user, preserve every exact preset id next to its title so follow-up requests can reference copyable ids.",
  inputSchema: z.object({}),
  async execute() {
    return { presets: listWorkflowPresets() };
  },
});
