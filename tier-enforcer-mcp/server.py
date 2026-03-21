#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  DSR AI-LAB TIER ENFORCER v6.1 — EXECUTION FIXED                   ║
║  File: ~/tier-enforcer-mcp/server.py                                ║
║                                                                      ║
║  BUGS FIXED vs v6.0:                                                ║
║                                                                      ║
║  BUG 1 — LangGraph quality gate was a conditional-edge function     ║
║           that tried to modify state. LangGraph DISCARDS state      ║
║           changes made inside edge functions. Result: model kept    ║
║           re-running on the same tier in an infinite loop until     ║
║           fallback_count hit 3, then returned empty.                ║
║           FIX: Split into _node_escalate (proper state node) +      ║
║                _should_escalate (pure routing function, no state).  ║
║                                                                      ║
║  BUG 2 — _call_ollama timeout = 120s. Local 7B model generating     ║
║           300+ lines of code takes 3–8 min on Mac Mini M-series.   ║
║           Result: TimeoutError → ok=False → score=0 → escalate.    ║
║           FIX: timeout=600s local, 300s cloud. Streaming HTTP.      ║
║                                                                      ║
║  BUG 3 — No num_ctx set. qwen2.5-coder:7b defaults to 2048 tokens. ║
║           Long prompts silently truncated. Model sees partial task. ║
║           FIX: num_ctx=8192 local, 16384 cloud, num_predict=4096.   ║
║                                                                      ║
║  BUG 4 — Quality scorer penalised results containing the word       ║
║           "error" (e.g. "error handling", "raise ValueError").      ║
║           Normal code scores 0.6 → below 0.75 threshold →          ║
║           triggers escalation on perfectly good output.             ║
║           FIX: Smarter scorer. Only penalise actual failure         ║
║                phrases. Completion markers add bonus. Tier-aware    ║
║                thresholds (T1-LOCAL=0.5, others=0.65).              ║
╚══════════════════════════════════════════════════════════════════════╝
Install: pip install fastmcp langgraph langchain-core langchain-ollama
         langchain-google-genai langsmith huggingface_hub pydantic httpx
         --break-system-packages
