#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  DSR AI-LAB — TIER ENFORCER MCP SERVER v5.1                        ║
║  File: ~/tier-enforcer-mcp/server.py  (REPLACE EXISTING)           ║
║  9 Tiers · LangSmith Traces · Kimi-K2 · qwen3-coder-next           ║
║  + execute_task() — LangGraph auto-invoked master entry point       ║
║    Layer 1 (OAuth auth) untouched · Layer 2 (tasks) hard enforced  ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, subprocess, urllib.request, urllib.error
from fastmcp import FastMCP

# ── Optional LangSmith tracing ────────────────────────────────────────
try:
    from langsmith import traceable
    LANGSMITH_ENABLED = bool(os.environ.get("LANGCHAIN_API_KEY"))
except ImportError:
    def traceable(**kwargs):
        def decorator(fn): return fn
        return decorator
    LANGSMITH_ENABLED = False

# ── Optional HuggingFace for Kimi-K2 ─────────────────────────────────
try:
    from huggingface_hub import InferenceClient
    HF_ENABLED = bool(os.environ.get("HF_API_KEY"))
except ImportError:
    HF_ENABLED = False

mcp = FastMCP("tier-router-mcp")

# ── CONFIGURATION ─────────────────────────────────────────────────────
OLLAMA_LOCAL      = os.environ.get("OLLAMA_LOCAL_HOST",  "http://localhost:11434")
OLLAMA_CLOUD      = os.environ.get("OLLAMA_CLOUD_HOST",  "http://localhost:11434")
OLLAMA_CLOUD_API  = "https://api.ollama.com"
OLLAMA_API_KEY    = os.environ.get("OLLAMA_API_KEY", "")
QUALITY_GATE  = float(os.environ.get("QUALITY_THRESHOLD", "0.75"))
LOG_PATH      = os.path.expanduser("~/.tier-enforcer/routing.log")
MEMORY_PATH   = os.path.expanduser("~/.tier-enforcer/memory.db")

# ── TIER MODEL MAPPING ────────────────────────────────────────────────
TIERS = {
    "T1-LOCAL":  {"model": "qwen2.5-coder:7b",        "host": OLLAMA_LOCAL,      "type": "ollama"},
    "T1-MID":    {"model": "qwen3-coder-next",           "host": OLLAMA_CLOUD_API,  "type": "ollama-cloud"},
    "T1-CLOUD":  {"model": "qwen3-coder:480b-cloud",   "host": OLLAMA_CLOUD,      "type": "ollama"},
    "T2-FLASH":  {"model": "gemini-2.5-flash",         "host": "gemini-cli",  "type": "gemini"},
    "T2-PRO":    {"model": "gemini-2.5-pro",           "host": "gemini-cli",  "type": "gemini"},
    "T2-KIMI":   {"model": "moonshotai/Kimi-K2-Instruct", "host": "hf-api",  "type": "huggingface"},
    "T3":        {"model": "claude-sonnet-4-6",        "host": "claude-cli",  "type": "claude"},
}

FALLBACK_CHAIN = ["T1-LOCAL", "T1-MID", "T1-CLOUD", "T2-FLASH", "T2-PRO", "T2-KIMI", "T3"]

# ══════════════════════════════════════════════════════════════════════
#  HARDCODED ROUTING RULES  (replaces tier-routing.md — same purpose,
#  enforced by Python code not prompt — cannot drift, cannot be ignored)
#  Source: tier-routing-v5.1.md — embedded here permanently
# ══════════════════════════════════════════════════════════════════════

# ── LAYER 1: AUTH (never routed — runs before MCP tools exist) ────────
# OAuth handshake at Claude CLI startup runs at process level.
# tier-routing rules and MCP tools do not exist yet during auth.
# T3 gate cannot fire during auth — it is infrastructure, not a task.
# After auth completes → Claude CLI shell opens → Layer 2 begins.
LAYER_1_AUTH_BYPASS = True   # auth always bypasses routing — hardcoded, not configurable

# ── LAYER 2: TASK ROUTING RULES (hardcoded — enforced by classify_node) ─
# These keyword sets drive the classify_node in langgraph_tier.py
# AND the tier_classify() MCP tool below — single source of truth.

