const host = normalizeHost(getArg("--host") ?? process.env.EVE_HOST ?? "http://127.0.0.1:3000");
const message = getArg("--message") ?? "Say ok in one word.";

async function main() {
  const health = await fetch(`${host}/eve/v1/health`);
  if (!health.ok) {
    throw new Error(`Health failed: HTTP ${health.status} ${await health.text()}`);
  }

  const session = await fetch(`${host}/eve/v1/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!session.ok) {
    throw new Error(`Session create failed: HTTP ${session.status} ${await session.text()}`);
  }

  const body = (await session.json()) as { sessionId?: string };
  if (!body.sessionId) {
    throw new Error(`No sessionId in response: ${JSON.stringify(body)}`);
  }

  const stream = await fetch(`${host}/eve/v1/session/${body.sessionId}/stream`);
  if (!stream.ok) {
    throw new Error(`Stream failed: HTTP ${stream.status} ${await stream.text()}`);
  }
  if (!stream.body) {
    throw new Error("Stream response had no body.");
  }

  const reader = stream.body.getReader();
  const decoder = new TextDecoder();
  let text = "";
  let sawCompletion = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    text += decoder.decode(value, { stream: true });
    if (text.includes('"type":"session.completed"') || text.includes('"type":"session.waiting"')) {
      sawCompletion = true;
      break;
    }
  }

  if (!sawCompletion) {
    throw new Error(`No completion/waiting event seen. Stream so far:\n${text.slice(0, 2000)}`);
  }

  console.log(JSON.stringify({ ok: true, host, sessionId: body.sessionId }));
}

function getArg(name: string): string | undefined {
  const idx = process.argv.indexOf(name);
  return idx >= 0 ? process.argv[idx + 1] : undefined;
}

function normalizeHost(value: string): string {
  return value.replace(/\/+$/, "");
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
