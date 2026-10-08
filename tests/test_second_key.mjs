// Checks the second Gemini key groups on a running gateway:
// - a tool round started on one key continues on the other (thought signatures),
// - the second embedding group returns compatible vectors,
// - the judge groups answer.
// Usage: node tests/test_second_key.mjs [gateway-url]   (default http://localhost:4000)
// LITELLM_MASTER_KEY is read from the local .env file.
process.loadEnvFile(new URL("../.env", import.meta.url));
const gateway = (process.argv[2] ?? "http://localhost:4000").replace(/\/+$/, "");
const headers = { "Content-Type": "application/json", Authorization: `Bearer ${process.env.LITELLM_MASTER_KEY}` };

async function post(path, body) {
  const response = await fetch(`${gateway}${path}`, { method: "POST", headers, body: JSON.stringify(body) });
  const text = await response.text();
  if (!response.ok) throw new Error(`${response.status} ${text.slice(0, 300)}`);
  return { data: JSON.parse(text), group: response.headers.get("x-litellm-model-group") };
}

const tools = [
  {
    type: "function",
    function: { name: "get_doctors", description: "List clinic doctors", parameters: { type: "object", properties: {} } },
  },
];

async function crossKeyRound(first, second) {
  const label = `${first} then ${second}`;
  try {
    const messages = [{ role: "user", content: "Which doctors work at the clinic? Use the tool." }];
    const step1 = await post("/chat/completions", { model: first, messages, tools });
    const message = step1.data.choices[0].message;
    if (!message.tool_calls?.length) return console.log(`${label}: FAIL no tool call`);
    messages.push(message, {
      role: "tool",
      tool_call_id: message.tool_calls[0].id,
      content: '{"ok":true,"doctors":[{"name":"Dr. Rahman","specialization":"Cardiology"}]}',
    });
    const step2 = await post("/chat/completions", { model: second, messages, tools });
    console.log(`${label}: OK served by ${step1.group} then ${step2.group}`);
  } catch (err) {
    console.log(`${label}: FAIL ${err.message}`);
  }
}

await crossKeyRound("carebridge-agent", "carebridge-agent-retry");
await crossKeyRound("carebridge-agent-retry", "carebridge-agent");

for (const model of ["carebridge-embed", "carebridge-embed-2"]) {
  try {
    const { data } = await post("/embeddings", { model, input: "clinic opening hours" });
    console.log(`${model}: OK ${data.data[0].embedding.length} dimensions`);
  } catch (err) {
    console.log(`${model}: FAIL ${err.message}`);
  }
}

for (const model of ["carebridge-judge", "carebridge-judge-2"]) {
  try {
    const { data } = await post("/chat/completions", {
      model,
      messages: [{ role: "user", content: 'Reply with the JSON {"score": 5} and nothing else.' }],
    });
    console.log(`${model}: OK ${data.model}: ${data.choices[0].message.content}`);
  } catch (err) {
    console.log(`${model}: FAIL ${err.message}`);
  }
}