ROUTING_RULES = {
    # ── T3: EPIC ONLY ─────────────────────────────────────────────────
    # Approved: complexity==EPIC OR chain_exhausted OR force+reason
    # Blocked:  everything else — hard gate, no exceptions
    "EPIC": {
        "tier":     "T3",
        "model":    "claude-sonnet-4-6",
        "keywords": ["greenfield", "new platform", "full system", "epic",
                     "build entire", "from scratch", "new product",
                     "new application", "complete system"],
        "gate":     "t3_epic_gate",          # mandatory hard gate
        "blocked_if_not_epic": True,         # hardcoded block
    },

    # ── T2-KIMI: Math / Stats / Algorithms ────────────────────────────
    "COMPLEX-REASON": {
        "tier":     "T2-KIMI",
        "model":    "moonshotai/Kimi-K2-Instruct",
        "keywords": ["math", "statistic", "algorithm", "proof", "formula",
                     "calculus", "matrix", "eigenvalue", "differential",
                     "regression model", "optimization problem", "bayesian",
                     "numerical method", "probability dist", "linear algebra",
                     "fourier", "gradient descent", "loss function"],
        "gate":     None,
    },

    # ── T2-PRO: Deep analysis / Architecture ──────────────────────────
    "COMPLEX-DEEP": {
        "tier":     "T2-PRO",
        "model":    "gemini-2.5-pro",
        "keywords": ["architecture", "security audit", "system design",
                     "deep analysis", "rca", "root cause", "tech spec",
                     "infrastructure design", "capacity planning",
                     "performance analysis", "comprehensive review",
                     "technical specification", "design document"],
        "gate":     None,
    },

    # ── T2-FLASH: Debug / Refactor / Integration ──────────────────────
    "COMPLEX-FAST": {
        "tier":     "T2-FLASH",
        "model":    "gemini-2.5-flash",
        "keywords": ["debug", "fix bug", "refactor", "multi-file",
                     "cross-module", "e2e wiring", "wire", "oauth flow",
                     "api integration", "integration test", "trace error",
                     "stack trace", "exception handling", "iterate"],
        "gate":     None,
    },

    # ── T1-CLOUD: Feature sets / Pipelines ────────────────────────────
    "MODERATE-LARGE": {
        "tier":     "T1-CLOUD",
        "model":    "qwen3-coder:480b-cloud",
        "keywords": ["feature set", "multiple files", "new module",
                     "database schema", "auth system", "full feature",
                     "rpa", "automation workflow", "ai agent", "llm app",
                     "pipeline", "end to end feature", "service layer"],
        "gate":     None,
    },

    # ── T1-MID: Single features / Components ──────────────────────────
    "MODERATE-SMALL": {
        "tier":     "T1-MID",
        "model":    "qwen3-coder-next",
        "keywords": ["implement", "create feature", "add component",
                     "new service", "unit test", "api endpoint", "crud",
                     "new class", "new function", "add method",
                     "write test", "add route"],
        "gate":     None,
    },

    # ── T1-LOCAL: Simple / Single file / Config ───────────────────────
    "SIMPLE": {
        "tier":     "T1-LOCAL",
        "model":    "qwen2.5-coder:7b",
        "keywords": [],   # default fallback — everything else
        "gate":     None,
    },
}

# ── QUALITY GATE RULES (hardcoded — enforced by quality_gate_node) ────
QUALITY_RULES = {
    "threshold":         QUALITY_GATE,          # 0.75 — escalate if below
    "escalate_action":   "next_tier_in_chain",  # move to next tier
    "exhausted_action":  "T3_gate",             # if T2-KIMI fails → T3 gate
    "max_fallbacks":     6,                     # T1-LOCAL → T2-KIMI = 6 steps
}

# ── SESSION START RULES (hardcoded procedure) ─────────────────────────
SESSION_START_PROCEDURE = [
    "tier_health_check(tier='ALL')",   # step 1 — verify all tiers live
    "check_budget()",                  # step 2 — confirm T3 cap status
    "/clear",                          # step 3 — fresh context
]

# ── SKIP execute_task FOR THESE CALLS ONLY ────────────────────────────
INFRASTRUCTURE_CALLS = {
    "tier_health_check", "check_budget", "tier_audit_log",
    "/tier-audit", "/tier-debug", "/tier-report",
    "/tier-reset", "/tier-health",
}

# ── MASTER ROUTING RULE (enforced by execute_task) ────────────────────
# Single rule: every user task → execute_task() → LangGraph graph
# No manual tool chaining. No direct T3 calls. No skipping classify.
MASTER_RULE = "execute_task(task, session_id)"  # only entry point

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

# ── HELPER: AUDIT LOG ─────────────────────────────────────────────────
def _write_log(entry: dict):
    entry["timestamp"] = time.time()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ── HELPER: OLLAMA CALL ───────────────────────────────────────────────
@traceable(name="ollama-call", run_type="llm")
def _call_ollama(host: str, model: str, prompt: str,
                 system: str = "You are a helpful coding assistant.") -> str:
    payload = json.dumps({
        "model": model, "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 131072, "seed": 42},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt}
        ]
    }).encode()
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
        return result["message"]["content"]

# ── HELPER: OLLAMA CLOUD CALL (OpenAI-compatible api.ollama.com) ──────
@traceable(name="ollama-cloud-call", run_type="llm")
def _call_ollama_cloud(model: str, prompt: str,
                       system: str = "You are a helpful coding assistant.") -> str:
    api_key = os.environ.get("OLLAMA_API_KEY", OLLAMA_API_KEY)
    payload = json.dumps({
        "model": model, "stream": False,
        "temperature": 0.1, "max_tokens": 4096,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt}
        ]
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_CLOUD_API}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]

