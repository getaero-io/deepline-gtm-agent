import { defineTool } from "eve/tools";
import { z } from "zod";
import { DeeplineClient, streamToTextAndToolCalls } from "../lib/deepline.js";
import { buildGuidedPrompt } from "../lib/guidance.js";

export default defineTool({
  description: "Send a GTM request to Deepline native v2 agent/chat and return the final response plus tool-call metadata.",
  inputSchema: z.object({
    message: z.string().min(1),
    messages: z.array(z.object({ role: z.string(), content: z.string() })).optional(),
    enabledToolIds: z.array(z.string()).optional(),
    maxToolCalls: z.number().int().positive().optional(),
    model: z.string().optional(),
  }),
  outputSchema: z.object({
    reply: z.string(),
    toolCalls: z.array(z.object({ toolName: z.string(), payloadKeys: z.array(z.string()) })),
  }),
  async execute(input) {
    const prompt = buildGuidedPrompt(input.message);
    const payload: Record<string, unknown> = {
      prompt,
      messages: input.messages && prompt === input.message
        ? input.messages
        : [{ role: "user", content: prompt }],
      response_mode: "stream",
    };
    if (input.enabledToolIds) payload.enabledToolIds = input.enabledToolIds;
    if (input.maxToolCalls) payload.maxToolCalls = input.maxToolCalls;
    if (input.model) payload.model = input.model;

    return await streamToTextAndToolCalls(new DeeplineClient().streamAgent(payload));
  },
  toModelOutput(output) {
    return {
      type: "text",
      value: output.reply || "Deepline returned no final text. Check tool-call metadata or retry with more context.",
    };
  },
});
