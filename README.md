# CareBridge LiteLLM Gateway

Small model gateway for CareBridge AI V2. It exposes one OpenAI-compatible API and hides provider details from the CareBridge application.

- Live: https://carebridge-lite-llm.vercel.app (server-to-server only, master key required)
- Whole-system overview: `../PROJECT_OVERVIEW.md`

```text
CareBridge Frontend
        ↓
Supabase Edge Function carebridge-ai-v2
        ↓
LiteLLM (this project)
        ↓
Chat:       Gemini, then Gemini retry, then OpenRouter Nvidia, then OpenRouter Qwen
Embeddings: Gemini embedding-001 (RAG queries and corpus upload from carebridge-rag)
```

This is a separate project because authentication, roles, tool execution, business rules, and Supabase access belong in the Supabase Edge Function. LiteLLM only handles model/provider abstraction, the application model aliases, provider credentials, and fallback routing.

LiteLLM must never connect to Supabase, authenticate CareBridge users, execute tools or SQL, or receive browser traffic.

Callers:

- the Edge Function `carebridge-ai-v2`: `POST /chat/completions` with `model = "carebridge-agent"`, and `POST /embeddings` with `model = "carebridge-embed"` for `search_knowledge`;
- the `carebridge-rag` upload script: `POST /embeddings` with `model = "carebridge-embed"`.

Every response carries the header `x-litellm-model-group`. The Edge Function reads it to record whether a fallback model answered.

## Current configuration

| Model group | Provider model | Role |
| --- | --- | --- |
| `carebridge-agent` | `gemini/gemini-3.1-flash-lite` | Primary (called by the application) |
| `carebridge-agent-retry` | `gemini/gemini-3.1-flash-lite` | First fallback: one Gemini retry for short-lived 503 "high demand" errors |
| `carebridge-agent-fallback` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | Second fallback |
| `carebridge-agent-fallback-2` | `openrouter/qwen/qwen3.8-27b:free` (key `OPENROUTER_API_KEY_2`) | Last fallback |
| `carebridge-embed` | `gemini/gemini-embedding-001` (768 dimensions) | Embeddings for the RAG corpus and queries (`/embeddings`) |

`litellm_config.yaml` is the routing source of truth. It contains no credentials. Each deployment has its own model group, and `router_settings.fallbacks` sends a failed `carebridge-agent` request to `carebridge-agent-retry`, then `carebridge-agent-fallback`, then `carebridge-agent-fallback-2`. A failed direct `carebridge-agent-fallback` request goes to `carebridge-agent-fallback-2`. Do not put both deployments under one model group: LiteLLM then load-balances between them instead of treating one as a fallback.

Test a tool round-trip on both model groups with `tests/test_tool_roundtrip.ps1`. Gemini 3 tool calling needs thought signatures passed back between steps; LiteLLM 1.103.0 handles this, older pins may not.

## Windows setup

Open PowerShell in this directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If your prompt starts with `C:\...>` instead of `PS C:\...>`, you are using
Command Prompt. Use these equivalent commands there:

```bat
rmdir /s /q .venv
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

Confirm the virtual environment is active before installing:

```bat
where python
```

The first result must be
`...\carebridge-liteLLM\.venv\Scripts\python.exe`.

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Open `.env` and set real local values:

```text
GEMINI_API_KEY=your Google AI Studio key
OPENROUTER_API_KEY=your OpenRouter key (Nvidia fallback)
OPENROUTER_API_KEY_2=a second OpenRouter key (Qwen fallback)
LITELLM_MASTER_KEY=sk-a-long-random-client-key
```

Generate a proxy key with Python:

```bat
python -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"
```

Copy generated value into `LITELLM_MASTER_KEY`. Create this key yourself.
LiteLLM does not issue it.

Keep all keys server-side. `LITELLM_MASTER_KEY` authenticates clients to LiteLLM. The provider keys authenticate LiteLLM to Gemini and OpenRouter. Never use one as another. Never commit `.env`.

## Start locally

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
litellm --config litellm_config.yaml --port 4000
```

Server URL: `http://localhost:4000`