# ── HELPER: GEMINI CALL ───────────────────────────────────────────────
@traceable(name="gemini-call", run_type="llm")
def _call_gemini(model: str, prompt: str) -> str:
    result = subprocess.run(
        ["gemini", "-m", model, "-p", prompt],
        capture_output=True, text=True, timeout=180
    )
    if result.returncode != 0:
        raise RuntimeError(f"Gemini CLI error: {result.stderr[:200]}")
    return result.stdout.strip()

# ── HELPER: KIMI-K2 CALL ─────────────────────────────────────────────
@traceable(name="kimi-k2-call", run_type="llm")
def _call_kimi(prompt: str) -> str:
    if not HF_ENABLED:
        raise RuntimeError("HF_API_KEY not set — cannot call Kimi-K2")
    client = InferenceClient(
        model="moonshotai/Kimi-K2-Instruct",
        token=os.environ.get("HF_API_KEY")
    )
    response = client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8192, temperature=0.1
    )
    return response.choices[0].message.content

# ── HELPER: QUALITY SCORE ─────────────────────────────────────────────
def _score(result: str, task: str) -> float:
    if not result or len(result) < 10: return 0.0
    score = 0.5
    if len(result) > 100:  score += 0.1
    if len(result) > 500:  score += 0.1
    if "```" in result and any(k in task.lower()
       for k in ["code","implement","write","create","fix","build","refactor"]):
        score += 0.15
    if not any(bad in result.lower()
               for bad in ["i cannot","i don't know","i'm unable","as an ai"]):
        score += 0.15
    return min(score, 1.0)

# ══════════════════════════════════════════════════════════════════════
#  TOOL 1: tier_classify
#  Driven by ROUTING_RULES — single source of truth, no duplicated keywords
# ══════════════════════════════════════════════════════════════════════
NEXT_TOOL_MAP = {
    "T3":       "t3_epic_gate",
    "T2-KIMI":  "t2_kimi_execute",
    "T2-PRO":   "t2_gemini_execute",
    "T2-FLASH": "t2_gemini_execute",
    "T1-CLOUD": "t1_cloud_execute",
    "T1-MID":   "t1_mid_execute",
    "T1-LOCAL": "t1_local_execute",
}

def _classify_task(task: str) -> tuple:
    """
    Core classification logic driven entirely by ROUTING_RULES dict.
    Single source of truth — used by tier_classify() MCP tool
    AND imported by langgraph_tier.py classify_node.
    Returns: (complexity, tier, next_tool)
    """
    t = task.lower()
    # Iterate complexity levels highest → lowest priority
    for complexity in ["EPIC", "COMPLEX-REASON", "COMPLEX-DEEP",
                        "COMPLEX-FAST", "MODERATE-LARGE", "MODERATE-SMALL"]:
        rule = ROUTING_RULES[complexity]
        if any(k in t for k in rule["keywords"]):
            tier = rule["tier"]
            return complexity, tier, NEXT_TOOL_MAP[tier]
    # Default: SIMPLE → T1-LOCAL
    return "SIMPLE", "T1-LOCAL", "t1_local_execute"

@mcp.tool()
def tier_classify(task: str, context: str = "") -> dict:
    """
    STEP 1 — called internally by execute_task() via LangGraph.
    Classifies task using ROUTING_RULES (hardcoded Python — not prompt).
    Rules are identical to tier-routing-v5.1.md — embedded here permanently.
    Layer 1 (OAuth auth) is never routed — runs before this tool exists.
    Layer 2 (user tasks) — always classified, always gated.
    """
    complexity, tier, next_tool = _classify_task(task)
    result = {
        "complexity":     complexity,
        "assigned_tier":  tier,
        "next_tool":      next_tool,
        "fallback_chain": " → ".join(FALLBACK_CHAIN),
        "quality_gate":   QUALITY_RULES["threshold"],
        "model":          TIERS[tier]["model"],
        "rule_source":    "ROUTING_RULES (hardcoded Python — single source of truth)",
        "t3_gate_required": tier == "T3",
        "layer":          "LAYER_2_TASK_ROUTING",
    }
    _write_log({"event": "classify", **result, "task_preview": task[:80]})
    return result

# ══════════════════════════════════════════════════════════════════════
#  TOOL 2: t1_local_execute
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
@traceable(name="T1-LOCAL", run_type="llm",
           metadata={"tier": "T1-LOCAL", "model": "qwen2.5-coder:7b"})
def t1_local_execute(task: str, context: str = "") -> dict:
    """
    T1-LOCAL: qwen2.5-coder:7b via Ollama localhost:11434
    Use for: SIMPLE tasks — single file, <20 lines, shell, config edits.
    REAL API CALL — not simulated.
    """
    t0 = time.time()
    cfg = TIERS["T1-LOCAL"]
    try:
        prompt = f"{context}\n\nTask: {task}".strip() if context else task
        result = _call_ollama(cfg["host"], cfg["model"], prompt)
        score  = _score(result, task)
        status = "PASS" if score >= QUALITY_GATE else "ESCALATE"
        entry  = {
            "event": "T1_LOCAL_EXECUTE", "model": cfg["model"],
            "quality": score, "status": status,
            "latency_ms": int((time.time()-t0)*1000),
            "task_preview": task[:80]
        }
        _write_log(entry)
        return {
            "tier": "T1-LOCAL", "model": cfg["model"],
            "api_call_made": True, "endpoint": cfg["host"],
            "result": result, "quality_score": score,
            "status": status,
            "next_tool": None if status == "PASS" else "t1_mid_execute"
        }
    except Exception as e:
        _write_log({"event": "T1_LOCAL_ERROR", "error": str(e)})
        return {"tier": "T1-LOCAL", "api_call_made": False,
                "error": str(e), "next_tool": "t1_mid_execute"}

