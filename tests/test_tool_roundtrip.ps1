# Tests one full tool-call round-trip through the gateway on the primary model
# group and directly on the fallback model group.
# Usage: .\tests\test_tool_roundtrip.ps1 -Gateway https://your-gateway.vercel.app [-Key sk-...]
# Without -Key, LITELLM_MASTER_KEY is read from the local .env file.
param(
  [Parameter(Mandatory = $true)][string]$Gateway,
  [string]$Key
)

$Gateway = $Gateway.Trim().Trim('"', "'").TrimEnd('/')
if (-not $Key) {
  $envFile = Join-Path $PSScriptRoot "..\.env"
  $Key = (Get-Content $envFile | Where-Object { $_ -match '^\s*LITELLM_MASTER_KEY\s*=' } | Select-Object -First 1) `
    -replace '^\s*LITELLM_MASTER_KEY\s*=\s*', '' -replace '["'']', ''
  if (-not $Key) { throw "LITELLM_MASTER_KEY not found in $envFile" }
}
$key = $Key

$headers = @{ Authorization = "Bearer $($key.Trim())" }
$tools = @(@{
    type     = "function"
    function = @{ name = "get_doctors"; description = "List clinic doctors"; parameters = @{ type = "object"; properties = @{} } }
  })

function Invoke-Gateway($body) {
  Invoke-RestMethod "$Gateway/chat/completions" -Method Post -Headers $headers `
    -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 30) -TimeoutSec 90
}

function Test-ToolRoundTrip($label, $model) {
  $messages = @(@{ role = "user"; content = "Which doctors work at the clinic? Use the tool." })
  try {
    $first = Invoke-Gateway @{ model = $model; messages = $messages; tools = $tools }
  } catch {
    "$label step 1 FAIL: $($_.ErrorDetails.Message) $($_.Exception.Message)"; return
  }
  $message = $first.choices[0].message
  "$label step 1 model=$($first.model) tool_calls=$(@($message.tool_calls).Count)"
  if (-not $message.tool_calls) { "$label FAIL: model did not call the tool. Reply: $($message.content)"; return }

  $messages += $message
  $messages += @{
    role         = "tool"
    tool_call_id = $message.tool_calls[0].id
    content      = '{"ok":true,"doctors":[{"name":"Dr. Rahman","specialization":"Cardiology"}]}'
  }
  try {
    $second = Invoke-Gateway @{ model = $model; messages = $messages; tools = $tools }
    "$label step 2 OK model=$($second.model): $($second.choices[0].message.content)"
  } catch {
    "$label step 2 FAIL: $($_.ErrorDetails.Message) $($_.Exception.Message)"
  }
}

# PRIMARY may report the fallback model when Gemini is overloaded (503); that is the fallback working.
Test-ToolRoundTrip "PRIMARY" "carebridge-agent"
Test-ToolRoundTrip "FALLBACK" "carebridge-agent-fallback"
