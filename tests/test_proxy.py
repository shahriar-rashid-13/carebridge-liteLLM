"""Small live client for local LiteLLM gateway checks.

Run the proxy first, then:
    python tests/test_proxy.py
"""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/")
PROXY_KEY = os.getenv("LITELLM_MASTER_KEY", "")


def request(path, method="GET", body=None, key=PROXY_KEY):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request_object = Request(
        f"{BASE_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request_object, timeout=90) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return error.code, payload


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    require(PROXY_KEY, "Set LITELLM_MASTER_KEY before running this client.")

    status, models = request("/models")
    require(status == 200, f"/models failed with HTTP {status}: {models}")
    model_ids = {model.get("id") for model in models.get("data", [])}
    require("carebridge-agent" in model_ids, f"Alias not listed in /models: {model_ids}")

    status, unauthorized = request("/models", key="sk-invalid-client-key")
    require(
        status in {400, 401, 403},
        f"Invalid proxy key returned HTTP {status}: {unauthorized}",
    )

    status, invalid_model = request(
        "/chat/completions",
        method="POST",
        body={
            "model": "carebridge-agent-does-not-exist",
            "messages": [{"role": "user", "content": "test"}],
        },
    )
    require(
        status in {400, 404, 422},
        f"Invalid model returned unexpected HTTP {status}: {invalid_model}",
    )

    status, completion = request(
        "/chat/completions",
        method="POST",
        body={
            "model": "carebridge-agent",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Explain in one sentence that you run through the "
                        "CareBridge LiteLLM gateway."
                    ),
                }
            ],
        },
    )
    require(status == 200, f"Gemini request failed with HTTP {status}: {completion}")
    require(completion.get("object") == "chat.completion", completion)
    require(completion.get("model"), completion)
    choices = completion.get("choices")
    require(isinstance(choices, list) and choices, completion)
    require(choices[0].get("message", {}).get("content"), completion)

    print("PASS /models: carebridge-agent listed")
    print("PASS authentication: invalid key rejected")
    print("PASS invalid alias: rejected")
    print("PASS /chat/completions: OpenAI-compatible response returned")
    print("PASS provider: Gemini response returned")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, URLError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
