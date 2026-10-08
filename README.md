# CareBridge LiteLLM Gateway

CareBridge's server-only model gateway. It presents a single OpenAI-compatible API to the CareBridge backend while keeping provider credentials, provider model names, and failover policy out of the clinic application.

## Related projects and documentation

- [CareBridge clinic application](https://github.com/shahriar-rashid-13/carebridge-clinic-flow) · [deployed application](https://carebridge-clinic-flow.vercel.app/)
- [CareBridge RAG, search evaluation, and no-show model](https://github.com/shahriar-rashid-13/carebridge-rag)
- [Gateway deployment](https://carebridge-lite-llm.vercel.app/) (server-to-server; a master key is required)
- [Assessment 2 report](https://github.com/shahriar-rashid-13/carebridge-clinic-flow/blob/main/docs/assessment-2/ASSESSMENT_2_REPORT.md)
- [Assessment 3 report](https://github.com/shahriar-rashid-13/carebridge-clinic-flow/blob/main/docs/assessment-3/ASSESSMENT_3_REPORT.md)
- [Complete project report](https://github.com/shahriar-rashid-13/carebridge-clinic-flow/blob/main/docs/FINAL_PROJECT_REPORT.md)
- [Project overview](https://github.com/shahriar-rashid-13/carebridge-clinic-flow/blob/main/docs/PROJECT_OVERVIEW.md)

## Responsibility boundary

This service is deliberately narrow. It owns:

- stable CareBridge model aliases;
- provider API credentials;
- OpenAI-compatible chat and embedding endpoints;
- provider selection, timeouts, and fallback order;
- master-key authentication at the gateway.

It does **not** authenticate clinic users, authorize roles, connect to Supabase, execute SQL or tools, enforce clinic business rules, or accept browser traffic. Those responsibilities remain in the CareBridge Supabase Edge Functions. The browser calls an authenticated Edge Function with the user's JWT; the Edge Function calls this gateway with a separate server secret.

```text
Browser
  │ user JWT
  ▼
CareBridge Supabase Edge Function
  ├─ carebridge-ai-v2: Assessment 2 single-agent baseline
  └─ carebridge-ai-v3: Assessment 3 supervisor and specialist agents
       │ LITELLM_API_KEY
       ▼
This LiteLLM gateway
  ├─ Gemini chat and embeddings
  └─ OpenRouter chat fallbacks

carebridge-rag scripts ── LITELLM_MASTER_KEY ──► gateway
  ├─ corpus embedding and Assessment 2 RAG evaluation
  ├─ classification
  └─ Assessment 3 answer, reranking, and judge evaluation
```

Both v2 and v3 use the gateway client implemented in `carebridge-ai-v2/gateway.ts`. They call `carebridge-agent` for chat and tool calling. After a non-Gemini fallback answers a tool-call round, the caller uses `carebridge-agent-fallback` for the remaining rounds so Gemini is not given tool history without Gemini thought signatures. v2 also uses `carebridge-embed` for its Gemini-based knowledge search. v3 uses its own gte-small query embeddings, but still uses this gateway for supervision, specialist calls, and model reranking.

## Models and routing

`litellm_config.yaml` is the source of truth. Each provider deployment has a separate model group so LiteLLM follows an explicit fallback chain instead of load-balancing across keys.

| Model group | Provider model | Key | Timeout | Purpose |
| --- | --- | --- | ---: | --- |
| `carebridge-agent` | `gemini/gemini-3.1-flash-lite` | `GEMINI_API_KEY` | 12 s | Primary application chat and tool calling |
| `carebridge-agent-retry` | `gemini/gemini-3.1-flash-lite` | `SECOND_GEMINI_API_KEY` | 12 s | Same-model retry on a second quota |
| `carebridge-agent-fallback` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `OPENROUTER_API_KEY` | 12 s | First non-Gemini chat fallback |
| `carebridge-agent-fallback-2` | `openrouter/qwen/qwen3.8-27b:free` | `OPENROUTER_API_KEY_2` | 12 s | Final chat fallback; reasoning is disabled to fit the timeout |
| `carebridge-embed` | `gemini/gemini-embedding-001` | `GEMINI_API_KEY` | 20 s | Primary 768-dimensional corpus and query embeddings |
| `carebridge-embed-2` | `gemini/gemini-embedding-001` | `SECOND_GEMINI_API_KEY` | 20 s | Compatible embedding fallback |
| `carebridge-judge` | `gemini/gemini-3.5-flash` | `SECOND_GEMINI_API_KEY` | 30 s | Evaluation judge; not an application model |
| `carebridge-judge-2` | `gemini/gemini-3.5-flash` | `GEMINI_API_KEY` | 30 s | Judge fallback |

The configured fallback routes are:

```text
carebridge-agent
  → carebridge-agent-retry
  → carebridge-agent-fallback
  → carebridge-agent-fallback-2

carebridge-agent-fallback → carebridge-agent-fallback-2
carebridge-embed          → carebridge-embed-2
carebridge-judge          → carebridge-judge-2
```

`router_settings.num_retries` is `0`; failover comes from these routes, not an additional retry loop. A fully exhausted chat chain can consume up to 48 seconds of configured provider timeout, embeddings up to 40 seconds, and judge calls up to 60 seconds, excluding routing and network overhead. The v2 and v3 agent callers allow at most 55 seconds for one gateway call; v3's supervisor and reranker use shorter 25-second and 6-second caller deadlines.

Use Gemini keys from separate Google projects if the goal is independent project-level quota. The cross-key test verifies that the currently pinned LiteLLM release preserves Gemini thought signatures across a two-key tool round.

## API

LiteLLM supplies the API; `app.py` adds no custom routes or middleware. CareBridge currently uses the unprefixed routes below. LiteLLM also exposes their `/v1` equivalents for OpenAI SDK compatibility.

| Method | Route | CareBridge use |
| --- | --- | --- |
| `POST` | `/chat/completions` or `/v1/chat/completions` | Chat, tools, classification, reranking, and evaluation |
| `POST` | `/embeddings` or `/v1/embeddings` | Gemini embeddings |
| `GET` | `/models` or `/v1/models` | Authenticated model discovery |

Authenticate every request with:

```http
Authorization: Bearer <LITELLM_MASTER_KEY>
Content-Type: application/json
```

Chat example:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"carebridge-agent","messages":[{"role":"user","content":"Hello"}]}'
```

Embedding example:

```bash
curl http://localhost:4000/v1/embeddings \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"carebridge-embed","input":"clinic opening hours"}'
```

LiteLLM adds routing metadata to model responses. CareBridge reads:

- `x-litellm-model-group` to identify the group that served the response;
- `x-litellm-attempted-fallbacks` as a compatibility fallback when the served group is unavailable.

The Edge Function treats `carebridge-agent` and `carebridge-agent-retry` as Gemini groups. Any other served chat group is recorded as a non-Gemini fallback.

## Local development

Python 3.12 matches CI. From this repository:

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, allow it for the current process only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### macOS or Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`, then start the proxy:

```bash
litellm --config litellm_config.yaml --port 4000
```

The local URL is `http://localhost:4000`. The CLI receives the config path explicitly. `app.py`, used by an ASGI deployment, loads `.env` and exports LiteLLM's `app`.

The dependency list pins LiteLLM to `1.103.0` and installs the proxy extras explicitly instead of using `litellm[proxy]`; the comments in `requirements.txt` document this as a Vercel bundle-size decision.

## Environment variables

Gateway runtime variables:

| Variable | Required | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | Yes | Primary Gemini chat and embedding key |
| `SECOND_GEMINI_API_KEY` | Yes | Second Gemini key for chat, embedding, and judge failover |
| `OPENROUTER_API_KEY` | Yes | Nvidia fallback key |
| `OPENROUTER_API_KEY_2` | Yes | Qwen fallback key |
| `LITELLM_MASTER_KEY` | Yes | Client-facing gateway secret; create this value yourself |
| `CONFIG_FILE_PATH` | ASGI deployment | Path from which LiteLLM loads `litellm_config.yaml`; see deployment notes |

Generate a master key locally:

```bash
python -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"
```

Variables belong to callers, not this gateway:

- Supabase Edge Functions use `LITELLM_BASE_URL` and `LITELLM_API_KEY`; the latter contains the same secret value as the gateway's `LITELLM_MASTER_KEY`.
- Local `carebridge-rag` scripts use `LITELLM_BASE_URL` and `LITELLM_MASTER_KEY`, alongside their Supabase variables.
- `tests/test_proxy.py` optionally uses `LITELLM_BASE_URL` and otherwise defaults to `http://localhost:4000`.

## Tests

Start the gateway before running the live checks.

```powershell
python tests\test_proxy.py
node tests\test_second_key.mjs
.\tests\test_tool_roundtrip.ps1 -Gateway http://localhost:4000
```

Test scope:

- `test_proxy.py` is an asserting smoke test for authenticated model discovery, rejection of a bad key and bad alias, and a real OpenAI-shaped chat completion.
- `test_second_key.mjs` exercises cross-key Gemini tool rounds, both embedding groups, and both judge groups. It is a diagnostic script: individual failures are printed rather than converted into a failing process exit.
- `test_tool_roundtrip.ps1` exercises a two-step tool call on the primary and direct fallback groups. It also reports failures as output rather than acting as a strict test runner.

The GitHub Actions workflow runs on pushes to `main` and on pull requests. It uses Python 3.12 to:

1. compile `app.py`;
2. parse `litellm_config.yaml`;
3. require a non-empty model list and provider model names;
4. reject key-like YAML values that do not use `os.environ/...`.

CI does **not** install the full application requirements, start LiteLLM, contact providers, run the live scripts, validate fallback behavior, or deploy Vercel.

## Vercel deployment assumptions

The repository contains an ASGI entry point but no `vercel.json`. `app.py` only loads dotenv and exports `litellm.proxy.proxy_server.app`; it does not pass a config file to LiteLLM in code. Therefore an ASGI deployment must:

1. package `app.py`, `litellm_config.yaml`, and the installed requirements;
2. route requests to the exported `app`;
3. set the five secret variables listed above;
4. set `CONFIG_FILE_PATH` to a deployment-resolvable path for `litellm_config.yaml` (for example `litellm_config.yaml` when the function working directory is the repository root);
5. allow enough execution time for the intended fallback chain and caller deadline.

Framework selection, route mapping, build commands, function duration, regions, Git integration, and automatic redeployment are Vercel project settings and are not tracked in this repository. Verify them in the Vercel project rather than treating them as repository guarantees.

Do not expose the gateway URL and master key to browser code. Store them in Supabase Edge Function secrets and in the local, ignored RAG environment file only.

## Security and operational limits

- `.env` is ignored; `.env.example` contains names and placeholders only.
- Provider keys authenticate this gateway to providers. `LITELLM_MASTER_KEY` authenticates trusted callers to this gateway. They are separate trust boundaries and must not be reused.
- Rotate any key that appears in source, logs, screenshots, browser bundles, or chat transcripts.
- Tool requests are model output only. The Edge Function validates tool names and arguments, executes authorized operations with the caller's context, and returns tool results.
- The configured provider models use free endpoints or quota-constrained keys. Availability, rate limits, model continuity, and latency are not guaranteed.
- Cold starts and routing overhead are outside the per-provider timeouts.
- Changing the embedding model or its 768 dimensions requires re-embedding every vector that will be compared with it.
- There is no persistence, response cache, rate limiter, database, or custom observability code in this repository.
- `docs/history/CAREBRIDGE_GATEWAY_CONTEXT.md` predates the current second-key and Assessment 3 configuration; use it as historical context, not current configuration.

## Repository map

```text
carebridge-liteLLM/
├── .github/workflows/ci.yml          # static config and syntax checks
├── .env.example                      # local secret-name template
├── app.py                            # minimal ASGI/Vercel entry point
├── litellm_config.yaml               # models, credentials, timeouts, fallbacks
├── requirements.txt                  # pinned LiteLLM and proxy dependencies
├── README.md
├── docs/history/
│   └── CAREBRIDGE_GATEWAY_CONTEXT.md # historical design handoff
└── tests/
    ├── test_proxy.py                 # asserting live smoke client
    ├── test_second_key.mjs           # cross-key and auxiliary-group diagnostics
    └── test_tool_roundtrip.ps1       # primary/fallback tool-round diagnostics
```
