export const DEFAULT_DEEPLINE_BASE_URL = "https://code.deepline.com";
export const V2_EXECUTE_RESPONSE_CONTRACT = "v2-tool-response";

export interface DeeplineClientOptions {
  apiKey?: string;
  baseUrl?: string;
  fetcher?: typeof fetch;
}

export interface DeeplineToolCall {
  toolName: string;
  payloadKeys: string[];
}

export interface DeeplineStreamResult {
  reply: string;
  toolCalls: DeeplineToolCall[];
}

export class DeeplineClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;

  constructor(options: DeeplineClientOptions = {}) {
    const apiKey = options.apiKey ?? process.env.DEEPLINE_API_KEY ?? "";
    if (!apiKey) {
      throw new Error("DEEPLINE_API_KEY is required.");
    }
    this.apiKey = apiKey;
    this.baseUrl = (
      options.baseUrl ??
      process.env.DEEPLINE_HOST_URL ??
      process.env.DEEPLINE_API_BASE_URL ??
      DEFAULT_DEEPLINE_BASE_URL
    ).replace(/\/+$/, "");
    this.fetcher = options.fetcher ?? fetch;
  }

  private headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
      "x-deepline-execute-response-contract": V2_EXECUTE_RESPONSE_CONTRACT,
    };
  }

  async executeTool(toolId: string, payload: Record<string, unknown> = {}) {
    const response = await this.fetcher(
      `${this.baseUrl}/api/v2/integrations/${encodeURIComponent(toolId)}/execute`,
      {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ payload }),
      },
    );
    await assertOk(response, `Deepline tool ${toolId} failed`);
    return await response.json();
  }

  async *streamAgent(payload: Record<string, unknown>): AsyncGenerator<string> {
    const response = await this.fetcher(`${this.baseUrl}/api/v2/integrations/deeplineagent/stream`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(payload),
    });
    await assertOk(response, "Deepline native agent stream failed");
    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      yield decoder.decode(value, { stream: true });
    }
  }
}

async function assertOk(response: Response, prefix: string) {
  if (response.ok) return;
  const body = await response.text().catch(() => "");
  throw new Error(`${prefix}: HTTP ${response.status} ${body.slice(0, 500)}`);
}

export function extractTextFromSseChunk(chunk: string): string {
  let text = "";
  for (const rawLine of chunk.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line.startsWith("data:")) continue;
    const data = line.slice("data:".length).trim();
    if (!data || data === "[DONE]") continue;
    let event: unknown;
    try {
      event = JSON.parse(data);
    } catch {
      continue;
    }
    if (!event || typeof event !== "object") continue;
    const obj = event as Record<string, unknown>;
    for (const key of ["text", "textDelta", "delta"]) {
      if (typeof obj[key] === "string") {
        text += obj[key];
        break;
      }
    }
    const part = obj.part;
    if (part && typeof part === "object") {
      const partObj = part as Record<string, unknown>;
      if (typeof partObj.text === "string") text += partObj.text;
      else if (typeof partObj.textDelta === "string") text += partObj.textDelta;
    }
  }
  return text;
}

export async function streamToTextAndToolCalls(chunks: AsyncIterable<string>): Promise<DeeplineStreamResult> {
  let reply = "";
  const toolCalls: DeeplineToolCall[] = [];
  for await (const chunk of chunks) {
    reply += extractTextFromSseChunk(chunk);
    toolCalls.push(...extractToolCallsFromSseChunk(chunk));
  }
  return { reply: reply.trim(), toolCalls };
}

function extractToolCallsFromSseChunk(chunk: string): DeeplineToolCall[] {
  const calls: DeeplineToolCall[] = [];
  for (const rawLine of chunk.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line.startsWith("data:")) continue;
    const data = line.slice("data:".length).trim();
    if (!data || data === "[DONE]") continue;
    let event: unknown;
    try {
      event = JSON.parse(data);
    } catch {
      continue;
    }
    if (!event || typeof event !== "object") continue;
    const obj = event as Record<string, unknown>;
    if (obj.type !== "tool-call" && obj.type !== "tool_call") continue;
    const toolName = obj.toolName ?? obj.tool_name ?? obj.name;
    if (typeof toolName !== "string" || !toolName) continue;
    const input = obj.input && typeof obj.input === "object" ? (obj.input as Record<string, unknown>) : {};
    calls.push({ toolName, payloadKeys: Object.keys(input) });
  }
  return calls;
}
