import assert from "node:assert/strict";
import test from "node:test";
import {
  DeeplineClient,
  extractTextFromSseChunk,
  streamToTextAndToolCalls,
} from "../agent/lib/deepline.js";

test("executeTool uses Deepline v2 tool route", async () => {
  const requests: Array<{ url: string; init: RequestInit }> = [];
  const fetcher: typeof fetch = async (input, init) => {
    const url = input instanceof Request ? input.url : String(input);
    requests.push({ url, init: init ?? {} });
    return new Response(
      JSON.stringify({ status: "completed", toolResponse: { raw: { email: "jane@acme.com" } } }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  };

  const client = new DeeplineClient({
    apiKey: "dl_test",
    baseUrl: "https://code.deepline.com",
    fetcher,
  });

  const result = await client.executeTool("hunter_email_finder", { domain: "acme.com" });

  assert.equal(requests[0].url, "https://code.deepline.com/api/v2/integrations/hunter_email_finder/execute");
  assert.equal((requests[0].init.headers as Record<string, string>).Authorization, "Bearer dl_test");
  assert.equal(
    (requests[0].init.headers as Record<string, string>)["x-deepline-execute-response-contract"],
    "v2-tool-response",
  );
  assert.equal((result as any).toolResponse.raw.email, "jane@acme.com");
});

test("extractTextFromSseChunk parses common Deepline stream events", () => {
  const chunk = [
    'data: {"type":"text-delta","textDelta":"hello"}',
    'data: {"type":"text-delta","delta":" world"}',
    "data: [DONE]",
    "",
  ].join("\n");

  assert.equal(extractTextFromSseChunk(chunk), "hello world");
});

test("streamToTextAndToolCalls captures text and tool-call metadata", async () => {
  async function* chunks() {
    yield 'data: {"type":"tool-call","toolName":"exa_search","input":{"query":"stripe"}}\n\n';
    yield 'data: {"type":"text-delta","textDelta":"done"}\n\n';
  }

  const result = await streamToTextAndToolCalls(chunks());

  assert.equal(result.reply, "done");
  assert.deepEqual(result.toolCalls, [{ toolName: "exa_search", payloadKeys: ["query"] }]);
});
