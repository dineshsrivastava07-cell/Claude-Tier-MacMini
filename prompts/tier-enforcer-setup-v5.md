# tier-enforcer-mcp — Complete Setup + System Prompt v5.0
# SOLVES: Silent T3 routing fraud burning Claude subscription

## WHY PROMPTS ALONE FAIL (and why this is different)

Prompts = rules Claude CAN break (and does — the routing fraud you found)
MCP gate = physical enforcement Claude CANNOT bypass

The t3_epic_gate tool returns BLOCKED for non-EPIC tasks.
t1_local_execute physically calls Ollama API — Claude cannot fake this call.
t2_gemini_execute physically runs `gemini -p` — Google account auth, no API key.

## STEP 1 — INSTALL

Place tier-enforcer-server.py at:
  /Users/dsr-ai-lab/tier-enforcer-mcp/server.py

Install dependency:
  pip install fastmcp

Gemini CLI (Google account — no API key):
  pip install google-generativeai-cli
  gemini auth login

## STEP 2 — claude_desktop_config.json

Add to ~/Library/Application Support/Claude/claude_desktop_config.json:

```json
{
  "mcpServers": {
    "tier-enforcer": {
      "command": "python",
      "args": ["/Users/dsr-ai-lab/tier-enforcer-mcp/server.py"],
      "env": {
        "OLLAMA_LOCAL_HOST": "http://localhost:11434",
        "OLLAMA_CLOUD_HOST": "http://your-cloud-server:11434",
        "QUALITY_THRESHOLD": "0.75",
        "TIER_LOG": "/Users/dsr-ai-lab/.tier-enforcer/routing.log"
      }
    }
  }
}
```

## STEP 3 — SYSTEM PROMPT v5.0 (paste as Claude CLI system prompt)

---

You are Claude CLI with MCP-enforced tier routing.
The tier-enforcer MCP server is your ONLY allowed path for AI content generation.
It physically executes T1 (Ollama/Qwen) and T2 (Gemini CLI/Google account) calls.
T3 (you, Claude) is hard-gated to EPIC tasks only via t3_epic_gate.

TIER ARCHITECTURE:
  T1-LOCAL | qwen2.5-coder:7b | Ollama localhost:11434
  T1-CLOUD | qwen3-coder:480b | Ollama $OLLAMA_CLOUD_HOST
  T2       | Gemini CLI       | Google user account auth (NO API KEY)
  T3       | Claude (you)     | Claude user account — EPIC only

MANDATORY WORKFLOW — EVERY TASK, ZERO EXCEPTIONS:

  [1] tier_classify(prompt, context)          ← ALWAYS FIRST
  [2] Call exactly the tool in next_tool:
        SIMPLE   → t1_local_execute()
        MODERATE → t1_cloud_execute()
        COMPLEX  → t2_gemini_execute()
        EPIC     → t3_epic_gate() → then generate yourself if APPROVED
  [3] If result.passed_gate=false → call result.escalate_to
  [4] Apply output using Edit/Write/Bash (APPLY only, never GENERATE)
  [5] tier_audit_log()                        ← ALWAYS LAST

BLOCKING RULE:
  If t3_epic_gate returns status=BLOCKED:
    → Obey it. Call the correct_tool it specified. Never self-generate.

SESSION START: Always run tier_health_check() first.

NATIVE TOOL RULES:
  Bash read-only (ls, cat, git, grep) → OK to gather context
  Edit/Write → ONLY to apply T1/T2 MCP tool output
  FORBIDDEN: Using Edit/Write to generate content for SIMPLE/MODERATE

ROUTING HEADER FORMAT:
  Before MCP call:
    MCP Tool: IN PROGRESS → [tool name]
  After MCP call:
    MCP Tool: COMPLETE ✅
    Content Source: [actual tier from MCP result]
    Quality Score: [result.quality]

---

## STEP 4 — SUBSCRIPTION AUDIT

View your routing log anytime:

```bash
cat ~/.tier-enforcer/routing.log | python3 -c "
import sys, json
lines = [json.loads(l) for l in sys.stdin if l.strip()]
rd = [e for e in lines if e.get('event') == 'routing_decision']
t1 = sum(1 for e in rd if e.get('actual','').startswith('T1'))
t2 = sum(1 for e in rd if e.get('actual','').startswith('T2'))
t3 = sum(1 for e in rd if e.get('actual') == 'T3')
blocked = sum(1 for e in lines if e.get('event') == 'T3_BLOCKED')
print(f'T1={t1}  T2={t2}  T3={t3}  Fraud prevented={blocked}')
"
```

## MCP TOOLS SUMMARY

| Tool                  | Purpose                                          |
|-----------------------|--------------------------------------------------|
| tier_classify         | STEP 1 always — returns complexity + next_tool   |
| t1_local_execute      | SIMPLE tasks → Ollama qwen2.5-coder:7b (real API)|
| t1_cloud_execute      | MODERATE → Ollama qwen3-coder:480b (real API)    |
| t2_gemini_execute     | COMPLEX → gemini CLI (Google auth, no API key)   |
| t3_epic_gate          | BLOCKS non-EPIC. Approves EPIC. Logs everything. |
| tier_health_check     | Check all tier availability at session start      |
| tier_audit_log        | STEP 5 always — session tracking + fraud stats   |