The LiteLLM CLI loads `.env` for local development. The `app.py` entry point also loads `.env` and exposes `app` for the Vercel deployment.

## Test locally

Keep the proxy terminal running. In a second PowerShell terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python tests\test_proxy.py
```

The test client loads `LITELLM_MASTER_KEY` from `.env`.

The test checks:

- `GET /models`
- visible `carebridge-agent` alias
- invalid proxy key rejection
- invalid model alias rejection
- authenticated `POST /chat/completions`
- OpenAI-compatible response shape
- actual Gemini response

Manual request:

```powershell
$headers = @{
  Authorization = "Bearer $env:LITELLM_MASTER_KEY"
  "Content-Type" = "application/json"
}
$body = @{
  model = "carebridge-agent"
  messages = @(
    @{
      role = "user"
      content = "Explain in one sentence that you run through the CareBridge LiteLLM gateway."
    }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod http://localhost:4000/chat/completions -Method Post -Headers $headers -Body $body
```

Model discovery:

```powershell
Invoke-RestMethod http://localhost:4000/models -Headers @{
  Authorization = "Bearer $env:LITELLM_MASTER_KEY"
}
```

`/models` should list `carebridge-agent`. LiteLLM may also expose the same resource at `/v1/models`.

## Error checks

| Check | Expected result |
| --- | --- |
| Omit `Authorization` or use another key | HTTP 400/401/403 |
| Use unknown model alias | HTTP 400/404/422 |
| Remove `GEMINI_API_KEY`, restart, then call alias | Provider/configuration error; no Gemini response |
| Set an invalid `GEMINI_API_KEY`, restart, then call alias | Gemini authentication/provider error |

Provider errors remain visible in local LiteLLM logs. Do not replace them with custom generic middleware.

## Vercel deployment

The gateway is deployed on Vercel using `app.py` as the Python entry point and this config file. Deployment rules:

- `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY_2`, and `LITELLM_MASTER_KEY` are Vercel server environment variables;
- pushing to `main` redeploys the gateway automatically;
- use a strong `sk-` proxy key and rotate it if exposed;
- the Vercel function max duration must be at least 60s (the Edge Function aborts gateway calls after 55s);
- keep the gateway URL and key only in the Supabase Edge Function secrets (`LITELLM_BASE_URL`, `LITELLM_API_KEY`) and the local `carebridge-rag/.env`;
- never call the gateway directly from the browser.

`mock_testing_fallbacks` is disabled on the deployed proxy, so fallback behaviour is checked with real calls and the `x-litellm-model-group` response header.

Known limits: all providers are free tiers, so quotas can run out (Gemini embeddings allow about 1,000 per day per project). Cold starts after idle add a few seconds to the first request.

## Timeouts and retries

Each chat deployment has `timeout: 12` seconds and `router_settings.num_retries: 0`, so the worst case is primary, retry, and two fallback timeouts (48s). This stays under the Edge Function's 55s gateway timeout. If you add fallbacks or raise these values, keep the total below that limit.

Current routing shape:

```text
carebridge-agent (Gemini)
    ↓ on failure
carebridge-agent-retry (Gemini, same model)
    ↓ on failure
carebridge-agent-fallback (OpenRouter, Nvidia)
    ↓ on failure
carebridge-agent-fallback-2 (OpenRouter, Qwen, second key)
```

LiteLLM `router_settings.fallbacks` handles failover. No custom fallback code exists in `app.py`.

## Project structure

```text
carebridge-liteLLM/
├── app.py
├── litellm_config.yaml
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
├── CAREBRIDGE_GATEWAY_CONTEXT.md
└── tests/
    ├── test_proxy.py
    └── test_tool_roundtrip.ps1
```

## Security rules

- No CareBridge database, Supabase client, Postgres, Redis, or clinic tools belong here.
- No provider key is hardcoded.
- `.env` is ignored by Git.
- `LITELLM_MASTER_KEY` and the provider keys (`GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY_2`) are different secrets.
- The proxy requires the master key and must stay server-to-server.
- LiteLLM returns model output and tool-call requests; the Edge Function validates and executes tools.
