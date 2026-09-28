# CareBridge LiteLLM Gateway

Small model gateway for CareBridge AI V2. It exposes one OpenAI-compatible API and hides provider details from the CareBridge application.

```text
CareBridge Frontend
        ↓
Supabase Edge Function
        ↓
LiteLLM
        ↓
Gemini
```

This is a separate project because authentication, roles, tool execution, business rules, and Supabase access belong in the Supabase Edge Function. LiteLLM only handles model/provider abstraction, the application model alias, provider credentials, and future routing.

LiteLLM must never connect to Supabase, authenticate CareBridge users, execute tools or SQL, or receive browser traffic in the final architecture.

## Current configuration

| Application model | Provider model | Order |
| --- | --- | --- |
| `carebridge-agent` | `gemini/gemini-3.1-flash-lite` | 1 |
| `carebridge-agent` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | 2 |

`litellm_config.yaml` is the routing source of truth. It contains no credentials. Both deployments share one client-facing model group. LiteLLM tries Gemini first, then OpenRouter when Gemini fails.

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
LITELLM_MASTER_KEY=sk-a-long-random-client-key
```

Generate a proxy key with Python:

```bat
python -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"
```

Copy generated value into `LITELLM_MASTER_KEY`. Create this key yourself.
LiteLLM does not issue it.

Keep both keys server-side. `LITELLM_MASTER_KEY` authenticates clients to LiteLLM. `GEMINI_API_KEY` authenticates LiteLLM to Gemini. Never use one as the other. Never commit `.env`.

## Start locally

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
litellm --config litellm_config.yaml --port 4000
```

Server URL: `http://localhost:4000`

The LiteLLM CLI loads `.env` for local development. The `app.py` entry point also loads `.env` and exposes `app` for the future Vercel deployment.

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

## Future Vercel deployment

Do not deploy this milestone yet. Official LiteLLM-on-Vercel support uses a Python entry point like `app.py` and this config file. Before deployment:

- configure `GEMINI_API_KEY` and `LITELLM_MASTER_KEY` as Vercel server environment variables;
- configure `OPENROUTER_API_KEY` as a Vercel server environment variable;
- use a strong `sk-` proxy key and rotate it if exposed;
- confirm Vercel Python runtime and request-duration limits for the selected plan;
- test cold starts, tool/function-calling pass-through, timeouts, and provider errors;
- keep the gateway URL and key only in the Supabase Edge Function;
- never call the gateway directly from the browser.

Current routing shape:

```text
carebridge-agent
    ↓
Primary Gemini (order 1)
    ↓
OpenRouter fallback (order 2)
```

LiteLLM native deployment ordering handles failover. No custom fallback code exists in `app.py`.

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
└── tests/
    └── test_proxy.py
```

## Security rules

- No CareBridge database, Supabase client, Postgres, Redis, or clinic tools belong here.
- No provider key is hardcoded.
- `.env` is ignored by Git.
- `LITELLM_MASTER_KEY` and `GEMINI_API_KEY` are different secrets.
- The proxy is authenticated locally and must stay server-to-server in production.
- LiteLLM returns model output and tool-call requests; the Edge Function validates and executes tools.

## Next milestone

Build the minimal Supabase Edge Function adapter: authenticate the CareBridge user, apply role/tool policy, call this gateway with `model = "carebridge-agent"`, and return a provider-neutral response. Do not add clinic tools until that boundary is tested.