# ══════════════════════════════════════════════════════════════════════
#  TOOL 3: t1_mid_execute  (NEW)
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
@traceable(name="T1-MID", run_type="llm",
           metadata={"tier": "T1-MID", "model": "qwen3-coder-next"})
def t1_mid_execute(task: str, context: str = "") -> dict:
    """
    T1-MID: qwen3-coder-next via Ollama cloud server (api.ollama.com).
    Use for: MODERATE-SMALL — 2-5 files, single feature, moderate refactor.
    REAL API CALL — not simulated.
    """
    t0 = time.time()
    cfg = TIERS["T1-MID"]
    try:
        prompt = f"{context}\n\nTask: {task}".strip() if context else task
        result = _call_ollama_cloud(cfg["model"], prompt)
        score  = _score(result, task)
        status = "PASS" if score >= QUALITY_GATE else "ESCALATE"
        _write_log({
            "event": "T1_MID_EXECUTE", "model": cfg["model"],
            "quality": score, "status": status,
            "latency_ms": int((time.time()-t0)*1000),
            "task_preview": task[:80]
        })
        return {
            "tier": "T1-MID", "model": cfg["model"],
            "api_call_made": True, "endpoint": cfg["host"],
            "result": result, "quality_score": score,
            "status": status,
            "next_tool": None if status == "PASS" else "t1_cloud_execute"
        }
    except Exception as e:
        _write_log({"event": "T1_MID_ERROR", "error": str(e)})
        return {"tier": "T1-MID", "api_call_made": False,
                "error": str(e), "next_tool": "t1_cloud_execute"}

# ══════════════════════════════════════════════════════════════════════
#  TOOL 4: t1_cloud_execute
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
@traceable(name="T1-CLOUD", run_type="llm",
           metadata={"tier": "T1-CLOUD", "model": "qwen3-coder:480b"})
def t1_cloud_execute(task: str, context: str = "") -> dict:
    """
    T1-CLOUD: qwen3-coder:480b via Ollama cloud server.
    Use for: MODERATE-LARGE — 5-10 files, feature-set, API integration.
    REAL API CALL — not simulated.
    """
    t0 = time.time()
    cfg = TIERS["T1-CLOUD"]
    try:
        prompt = f"{context}\n\nTask: {task}".strip() if context else task
        result = _call_ollama(cfg["host"], cfg["model"], prompt)
        score  = _score(result, task)
        status = "PASS" if score >= QUALITY_GATE else "ESCALATE"
        _write_log({
            "event": "T1_CLOUD_EXECUTE", "model": cfg["model"],
            "quality": score, "status": status,
            "latency_ms": int((time.time()-t0)*1000)
        })
        return {
            "tier": "T1-CLOUD", "model": cfg["model"],
            "api_call_made": True, "endpoint": cfg["host"],
            "result": result, "quality_score": score,
            "status": status,
            "next_tool": None if status == "PASS" else "t2_gemini_execute"
        }
    except Exception as e:
        return {"tier": "T1-CLOUD", "api_call_made": False,
                "error": str(e), "next_tool": "t2_gemini_execute"}

# ══════════════════════════════════════════════════════════════════════
#  TOOL 5: t2_gemini_execute
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
@traceable(name="T2-GEMINI", run_type="llm",
           metadata={"tier": "T2", "models": "gemini-2.5-flash/pro"})
def t2_gemini_execute(task: str, context: str = "",
                      model: str = "gemini-2.5-flash",
                      use_pro: bool = False) -> dict:
    """
    T2-GEMINI: gemini-2.5-flash (default) or gemini-2.5-pro (use_pro=True).
    T2-FLASH: COMPLEX-FAST — debug, iteration, multi-file refactor.
    T2-PRO:   COMPLEX-DEEP — analytics, architecture, security audit.
    Uses Google account CLI auth — no API key needed.
    """
    t0 = time.time()
    selected = "gemini-2.5-pro" if use_pro else "gemini-2.5-flash"
    tier_name = "T2-PRO" if use_pro else "T2-FLASH"
    try:
        prompt = f"{context}\n\nTask: {task}".strip() if context else task
        result = _call_gemini(selected, prompt)
        score  = _score(result, task)
        status = "PASS" if score >= QUALITY_GATE else "ESCALATE"
        _write_log({
            "event": f"{tier_name}_EXECUTE", "model": selected,
            "quality": score, "status": status,
            "latency_ms": int((time.time()-t0)*1000)
        })
        return {
            "tier": tier_name, "model": selected,
            "api_call_made": True, "method": "gemini-cli",
            "result": result, "quality_score": score,
            "status": status,
            "next_tool": None if status == "PASS" else "t2_kimi_execute"
        }
    except Exception as e:
        return {"tier": tier_name, "api_call_made": False,
                "error": str(e), "next_tool": "t2_kimi_execute"}

