# Claude CLI — Intelligent Tier Routing (NATIVE — injected on every session)
#   Auto-injects ~/.claude/tier-routing.md as system prompt via
#   --append-system-prompt so CLAUDE.md + tier routing both stay active.
#   T1-LOCAL: qwen2.5-coder:7b (Ollama) | T1-CLOUD: qwen3-coder:480b (Ollama)
#   T2: Gemini Fleet (account) | T3: Claude (direct — this instance)
# ═══════════════════════════════════════════════════════════════════════════
export CLAUDE_BINARY="/Users/dsr-ai-lab/.local/bin/claude"
export CLAUDE_TIER_PROMPT="$HOME/.claude/tier-routing.md"

function 
# ─────────────────────────────────────────────────────────
claude() {
  # Force API key mode — block OAuth path
  unset ANTHROPIC_ACCESS_TOKEN
  unset CLAUDE_OAUTH_TOKEN
      # ── STARTUP BANNER — DSR AI-Lab Tier Routing v6 ──────────────────────
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════════╗"
  echo "║  DSR AI-LAB — TIER ROUTING v6 — ACTIVE (NON-NEGOTIABLE)             ║"
  echo "╠══════════════════════════════════════════════════════════════════════╣"
  echo "║  Brain  : Claude (plan only — NEVER self-executes)                  ║"
  echo "║  MCP    : tier-enforcer-mcp  tier-router-mcp  (AUTO-START)          ║"
  echo "║  Skill  : /tier-routing  /tier-health  /tier-audit  /tier-reset     ║"
  echo "║  Trace  : LangSmith ✓  Project: dsr-ai-lab-tier-routing             ║"
  echo "║  Prompt : ~/.claude/CLAUDE.md (v6) + tier-routing.md (injected)     ║"
  echo "╠══════════════════════════════════════════════════════════════════════╣"
  echo "║  T1-LOCAL : qwen2.5-coder:7b       → SIMPLE          (Ollama local) ║"
  echo "║  T1-MID   : qwen3-coder:30b        → MODERATE-SMALL  (Ollama cloud) ║"
  echo "║  T1-CLOUD : qwen3-coder:480b-cloud → MODERATE-LARGE  (Ollama cloud) ║"
  echo "║  T2-FLASH : gemini-2.5-flash       → COMPLEX-FAST    (Gemini CLI)   ║"
  echo "║  T2-PRO   : gemini-2.5-pro         → COMPLEX-DEEP    (Gemini CLI)   ║"
  echo "║  T2-KIMI  : Kimi-K2-Instruct       → COMPLEX-REASON  (HF API)       ║"
  echo "║  T3       : claude-sonnet-4-6      → EPIC ONLY        (Subscription)║"
  echo "╠══════════════════════════════════════════════════════════════════════╣"
  echo "║  CHAIN : T1-LOCAL→T1-MID→T1-CLOUD→T2-FLASH→T2-PRO→T2-KIMI→T3      ║"
  echo "║  GATE  : T3 BLOCKED unless EPIC or full chain exhausted              ║"
  echo "║  EXEC  : Ollama T1 executes | T2 analysis only | T3 blueprint only  ║"
  echo "╚══════════════════════════════════════════════════════════════════════╝"
  echo ""

  # Inject tier-routing.md as system prompt on every session
  if [[ -f "$CLAUDE_TIER_PROMPT" ]] \
     && [[ "$*" != *"--system-prompt"* ]] \
     && [[ "$*" != *"--append-system-prompt"* ]]; then
    "$CLAUDE_BINARY" --append-system-prompt "$(cat "$CLAUDE_TIER_PROMPT")" "$@"
  else
    "$CLAUDE_BINARY" "$@"
  fi
}

# Bypass tier routing (raw Claude CLI — no injection)
alias claude-raw="$CLAUDE_BINARY"
function claude-tier-status() {
  local f="$HOME/.claude/tier-routing.md"
  if [[ -f "$f" ]]; then
    echo "Tier routing : ACTIVE"
    echo "Prompt file  : $f ($(wc -l < "$f") lines)"
    echo "Injected via : claude() --append-system-prompt"
    echo "Bypass raw   : claude-raw"
  else
    echo "Tier routing : MISSING — $f not found"
  fi
}
alias ai-services='~/.local/bin/ai-services'   # status/control AI services
alias ai-status='~/.local/bin/ai-services'      # same
export PATH="$HOME/.npm-global/bin:$PATH"