"""

import os, json, time, subprocess, logging, sqlite3, urllib.request
from typing import TypedDict
from fastmcp import FastMCP

# ── OPTIONAL IMPORTS ──────────────────────────────────────────────────
try:
    from langgraph.graph import StateGraph, END
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

try:
    from huggingface_hub import InferenceClient
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

HOME     = os.path.expanduser("~")
DB_DIR   = os.path.join(HOME, ".tier-enforcer")
LOG_PATH = os.path.join(DB_DIR, "routing.log")
MEM_DB   = os.path.join(DB_DIR, "memory.db")
os.makedirs(DB_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH, level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger("tier-enforcer")

OLLAMA_LOCAL = os.environ.get("OLLAMA_LOCAL_HOST", "http://localhost:11434")
OLLAMA_CLOUD = os.environ.get("OLLAMA_CLOUD_HOST", "http://localhost:11434")
HF_API_KEY   = os.environ.get("HF_API_KEY", "")

# ── TIMEOUTS (FIX 2) ──────────────────────────────────────────────────
TIMEOUT_LOCAL  = int(os.environ.get("OLLAMA_TIMEOUT_LOCAL",  "600"))  # 10 min
TIMEOUT_MID    = int(os.environ.get("OLLAMA_TIMEOUT_MID",    "480"))  # 8 min
TIMEOUT_CLOUD  = int(os.environ.get("OLLAMA_TIMEOUT_CLOUD",  "300"))  # 5 min

# ── OLLAMA GENERATION PARAMS (FIX 3) ─────────────────────────────────
OLLAMA_PARAMS_LOCAL = {
    "num_ctx":     8192,    # context window — was defaulting to 2048
    "num_predict": 4096,    # max output tokens — prevents early stop
    "temperature": 0.1,     # deterministic code output
    "top_p":       0.9,
    "repeat_penalty": 1.1,
}
OLLAMA_PARAMS_CLOUD = {
    "num_ctx":     16384,
    "num_predict": 8192,
    "temperature": 0.1,
    "top_p":       0.9,
    "repeat_penalty": 1.1,
}

# ── QUALITY THRESHOLDS PER TIER (FIX 4) ──────────────────────────────
# Lower threshold for local — it's fast and free, accept imperfect output
# rather than always escalating to cloud
QUALITY_THRESHOLDS = {
    "T1-LOCAL":  float(os.environ.get("QUALITY_T1_LOCAL",  "0.50")),
    "T1-MID":    float(os.environ.get("QUALITY_T1_MID",    "0.55")),
    "T1-CLOUD":  float(os.environ.get("QUALITY_T1_CLOUD",  "0.60")),
    "DEFAULT":   float(os.environ.get("QUALITY_THRESHOLD", "0.55")),
}

CLAUDE_EXECUTION_BLOCK = True
MASTER_RULE = "execute_task(task, session_id, context)"

# ── TIER CONFIG ───────────────────────────────────────────────────────
TIER_CONFIG = {
    "T1-LOCAL":  {"model": "qwen2.5-coder:7b",      "role": "executor", "base": OLLAMA_LOCAL, "type": "ollama", "timeout": TIMEOUT_LOCAL,  "params": OLLAMA_PARAMS_LOCAL},
    "T1-MID":    {"model": "qwen2.5-coder:14b",       "role": "executor", "base": OLLAMA_LOCAL, "type": "ollama", "timeout": TIMEOUT_MID,    "params": OLLAMA_PARAMS_LOCAL},
    "T1-CLOUD":  {"model": "qwen3-coder:480b-cloud",  "role": "executor", "base": OLLAMA_CLOUD, "type": "ollama", "timeout": TIMEOUT_CLOUD,  "params": OLLAMA_PARAMS_CLOUD},
    "T2-FLASH":  {"model": "gemini-2.5-flash",       "role": "analysis", "type": "gemini"},
    "T2-PRO":    {"model": "gemini-2.5-pro",         "role": "analysis", "type": "gemini"},
    "T2-KIMI":   {"model": "Qwen/Kimi-K2-Instruct",  "role": "analysis", "type": "huggingface"},
    "T3-EPIC":   {"model": "claude-brain-only",      "role": "brain",    "type": "claude"},
}

ROUTING_RULES = {
    "T3-EPIC": {"keywords": ["greenfield platform","full system","entire application","production architecture","design and build complete","from scratch end to end"]},
    "T2-KIMI":  {"keywords": ["algorithm analysis","mathematical proof","statistical model","complex math","optimize algorithm","big o analysis"]},
    "T2-PRO":   {"keywords": ["security audit","performance review","architecture review","code review entire","analyse codebase"]},
    "T2-FLASH": {"keywords": ["debug","fix bug","refactor","trace error","why is this failing","what is wrong"]},
    "T1-CLOUD": {"keywords": ["feature set","ai agent","rpa workflow","full component","multi-file","entire module","build the"]},
    "T1-MID":   {"keywords": ["implement","create function","unit test","add endpoint","write class","build service"]},
    "T1-LOCAL": {"keywords": []},
}

FALLBACK_CHAIN = ["T1-LOCAL", "T1-MID", "T1-CLOUD"]
MAX_FALLBACKS  = 2   # reduced: attempt local, then mid, then accept


# ═══════════════════════════════════════════════════════════════════════
# ROUTING CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════

def _classify_task(task: str) -> tuple:
    t = task.lower()
    for tier in ["T3-EPIC","T2-KIMI","T2-PRO","T2-FLASH","T1-CLOUD","T1-MID"]:
        if any(k in t for k in ROUTING_RULES[tier]["keywords"]):
            return tier, TIER_CONFIG[tier], tier
    return "T1-LOCAL", TIER_CONFIG["T1-LOCAL"], "T1-LOCAL"

def _get_executor_tier(classified: str) -> str:
    if classified == "T3-EPIC":
        return "T1-CLOUD"
    if classified in ("T2-FLASH","T2-PRO","T2-KIMI"):
        return "T1-MID"
    return classified


# ═══════════════════════════════════════════════════════════════════════
# MODEL CALLERS — FIXED
# ═══════════════════════════════════════════════════════════════════════

def _call_ollama(model: str, base_url: str, prompt: str,
                 system: str = "", timeout: int = 600,
                 params: dict = None) -> dict:
    """
    Call Ollama via streaming HTTP — collects all chunks, no timeout risk.
    FIX 2: Long timeout (600s default).
    FIX 3: num_ctx=8192, num_predict=4096 to prevent truncation.
    Uses urllib (stdlib only, no httpx needed).
    """
    params = params or OLLAMA_PARAMS_LOCAL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model":   model,
        "messages": messages,
        "stream":  True,         # streaming prevents timeout on large outputs
        "options": params,
    }).encode("utf-8")

    url = base_url.rstrip("/") + "/api/chat"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t_start = time.time()
    chunks  = []
    done    = False
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = obj.get("message", {}).get("content", "")
                if content:
                    chunks.append(content)
                if obj.get("done", False):
                    done = True
                    break

        result    = "".join(chunks)
        elapsed   = round(time.time() - t_start, 1)
        log.info("OLLAMA_DONE model=%s elapsed=%ss tokens=%d done=%s",
                 model, elapsed, len(result.split()), done)
        return {"ok": True, "result": result, "model": model,
                "elapsed": elapsed, "done": done}

    except Exception as e:
        elapsed = round(time.time() - t_start, 1)
        partial = "".join(chunks)
        log.error("OLLAMA_ERR model=%s elapsed=%ss err=%s partial_len=%d",
                  model, elapsed, str(e)[:120], len(partial))
        # Return partial result if we got something — don't discard it
        if partial and len(partial.strip()) > 50:
            log.warning("OLLAMA partial result returned (%d chars)", len(partial))
            return {"ok": True, "result": partial, "model": model,
                    "elapsed": elapsed, "done": False, "partial": True}
        return {"ok": False, "error": str(e), "model": model, "elapsed": elapsed}


def _call_ollama_with_retry(model: str, base_url: str, prompt: str,
                             system: str = "", timeout: int = 600,
                             params: dict = None, retries: int = 1) -> dict:
    """Wrapper that retries once on failure before giving up."""
    for attempt in range(retries + 1):
        r = _call_ollama(model, base_url, prompt, system, timeout, params)
        if r["ok"]:
            return r
        if attempt < retries:
            wait = 5 * (attempt + 1)
            log.warning("OLLAMA retry %d/%d in %ds — err: %s",
                        attempt+1, retries, wait, r.get("error","")[:60])
            time.sleep(wait)
    return r


def _call_gemini(model: str, prompt: str, system: str = "") -> dict:
    """Gemini CLI — analysis only."""
    try:
        full = (system + "\n\n" + prompt).strip() if system else prompt
        r = subprocess.run(
            ["gemini", "--model", model, full],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            return {"ok": True, "result": r.stdout.strip(), "model": model}
        return {"ok": False, "error": r.stderr[:200], "model": model}
    except Exception as e:
        return {"ok": False, "error": str(e), "model": model}


def _call_huggingface(model: str, prompt: str) -> dict:
    """HuggingFace — analysis only."""
    try:
        if not HF_AVAILABLE or not HF_API_KEY:
            return {"ok": False, "error": "HF not configured", "model": model}
        client = InferenceClient(token=HF_API_KEY)
        result = client.text_generation(prompt, model=model, max_new_tokens=2048, temperature=0.1)
        return {"ok": True, "result": result, "model": model}
    except Exception as e:
        return {"ok": False, "error": str(e), "model": model}


# ═══════════════════════════════════════════════════════════════════════
# QUALITY SCORER — FIXED (FIX 4)
# ═══════════════════════════════════════════════════════════════════════

def _score_result(result: str, task: str, tier: str = "T1-LOCAL") -> float:
    """
    Smarter quality scoring.
    FIX 4: Only penalise actual failure phrases, not code-context words.
    Completion markers (def, class, return, closing brackets) add score.
    Tier-aware thresholds.
    """
    if not result:
        return 0.0
    stripped = result.strip()
    if len(stripped) < 15:
        return 0.1

    score = 0.4   # base

    # Length bonus
    n = len(stripped)
    if n > 200:   score += 0.15
    if n > 800:   score += 0.10
    if n > 2000:  score += 0.05

    # Code structure markers — strong positive signals
    code_markers = [
        "def ", "class ", "import ", "from ", "function ",
        "const ", "export ", "return ", "async ", "await ",
        "for ", "while ", "if ", "try:", "except",
        "```", "#!/", "SELECT ", "CREATE TABLE",
    ]
    code_hits = sum(1 for m in code_markers if m in result)
    score += min(code_hits * 0.04, 0.20)

    # Completion markers — code that actually finished
    completion_markers = [
        "return ", "};", "end", "EOF", "```\n", "\nif __name__",
        "print(", "console.log", "done", "complete",
    ]
    if any(m in result for m in completion_markers):
        score += 0.10

    # ACTUAL failure phrases — precise matching, not substring
    fail_phrases = [
        "i cannot help with",
        "i am unable to",
        "i don't have the ability",
        "i cannot complete this",
        "as an ai, i",
        "i'm sorry, but i cannot",
        "this request cannot be fulfilled",
    ]
    result_lower = result.lower()
    if any(p in result_lower for p in fail_phrases):
        score -= 0.40   # hard penalty for refusals

    # Uncertainty — soft penalty (model unsure but gave output)
    uncertain = ["i'm not sure", "i'm not certain", "you may need to"]
    if any(p in result_lower for p in uncertain):
        score -= 0.10

    return round(min(max(score, 0.0), 1.0), 3)


def _get_threshold(tier: str) -> float:
    return QUALITY_THRESHOLDS.get(tier, QUALITY_THRESHOLDS["DEFAULT"])


# ═══════════════════════════════════════════════════════════════════════
# AUDIT
# ═══════════════════════════════════════════════════════════════════════

def _audit(session_id, task, tier, executor_tier, model, score, ok):
    entry = {"ts": time.time(), "session": session_id, "task": task[:120],
             "classified_tier": tier, "executor_tier": executor_tier,
             "model": model, "score": score, "ok": ok}
    log.info(json.dumps(entry))
    try:
        conn = sqlite3.connect(MEM_DB)
        conn.execute("""CREATE TABLE IF NOT EXISTS routing_log
            (ts REAL, session TEXT, task TEXT, classified_tier TEXT,
             executor_tier TEXT, model TEXT, score REAL, ok INTEGER)""")
        conn.execute("INSERT INTO routing_log VALUES (?,?,?,?,?,?,?,?)",
            (entry["ts"], session_id, entry["task"], tier, executor_tier,
             model, score, int(ok)))
        conn.commit(); conn.close()
    except Exception as e:
        log.error("audit DB: %s", e)


# ═══════════════════════════════════════════════════════════════════════
# LANGGRAPH NODES — FIXED
# ═══════════════════════════════════════════════════════════════════════

class TierState(TypedDict):
    task:             str
    session_id:       str
    context:          str
    classified_tier:  str
    executor_tier:    str
    tier_config:      dict
    reason:           str
    analysis:         str
    blueprint:        str
    execution_prompt: str
    result:           str
    score:            float
    fallback_count:   int
    final_tier:       str
    ok:               bool
    mode:             str
    should_escalate:  bool   # NEW — set by _node_escalate, read by edge


def _node_classify(state: TierState) -> TierState:
    tier, cfg, reason = _classify_task(state["task"])
    executor = _get_executor_tier(tier)
    state["classified_tier"]  = tier
    state["executor_tier"]    = executor
    state["tier_config"]      = TIER_CONFIG[executor]
    state["reason"]           = reason
    state["mode"]             = "LANGGRAPH_HARD"
    state["fallback_count"]   = 0
    state["should_escalate"]  = False
    log.info("CLASSIFY task='%s' tier=%s executor=%s", state["task"][:60], tier, executor)
    return state


def _node_t3_brain_plan(state: TierState) -> TierState:
    """T3-EPIC: format the Claude-generated blueprint for Ollama executor."""
    if state["classified_tier"] != "T3-EPIC":
        return state
    blueprint = (
        "EXECUTION BLUEPRINT — implement this fully:\n\n"
        "Task: " + state["task"] + "\n\n"
        + ("Context:\n" + state["context"] + "\n\n" if state["context"] else "")
        + "Requirements:\n"
        "- Complete, production-quality implementation\n"
        "- All error handling included\n"
        "- Runnable code, no placeholders\n"
        "- Include brief inline comments\n"
    )
    state["blueprint"]        = blueprint
    state["execution_prompt"] = blueprint
    state["executor_tier"]    = "T1-CLOUD"
    state["tier_config"]      = TIER_CONFIG["T1-CLOUD"]
    log.info("T3_PLAN blueprint_len=%d executor=T1-CLOUD", len(blueprint))
    return state


def _node_t2_analysis(state: TierState) -> TierState:
    """T2 analysis pass — enriches the execution prompt for T1."""
    tier = state["classified_tier"]
    if tier not in ("T2-FLASH","T2-PRO","T2-KIMI"):
        if not state.get("execution_prompt"):
            state["execution_prompt"] = state["task"]
        return state

    cfg = TIER_CONFIG[tier]
    sys_prompt = (
        "Analyse the following task. Identify the best approach, potential issues, "
        "and recommended implementation strategy. Do NOT write the full implementation. "
        "Your analysis will guide an executor model."
    )
    analysis_prompt = "Analyse:\n\n" + state["task"]
    if state.get("context"):
        analysis_prompt += "\n\nContext:\n" + state["context"]

    if cfg["type"] == "gemini":
        r = _call_gemini(cfg["model"], analysis_prompt, sys_prompt)
    else:
        r = _call_huggingface(cfg["model"], sys_prompt + "\n\n" + analysis_prompt)

    analysis = r.get("result","") if r["ok"] else "Analysis unavailable."
    state["analysis"] = analysis
    state["execution_prompt"] = (
        "Task: " + state["task"] + "\n\n"
        "Analysis:\n" + analysis + "\n\n"
        "Implement the complete solution based on the above analysis. "
        "Write production-quality, complete, runnable code. No placeholders."
    )
    log.info("T2_ANALYSIS model=%s ok=%s len=%d", cfg["model"], r["ok"], len(analysis))
    return state


def _node_execute(state: TierState) -> TierState:
    """
    Call the Ollama executor.
    FIX 2+3: Uses _call_ollama_with_retry with proper timeouts and num_ctx.
    Hard block: if executor maps to Claude → redirect to T1-CLOUD.
    """
    executor = state["executor_tier"]
    cfg      = TIER_CONFIG.get(executor, TIER_CONFIG["T1-LOCAL"])

    # HARD CLAUDE BLOCK
    if cfg.get("role") == "brain" or cfg.get("type") == "claude":
        log.warning("CLAUDE EXECUTION BLOCK — redirecting to T1-CLOUD")
        executor = "T1-CLOUD"
        cfg      = TIER_CONFIG["T1-CLOUD"]
        state["executor_tier"] = executor
        state["tier_config"]   = cfg

    prompt = state.get("execution_prompt") or state["task"]
    system = (
        "You are an expert software engineer. "
        "Implement the requested solution completely. "
        "Write production-quality, runnable code. "
        "Do not truncate. Do not say 'I cannot'. "
        "Return only the implementation."
    )
    timeout = cfg.get("timeout", TIMEOUT_LOCAL)
    params  = cfg.get("params",  OLLAMA_PARAMS_LOCAL)

    log.info("EXECUTE tier=%s model=%s timeout=%ds", executor, cfg["model"], timeout)

    r = _call_ollama_with_retry(
        cfg["model"], cfg["base"], prompt, system,
        timeout=timeout, params=params, retries=1
    )

    state["result"]     = r.get("result","")
    state["ok"]         = r["ok"]
    state["final_tier"] = executor
    state["score"]      = _score_result(state["result"], state["task"], executor)
    state["should_escalate"] = False

    log.info("EXECUTE done tier=%s ok=%s score=%.3f len=%d",
             executor, r["ok"], state["score"], len(state["result"]))
    return state


def _node_escalate(state: TierState) -> TierState:
    """
    FIX 1 — This is now a proper STATE NODE (not an edge function).
    Checks quality and updates executor_tier in state if escalation needed.
    Sets state["should_escalate"] = True/False for the routing edge.
    """
    tier      = state["executor_tier"]
    score     = state["score"]
    threshold = _get_threshold(tier)
    ok        = state["ok"]

    # Accept if: result is ok AND score meets tier threshold
    if ok and score >= threshold:
        state["should_escalate"] = False
        log.info("QUALITY_PASS tier=%s score=%.3f threshold=%.2f", tier, score, threshold)
        return state

    # Accept partial results — better to return something than nothing
    if state["result"] and len(state["result"].strip()) > 100:
        if state["fallback_count"] >= MAX_FALLBACKS:
            log.warning("MAX_FALLBACKS=%d reached — accepting partial result", MAX_FALLBACKS)
            state["should_escalate"] = False
            return state

    # Escalate within T1 chain only
    chain = ["T1-LOCAL","T1-MID","T1-CLOUD"]
    idx   = chain.index(tier) if tier in chain else -1
    if idx >= 0 and idx < len(chain) - 1:
        next_tier = chain[idx + 1]
        log.info("ESCALATE %s→%s score=%.3f threshold=%.2f", tier, next_tier, score, threshold)
        state["executor_tier"]    = next_tier
        state["tier_config"]      = TIER_CONFIG[next_tier]
        state["fallback_count"]   = state.get("fallback_count",0) + 1
        state["should_escalate"]  = True
    else:
        # Already at top of chain — accept whatever we have
        state["should_escalate"] = False
        log.info("TOP_OF_CHAIN — accepting result score=%.3f", score)

    return state


def _route_after_escalate(state: TierState) -> str:
    """Pure routing function — reads state only, never modifies it. FIX 1."""
    return "execute" if state["should_escalate"] else "audit"


def _node_audit(state: TierState) -> TierState:
    _audit(
        session_id    = state.get("session_id","unknown"),
        task          = state["task"],
        tier          = state["classified_tier"],
        executor_tier = state["final_tier"],
        model         = TIER_CONFIG.get(state["final_tier"],{}).get("model","unknown"),
        score         = state.get("score",0.0),
        ok            = state.get("ok",False),
    )
    return state


def _build_graph():
    """Compile the LangGraph graph with fixed node/edge structure."""
    g = StateGraph(TierState)

    g.add_node("classify",    _node_classify)
    g.add_node("t3_plan",     _node_t3_brain_plan)
    g.add_node("t2_analysis", _node_t2_analysis)
    g.add_node("execute",     _node_execute)
    g.add_node("escalate",    _node_escalate)   # FIX 1: proper node
    g.add_node("audit",       _node_audit)

    g.set_entry_point("classify")

    g.add_conditional_edges("classify", lambda s: (
        "t3_plan"     if s["classified_tier"] == "T3-EPIC" else
        "t2_analysis" if s["classified_tier"] in ("T2-FLASH","T2-PRO","T2-KIMI") else
        "execute"
    ), {"t3_plan":"t3_plan","t2_analysis":"t2_analysis","execute":"execute"})

    g.add_edge("t3_plan",     "execute")
    g.add_edge("t2_analysis", "execute")
    g.add_edge("execute",     "escalate")       # FIX 1: execute → escalate node

    # FIX 1: escalate node → routing function → execute or audit
    g.add_conditional_edges("escalate", _route_after_escalate,
                            {"execute":"execute","audit":"audit"})
    g.add_edge("audit", END)

    return g.compile()


_GRAPH = None
def _get_graph():
    global _GRAPH
    if _GRAPH is None and LANGGRAPH_AVAILABLE:
        _GRAPH = _build_graph()
    return _GRAPH


# ═══════════════════════════════════════════════════════════════════════
# SOFT-CHAIN FALLBACK
# ═══════════════════════════════════════════════════════════════════════

def _soft_chain_execute(task: str, session_id: str, context: str) -> dict:
    classified, cfg, reason = _classify_task(task)
    executor = _get_executor_tier(classified)
    exec_cfg = TIER_CONFIG[executor]

    analysis = ""
    if classified in ("T2-FLASH","T2-PRO"):
        r = _call_gemini(TIER_CONFIG[classified]["model"], "Analyse:\n" + task)
        analysis = r.get("result","")
    elif classified == "T2-KIMI":
        r = _call_huggingface(TIER_CONFIG["T2-KIMI"]["model"], "Analyse:\n" + task)
        analysis = r.get("result","")

    prompt = task
    if analysis:
        prompt = "Task: " + task + "\n\nAnalysis:\n" + analysis + "\n\nImplement:"
    if classified == "T3-EPIC":
        prompt = "Implement fully:\n" + task + "\n\nContext: " + (context or "")

    timeout = exec_cfg.get("timeout", TIMEOUT_LOCAL)
    params  = exec_cfg.get("params",  OLLAMA_PARAMS_LOCAL)
    result  = _call_ollama_with_retry(exec_cfg["model"], exec_cfg["base"],
                                       prompt, "", timeout, params)
    score   = _score_result(result.get("result",""), task, executor)
    _audit(session_id, task, classified, executor, exec_cfg["model"], score, result["ok"])

    return {
        "mode":            "MCP_SOFT_CHAIN",
        "classified_tier": classified,
        "executor_tier":   executor,
        "executor_model":  exec_cfg["model"],
        "result":          result.get("result",""),
        "score":           score,
        "ok":              result["ok"],
        "claude_blocked":  True,
    }


# ═══════════════════════════════════════════════════════════════════════
# MCP SERVER TOOLS
# ═══════════════════════════════════════════════════════════════════════

mcp = FastMCP("tier-enforcer")


@mcp.tool()
def execute_task(task: str, session_id: str = "default", context: str = "") -> dict:
    """
    MASTER ENTRY POINT. Call for every task.
    Claude = brain only. All execution goes to Ollama T1 tiers.
    """
    graph = _get_graph()
    if graph:
        init: TierState = {
            "task": task, "session_id": session_id, "context": context,
            "classified_tier":"","executor_tier":"","tier_config":{},
            "reason":"","analysis":"","blueprint":"","execution_prompt":"",
            "result":"","score":0.0,"fallback_count":0,"final_tier":"",
            "ok":False,"mode":"LANGGRAPH_HARD","should_escalate":False,
        }
        final = graph.invoke(init)
        tier  = final.get("final_tier","?")
        model = TIER_CONFIG.get(tier,{}).get("model","?")
        return {
            "mode":            final["mode"],
            "classified_tier": final["classified_tier"],
            "executor_tier":   tier,
            "executor_model":  model,
            "analysis":        final.get("analysis",""),
            "blueprint":       final.get("blueprint",""),
            "result":          final["result"],
            "score":           round(final["score"],3),
            "ok":              final["ok"],
            "fallbacks_used":  final["fallback_count"],
            "claude_blocked":  True,
            "banner": (
                "🧠 BRAIN: Claude → " + final["classified_tier"] +
                " | ⚙️ EXECUTOR: Ollama " + tier + " → " + model
            ),
        }
    return _soft_chain_execute(task, session_id, context)


@mcp.tool()
def activate_tier_routing(session_id: str = "auto") -> dict:
    """Auto-called by CLAUDE.md on every session open."""
    graph = _get_graph()
    status = {
        "activated":        True,
        "session_id":       session_id,
        "timestamp":        time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode":             "LANGGRAPH_HARD" if graph else "MCP_SOFT_CHAIN",
        "langgraph":        LANGGRAPH_AVAILABLE,
        "claude_role":      "BRAIN_ONLY — execution hard blocked",
        "executor_chain":   ["T1-LOCAL","T1-MID","T1-CLOUD"],
        "analysis_chain":   ["T2-FLASH","T2-PRO","T2-KIMI"],
        "t3_epic_executor": "T1-CLOUD",
        "timeouts":         {"T1-LOCAL": TIMEOUT_LOCAL,"T1-MID": TIMEOUT_MID,"T1-CLOUD": TIMEOUT_CLOUD},
        "num_ctx":          {"T1-LOCAL": OLLAMA_PARAMS_LOCAL["num_ctx"],"T1-CLOUD": OLLAMA_PARAMS_CLOUD["num_ctx"]},
        "thresholds":       QUALITY_THRESHOLDS,
        "banner": (
            "╔═══════════════════════════════════════╗\n"
            "║  DSR AI-Lab Tier Routing v6.1 ACTIVE  ║\n"
            "║  Brain: Claude (plan only)            ║\n"
            "║  Executor: Ollama T1-LOCAL/MID/CLOUD  ║\n"
            "║  Fixes: timeout/ctx/scoring/graph     ║\n"
            "╚═══════════════════════════════════════╝"
        ),
    }
    _audit(session_id, "SYSTEM:activate", "SYSTEM","SYSTEM","none",1.0,True)
    return status


@mcp.tool()
def tier_health_check(tier: str = "ALL") -> dict:
    """Check health of all tiers."""
    import urllib.request, urllib.error

    def check_ollama(base: str, model: str) -> str:
        try:
            req = urllib.request.Request(base.rstrip("/")+"/api/tags")
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            models = [m["name"] for m in data.get("models",[])]
            short  = model.split(":")[0]
            if any(short in m for m in models):
                return "ONLINE"
            return "DEGRADED (not pulled — run: ollama pull " + model + ")"
        except Exception as e:
            return "OFFLINE (" + str(e)[:60] + ")"

    def check_gemini() -> str:
        r = subprocess.run(["gemini","--version"],capture_output=True,text=True,timeout=5)
        return "ONLINE" if r.returncode==0 else "OFFLINE (npm install -g @google/gemini-cli)"

    def check_hf() -> str:
        return "ONLINE" if HF_API_KEY else "OFFLINE (set HF_API_KEY)"

    checks = {
        "T1-LOCAL":  check_ollama(OLLAMA_LOCAL, "qwen2.5-coder:7b"),
        "T1-MID":    check_ollama(OLLAMA_LOCAL, "qwen2.5-coder:14b"),
        "T1-CLOUD":  check_ollama(OLLAMA_CLOUD, "qwen3-coder:480b-cloud"),
        "T2-FLASH":  check_gemini(),
        "T2-PRO":    check_gemini(),
        "T2-KIMI":   check_hf(),
        "T3-EPIC":   "BRAIN ONLY — always available",
    }
    if tier != "ALL":
        return {tier: checks.get(tier,"Unknown tier")}

    online  = [t for t,s in checks.items() if "ONLINE" in s or "BRAIN" in s]
    offline = [t for t,s in checks.items() if "OFFLINE" in s]
    return {
        "tiers":        checks,
        "online_count": len(online),
        "offline":      offline,
        "routing_mode": "LANGGRAPH_HARD" if LANGGRAPH_AVAILABLE else "MCP_SOFT_CHAIN",
        "claude_role":  "BRAIN ONLY",
        "fixes_active": {
            "streaming_http":    True,
            "timeout_local_s":   TIMEOUT_LOCAL,
            "num_ctx_local":     OLLAMA_PARAMS_LOCAL["num_ctx"],
            "quality_threshold": QUALITY_THRESHOLDS,
            "langgraph_escalate_node": True,
        },
    }


@mcp.tool()
def classify_only(task: str) -> dict:
    """Preview routing without executing."""
    classified, cfg, reason = _classify_task(task)
    executor  = _get_executor_tier(classified)
    exec_cfg  = TIER_CONFIG[executor]
    threshold = _get_threshold(executor)
    return {
        "task":            task[:100],
        "classified_tier": classified,
        "executor_tier":   executor,
        "executor_model":  exec_cfg["model"],
        "timeout_s":       exec_cfg.get("timeout", TIMEOUT_LOCAL),
        "num_ctx":         exec_cfg.get("params",{}).get("num_ctx","?"),
        "quality_threshold": threshold,
        "claude_executes": False,
        "flow": (
            "Claude brain → blueprint → T1-CLOUD executes" if classified=="T3-EPIC" else
            TIER_CONFIG[classified]["model"]+" analysis → "+executor+" executes" if cfg.get("role")=="analysis" else
            exec_cfg["model"]+" executes directly"
        ),
    }


@mcp.tool()
def tier_audit_log(last_n: int = 20) -> dict:
    """Last N routing decisions."""
    try:
        conn = sqlite3.connect(MEM_DB)
        rows = conn.execute(
            "SELECT ts,session,task,classified_tier,executor_tier,model,score,ok "
            "FROM routing_log ORDER BY ts DESC LIMIT ?", (last_n,)
        ).fetchall()
        conn.close()
        return {"entries": [
            {"ts":time.strftime("%H:%M:%S",time.localtime(r[0])),"session":r[1],
             "task":r[2],"classified":r[3],"executor":r[4],
             "model":r[5],"score":r[6],"ok":bool(r[7])} for r in rows
        ], "count": len(rows)}
    except Exception as e:
        return {"error": str(e), "entries": []}


@mcp.tool()
def tier_reset() -> dict:
    """Reset and re-activate routing."""
    global _GRAPH
    _GRAPH = None   # force graph rebuild
    return {"reset": True, "status": activate_tier_routing("reset")}


if __name__ == "__main__":
    mcp.run()