# ══════════════════════════════════════════════════════════════════════
#  TOOL 6: t2_kimi_execute  (NEW)
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
@traceable(name="T2-KIMI", run_type="llm",
           metadata={"tier": "T2-KIMI", "model": "Kimi-K2-Instruct"})
def t2_kimi_execute(task: str, context: str = "") -> dict:
    """
    T2-KIMI: Kimi-K2-Instruct via HuggingFace API.
    Use for: COMPLEX-REASON — mathematics, statistics, algorithms,
             proofs, optimization, numerical methods, data science.
    Requires HF_API_KEY in environment.
    """
    t0 = time.time()
    try:
        prompt = f"{context}\n\nTask: {task}".strip() if context else task
        result = _call_kimi(prompt)
        score  = _score(result, task)
        status = "PASS" if score >= QUALITY_GATE else "ESCALATE"
        _write_log({
            "event": "T2_KIMI_EXECUTE",
            "model": "moonshotai/Kimi-K2-Instruct",
            "quality": score, "status": status,
            "latency_ms": int((time.time()-t0)*1000)
        })
        return {
            "tier": "T2-KIMI", "model": "moonshotai/Kimi-K2-Instruct",
            "api_call_made": True, "method": "huggingface-inference-api",
            "result": result, "quality_score": score,
            "status": status,
            "next_tool": None if status == "PASS" else "t3_epic_gate"
        }
    except Exception as e:
        _write_log({"event": "T2_KIMI_ERROR", "error": str(e)})
        return {"tier": "T2-KIMI", "api_call_made": False,
                "error": str(e), "next_tool": "t3_epic_gate"}

# ══════════════════════════════════════════════════════════════════════
#  TOOL 7: t3_epic_gate  (HARD GATE — UNCHANGED FROM v4.1)
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
@traceable(name="T3-GATE", run_type="chain",
           metadata={"gate": "epic-only", "tier": "T3"})
def t3_epic_gate(task: str, complexity: str,
                 force: bool = False,
                 force_reason: str = "",
                 chain_exhausted: bool = False) -> dict:
    """
    T3 HARD GATE — PHYSICAL BLOCK.
    APPROVED only if: complexity==EPIC, chain_exhausted==True,
                      or force==True with documented reason.
    EVERYTHING ELSE IS BLOCKED. No exceptions.
    Logs every attempt — approved and blocked.
    """
    approved = (
        complexity == "EPIC" or
        chain_exhausted or
        (force and bool(force_reason))
    )

    reason = (
        "EPIC complexity — T3 appropriate"    if complexity == "EPIC"
        else "Full fallback chain exhausted"   if chain_exhausted
        else f"Force override: {force_reason}" if force
        else f"BLOCKED — complexity={complexity}. Use T1/T2 tools."
    )

    _write_log({
        "event":      "T3_APPROVED" if approved else "T3_BLOCKED",
        "complexity": complexity,
        "approved":   approved,
        "reason":     reason,
        "task_preview": task[:80],
        "fraud_prevented": not approved
    })

    if not approved:
        tier_map = {
            "SIMPLE":          "t1_local_execute",
            "MODERATE-SMALL":  "t1_mid_execute",
            "MODERATE-LARGE":  "t1_cloud_execute",
            "COMPLEX-FAST":    "t2_gemini_execute (use_pro=False)",
            "COMPLEX-DEEP":    "t2_gemini_execute (use_pro=True)",
            "COMPLEX-REASON":  "t2_kimi_execute",
        }
        return {
            "approved":      False,
            "reason":        reason,
            "correct_tool":  tier_map.get(complexity, "t2_gemini_execute"),
            "action":        "STOP — call the correct_tool instead of T3"
        }

    return {
        "approved":   True,
        "reason":     reason,
        "model":      "claude-sonnet-4-6",
        "action":     "PROCEED — Claude subscription authorized for this task"
    }

