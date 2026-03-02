# LiteLLM Proxy Config — Unified Tier Endpoint

LiteLLM provides a single OpenAI-compatible endpoint that internally routes to all tiers.
This lets any OpenAI SDK client use the tier router transparently.

## Install

```bash
pip install litellm[proxy]
# or
uv add litellm
```

## config.yaml (Tier-Mapped)

```yaml
model_list:
  # T1-LOCAL
  - model_name: t1-local
    litellm_params:
      model: ollama/qwen2.5-coder:7b
      api_base: http://localhost:11434
      temperature: 0.1
      num_ctx: 32768

  # T1-CLOUD
  - model_name: t1-cloud
    litellm_params:
      model: ollama/qwen3-coder:480b-cloud
      api_base: "${OLLAMA_CLOUD_HOST:-http://localhost:11434}"
      temperature: 0.1
      num_ctx: 131072
      timeout: 300

  # T2-PRO
  - model_name: t2-pro
    litellm_params:
      model: gemini/gemini-2.5-pro
      api_key: "${GEMINI_API_KEY}"

  # T2-FLASH
  - model_name: t2-flash
    litellm_params:
      model: gemini/gemini-2.5-flash
      api_key: "${GEMINI_API_KEY}"

  # T2-LITE
  - model_name: t2-lite
    litellm_params:
      model: gemini/gemini-2.5-flash-lite-preview-06-17
      api_key: "${GEMINI_API_KEY}"

  # T3
  - model_name: t3
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: "${ANTHROPIC_API_KEY}"
      max_tokens: 8192

  # Auto-router (maps to tier-router-mcp logic via fallback)
  - model_name: auto
    litellm_params:
      model: ollama/qwen2.5-coder:7b
      api_base: http://localhost:11434

litellm_settings:
  # Global quality fallback chain
  fallbacks:
    - { t1-local:  [t1-cloud, t2-flash, t3] }
    - { t1-cloud:  [t2-flash, t3] }
    - { t2-pro:    [t2-flash, t3] }
    - { t2-flash:  [t2-pro, t3] }
    - { t2-lite:   [t2-flash, t1-cloud] }

  timeout: 120
  num_retries: 2
  set_verbose: false
  drop_params: true   # ignore unknown params (e.g. num_ctx for non-ollama)

router_settings:
  routing_strategy: simple-shuffle    # or: usage-based-routing, latency-based-routing
  num_retries: 2
  retry_after: 5

general_settings:
  master_key: "${LITELLM_MASTER_KEY}"
  database_url: "${DATABASE_URL}"     # optional — for usage tracking
  store_model_in_db: true
```

## Start Proxy

```bash
litellm --config config.yaml --port 4002 --host 0.0.0.0

# Background
litellm --config config.yaml --port 4002 &

# With Docker
docker run -p 4002:4002 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  ghcr.io/berriai/litellm:main \
  --config /app/config.yaml --port 4002
```

## Use from Any OpenAI Client

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  apiKey:  "anything",   // litellm uses master key
  baseURL: "http://localhost:4002/v1",
});

// Use T1-LOCAL
const r1 = await client.chat.completions.create({
  model:    "t1-local",
  messages: [{ role: "user", content: "Write a quicksort in TypeScript" }],
});

// Use T2-PRO
const r2 = await client.chat.completions.create({
  model:    "t2-pro",
  messages: [{ role: "user", content: "Analyse the trade-offs of CQRS" }],
  max_tokens: 8192,
});

// Auto-route (falls back through chain automatically)
const r3 = await client.chat.completions.create({
  model:    "auto",
  messages: [{ role: "user", content: "Implement JWT auth middleware" }],
});
```

## Use from Python

```python
from openai import OpenAI

client = OpenAI(api_key="anything", base_url="http://localhost:4002/v1")

# T1-LOCAL
response = client.chat.completions.create(
    model="t1-local",
    messages=[{"role": "user", "content": "Write a binary search in Python"}]
)
print(response.choices[0].message.content)

# T2-PRO for analytics
response = client.chat.completions.create(
    model="t2-pro",
    messages=[{"role": "user", "content": "Build a ClickHouse analytics query for SPSF KPI"}],
    max_tokens=8192
)
```

## Health Check

```bash
curl http://localhost:4002/health
curl http://localhost:4002/health/liveliness
curl http://localhost:4002/v1/models   # list registered models
```

## Cost Tracking Dashboard

```bash
# LiteLLM has a built-in UI at:
http://localhost:4002/ui

# Or use the API
curl http://localhost:4002/spend/logs
```

## LaunchAgent (macOS auto-start)

```xml
<!-- ~/Library/LaunchAgents/com.litellm.tier-proxy.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.litellm.tier-proxy</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/litellm</string>
    <string>--config</string>
    <string>/Users/dsr-ai-lab/tier-router-mcp/litellm-config.yaml</string>
    <string>--port</string>
    <string>4002</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>GEMINI_API_KEY</key>
    <string>$(GEMINI_API_KEY)</string>
    <key>ANTHROPIC_API_KEY</key>
    <string>$(ANTHROPIC_API_KEY)</string>
    <key>OLLAMA_CLOUD_HOST</key>
    <string>http://localhost:11434</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/litellm-tier.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/litellm-tier-err.log</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.litellm.tier-proxy.plist
launchctl start com.litellm.tier-proxy
```

## zshrc Aliases

```bash
alias litellm-status="curl -s http://localhost:4002/health | python3 -m json.tool"
alias litellm-models="curl -s http://localhost:4002/v1/models | python3 -m json.tool"
alias litellm-logs="tail -f /tmp/litellm-tier.log"
```