# ══════════════════════════════════════════════════════════════════════
#  TOOL 8: tier_health_check
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
def tier_health_check(tier: str = "ALL") -> dict:
    """
    Check health of all tiers or a specific tier.
    Run at session start. Reports latency and availability.
    """
    results = {}
    check_tiers = list(TIERS.keys()) if tier == "ALL" else [tier]

    for t in check_tiers:
        cfg = TIERS[t]
        t0 = time.time()
        try:
            if cfg["type"] == "ollama-cloud":
                api_key = os.environ.get("OLLAMA_API_KEY", OLLAMA_API_KEY)
                if not api_key:
                    results[t] = {
                        "status":  "NO_API_KEY",
                        "model":   cfg["model"],
                        "latency": "0ms",
                        "note":    "Set OLLAMA_API_KEY in env config"
                    }
                else:
                    req = urllib.request.Request(
                        f"{OLLAMA_CLOUD_API}/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                        method="GET"
                    )
                    with urllib.request.urlopen(req, timeout=10) as r:
                        data = json.loads(r.read())
                        models = [m["id"] for m in data.get("data", [])]
                        available = any(cfg["model"] in m for m in models)
                    results[t] = {
                        "status":  "HEALTHY" if available else "MODEL_MISSING",
                        "model":   cfg["model"],
                        "latency": f"{int((time.time()-t0)*1000)}ms",
                        "models_found": models[:5]
                    }

            elif cfg["type"] == "ollama":
                req = urllib.request.Request(
                    f"{cfg['host']}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read())
                    models = [m["name"] for m in data.get("models", [])]
                    available = any(cfg["model"].split(":")[0] in m
                                    for m in models)
                results[t] = {
                    "status":  "HEALTHY" if available else "MODEL_MISSING",
                    "model":   cfg["model"],
                    "latency": f"{int((time.time()-t0)*1000)}ms",
                    "models_found": models[:5]
                }

            elif cfg["type"] == "gemini":
                r = subprocess.run(
                    ["gemini", "-p", "say: health-check-ok"],
                    capture_output=True, text=True, timeout=30)
                results[t] = {
                    "status":  "HEALTHY" if r.returncode == 0 else "AUTH_NEEDED",
                    "model":   cfg["model"],
                    "latency": f"{int((time.time()-t0)*1000)}ms"
                }

            elif cfg["type"] == "huggingface":
                result_entry = {
                    "status":  "HEALTHY" if HF_ENABLED else "NO_API_KEY",
                    "model":   cfg["model"],
                    "latency": f"{int((time.time()-t0)*1000)}ms",
                }
                if not HF_ENABLED:
                    result_entry["note"] = "Set HF_API_KEY in environment — already in ~/.zshrc, add to MCP env config"
                results[t] = result_entry

            elif cfg["type"] == "claude":
                results[t] = {
                    "status":  "HEALTHY",
                    "model":   cfg["model"],
                    "latency": f"{int((time.time()-t0)*1000)}ms",
                    "note":    "EPIC-only — gated by t3_epic_gate"
                }

        except Exception as e:
            results[t] = {
                "status":  "UNHEALTHY",
                "model":   cfg["model"],
                "error":   str(e)[:100],
                "latency": f"{int((time.time()-t0)*1000)}ms"
            }

    healthy = sum(1 for v in results.values() if v["status"] == "HEALTHY")
    return {
        "summary":      f"{healthy}/{len(check_tiers)} tiers healthy",
        "langsmith":    "ACTIVE" if LANGSMITH_ENABLED else "NOT_CONFIGURED",
        "kimi_k2":      "ACTIVE" if HF_ENABLED else "NEEDS_HF_API_KEY",
        "tiers":        results,
        "fallback_chain": " → ".join(FALLBACK_CHAIN)
    }

# ══════════════════════════════════════════════════════════════════════
#  TOOL 9: tier_audit_log
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
def tier_audit_log(session_id: str = "current",
                   last_n: int = 20) -> dict:
    """
    STEP 5 — ALWAYS CALL LAST.
    Returns routing stats, tier usage breakdown,
    T3 fraud prevention count, quality score trends.
    """
    try:
        entries = []
        with open(LOG_PATH) as f:
            for line in f:
                try: entries.append(json.loads(line.strip()))
                except: pass
        entries = entries[-last_n:]

        decisions   = [e for e in entries if e.get("event") == "routing_decision"]
        t3_blocked  = [e for e in entries if e.get("event") == "T3_BLOCKED"]
        t3_approved = [e for e in entries if e.get("event") == "T3_APPROVED"]

        tier_counts = {}
        for e in entries:
            t = e.get("tier") or e.get("final_tier") or e.get("assigned_tier")
            if t: tier_counts[t] = tier_counts.get(t, 0) + 1

        scores = [e["quality"] for e in entries if "quality" in e]
        avg_q = sum(scores)/len(scores) if scores else 0

        return {
            "total_tasks":       len(decisions),
            "tier_distribution": tier_counts,
            "avg_quality_score": round(avg_q, 3),
            "t3_approved":       len(t3_approved),
            "t3_blocked":        len(t3_blocked),
            "subscription_saves": f"{len(t3_blocked)} T3 calls prevented",
            "langsmith_project":  os.environ.get("LANGCHAIN_PROJECT", "not set"),
            "log_path":           LOG_PATH,
            "recent_tasks":       [
                {"task": e.get("task_preview","")[:50],
                 "tier": e.get("tier","?"),
                 "quality": e.get("quality",0)}
                for e in entries[-5:]
            ]
        }
    except FileNotFoundError:
        return {"message": "No routing log yet — run some tasks first"}
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════════════════════════════════════
#  BANNER HELPERS — progress + execution banners for every task
# ══════════════════════════════════════════════════════════════════════

_TIER_META = {
    "T1-LOCAL": {"model": "qwen2.5-coder:7b",           "api": "localhost:11434/api/chat",   "icon": "🟢"},
    "T1-MID":   {"model": "qwen3-coder:30b",             "api": "localhost:11434/api/chat",   "icon": "🟡"},
    "T1-CLOUD": {"model": "qwen3-coder:480b-cloud",      "api": "localhost:11434/api/chat",   "icon": "🟠"},
    "T2-FLASH": {"model": "gemini-2.5-flash",            "api": "Gemini CLI / Google API",    "icon": "🔵"},
    "T2-PRO":   {"model": "gemini-2.5-pro",              "api": "Gemini CLI / Google API",    "icon": "🔷"},
    "T2-KIMI":  {"model": "Kimi-K2-Instruct",            "api": "HuggingFace API",            "icon": "🟣"},
    "T3":       {"model": "claude-sonnet-4-6",           "api": "Anthropic (Claude direct)",  "icon": "🔴"},
}
_W = 68  # banner inner width

def _brow(label: str, value: str) -> str:
    content = f"  {label:<13}: {value}"
    return f"║{content:<{_W - 2}}║"

def _btitle(text: str) -> str:
    content = f"  {text}"
    return f"║{content:<{_W - 2}}║"

def _make_banners(task: str, tier: str, complexity: str,
                  quality: float, fallback_count: int,
                  enforcement: str,
                  t3_blocked: bool = False,
                  t3_reason: str = "") -> dict:
    """Return progress_banner and execution_banner strings."""
    meta   = _TIER_META.get(tier, {"model": tier, "api": "unknown", "icon": "⚡"})
    model  = meta["model"]
    api    = meta["api"]
    icon   = meta["icon"]
    task_p = (task[:50] + "…") if len(task) > 51 else task
    sep    = "╠" + "═" * (_W - 2) + "╣"
    top    = "╔" + "═" * (_W - 2) + "╗"
    bot    = "╚" + "═" * (_W - 2) + "╝"

    # ── Progress banner (tier assigned, before execution) ─────────────
    progress_banner = "\n".join([
        top,
        _btitle(f"⚡ TIER ROUTING — TASK ASSIGNED"),
        sep,
        _brow("Task",       task_p),
        _brow("Complexity", complexity),
        _brow("Tier",       f"{icon}  {tier}"),
        _brow("Model",      model),
        _brow("API",        f"IN PROGRESS → {api}"),
        bot,
    ])

    # ── Execution banner (after execution) ────────────────────────────
    q_str = f"{quality:.2f} — {'PASS ✓' if quality >= 0.75 else f'FAIL ✗  (< 0.75)'}"
    fb_str = f"{fallback_count} escalation{'s' if fallback_count != 1 else ''}"

    if t3_blocked:
        execution_banner = "\n".join([
            top,
            _btitle(f"🚫  T3 BLOCKED — complexity: {complexity}"),
            sep,
            _brow("Reason",  "T3 is EPIC only — T3 gate returned BLOCKED"),
            _brow("Message", (t3_reason or "Not EPIC")[:48]),
            _brow("Use tier", f"{icon}  {tier} / {model}"),
            bot,
        ])
    else:
        execution_banner = "\n".join([
            top,
            _btitle(f"✅  TASK EXECUTED — {icon}  {tier}"),
            sep,
            _brow("Model",       model),
            _brow("Quality",     q_str),
            _brow("Fallbacks",   fb_str),
            _brow("Enforcement", enforcement),
            _brow("API",         f"YES → {api} ✓"),
            bot,
        ])

    return {"progress_banner": progress_banner, "execution_banner": execution_banner}

# ══════════════════════════════════════════════════════════════════════
#  TOOL 10: execute_task  — MASTER ENTRY POINT (LangGraph auto-invoke)
# ══════════════════════════════════════════════════════════════════════
@mcp.tool()
@traceable(name="EXECUTE-TASK-MASTER", run_type="chain",
           metadata={"role": "master-entry-point", "version": "5.1"})
def execute_task(task: str,
                 session_id: str = "default",
                 context: str = "") -> dict:
    """
    ╔══════════════════════════════════════════════════════════════╗
    ║  MASTER ENTRY POINT — CALL THIS FOR EVERY TASK              ║
    ║                                                              ║
    ║  Automatically runs the full LangGraph enforcement graph:   ║
    ║    classify → t3_gate → execute → quality_gate → audit      ║
    ║                                                              ║
    ║  LAYER 1 (OAuth startup auth) — NOT affected. Auth runs     ║
    ║  before MCP tools exist. This tool only activates after     ║
    ║  Claude CLI shell is open and tier-routing.md has loaded.   ║
    ║                                                              ║
    ║  LAYER 2 (task execution) — HARD ENFORCED via LangGraph.   ║
    ║  T3 is physically unreachable except:                       ║
    ║    • complexity == EPIC                                      ║
    ║    • full T1→T2 fallback chain exhausted                    ║
    ╚══════════════════════════════════════════════════════════════╝

    DO NOT call individual tier tools manually.
    DO NOT call bash/read/write before this tool.
    DO NOT attempt t3_epic_gate directly — it runs inside this graph.

    Only skip this tool for:
      • tier_health_check   (session start diagnostics)
      • check_budget        (budget queries)
      • /tier-* skills      (audit/debug/report)
    """
    # ── Step 1: Try LangGraph hard enforcement (preferred) ────────────
    try:
        import sys, os
        # Ensure langgraph_tier.py is importable from same directory
        _mcp_dir = os.path.dirname(os.path.abspath(__file__))
        if _mcp_dir not in sys.path:
            sys.path.insert(0, _mcp_dir)

        from langgraph_tier import run_tier_graph
        result = run_tier_graph(
            task=task,
            session_id=session_id,
            context=context
        )
        _tier      = result.get("assigned_tier", "T1-LOCAL")
        _complexity= result.get("complexity", "SIMPLE")
        _quality   = result.get("quality_score", 0.0)
        _fallbacks = result.get("fallback_count", 0)
        _t3_blocked= (not result.get("t3_approved", True) and _tier == "T3")
        _banners   = _make_banners(
            task=task, tier=_tier, complexity=_complexity,
            quality=_quality, fallback_count=_fallbacks,
            enforcement="LANGGRAPH_HARD",
            t3_blocked=_t3_blocked,
            t3_reason=result.get("t3_block_reason", ""),
        )
        return {
            "enforcement":      "LANGGRAPH_HARD",
            "tier":             _tier,
            "complexity":       _complexity,
            "quality_score":    _quality,
            "fallback_count":   _fallbacks,
            "t3_approved":      result.get("t3_approved", False),
            "t3_block_reason":  result.get("t3_block_reason", ""),
            "chain_exhausted":  result.get("chain_exhausted", False),
            "result":           result.get("result"),
            "error":            result.get("error"),
            "session_id":       session_id,
            "graph_nodes":      [e.get("node") for e in result.get("audit_log", [])],
            "progress_banner":  _banners["progress_banner"],
            "execution_banner": _banners["execution_banner"],
        }

    except ImportError as ie:
        # ── Step 2: LangGraph not installed — fallback to MCP soft chain ──
        _write_log({
            "event":   "LANGGRAPH_FALLBACK",
            "reason":  str(ie),
            "task":    task[:80],
            "note":    "Install langgraph: pip install langgraph --break-system-packages"
        })
        # Run soft chain: classify → execute → gate
        classification = tier_classify(task, context)
        tier       = classification.get("assigned_tier", "T1-LOCAL")
        next_tool  = classification.get("next_tool", "t1_local_execute")
        complexity = classification.get("complexity", "SIMPLE")

        # Hard block T3 via gate even in fallback mode
        if tier == "T3":
            gate = t3_epic_gate(task, complexity)
            if not gate.get("approved"):
                return {
                    "enforcement":  "MCP_SOFT_GATE_BLOCKED",
                    "tier":         "T3_BLOCKED",
                    "complexity":   complexity,
                    "gate_result":  gate,
                    "action":       gate.get("action"),
                    "correct_tool": gate.get("correct_tool"),
                    "warning":      "LangGraph not installed — install for hard enforcement"
                }

        # Execute at classified tier
        exec_map = {
            "t1_local_execute": lambda: t1_local_execute(task, context),
            "t1_mid_execute":   lambda: t1_mid_execute(task, context),
            "t1_cloud_execute": lambda: t1_cloud_execute(task, context),
            "t2_gemini_execute":lambda: t2_gemini_execute(task, context),
            "t2_kimi_execute":  lambda: t2_kimi_execute(task, context),
        }
        exec_fn  = exec_map.get(next_tool, exec_map["t1_local_execute"])
        exec_result = exec_fn()

        tier_audit_log(session_id=session_id)
        _q2       = exec_result.get("quality_score", 0.0)
        _banners2 = _make_banners(
            task=task, tier=tier, complexity=complexity,
            quality=_q2, fallback_count=0,
            enforcement="MCP_SOFT_CHAIN",
        )
        return {
            "enforcement":      "MCP_SOFT_CHAIN",
            "tier":             tier,
            "complexity":       complexity,
            "quality_score":    _q2,
            "result":           exec_result.get("result"),
            "status":           exec_result.get("status"),
            "warning":          (f"LangGraph not installed ({ie}). "
                                 f"Run: pip install langgraph --break-system-packages"),
            "progress_banner":  _banners2["progress_banner"],
            "execution_banner": _banners2["execution_banner"],
        }

    except Exception as e:
        _write_log({"event": "EXECUTE_TASK_ERROR", "error": str(e), "task": task[:80]})
        return {
            "enforcement": "ERROR",
            "error":       str(e),
            "fallback":    "Call tier_classify() then the appropriate tier tool manually"
        }


if __name__ == "__main__":
    mcp.run()

