#!/usr/bin/env python3
"""
tier-enforcer-mcp  Physical Routing Gate for Claude CLI
T1=Ollama, T2=Gemini CLI (Google auth), T3=Claude (gated EPIC only)
"""
import json, os, subprocess, time, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from fastmcp import FastMCP

OLLAMA_LOCAL   = os.getenv("OLLAMA_LOCAL_HOST",  "http://localhost:11434")
OLLAMA_CLOUD   = os.getenv("OLLAMA_CLOUD_HOST",  "")
T1_LOCAL_MODEL = "qwen2.5-coder:7b"
T1_CLOUD_MODEL = "qwen3-coder:480b"
QUALITY_GATE   = float(os.getenv("QUALITY_THRESHOLD", "0.75"))
LOG_PATH       = Path(os.getenv("TIER_LOG", os.path.expanduser("~/.tier-enforcer/routing.log")))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("tier-enforcer", instructions="""
MANDATORY WORKFLOW for every task — no exceptions:
1. Call tier_classify  → get complexity + assigned_tier
2. Call matching tool: t1_local_execute / t1_cloud_execute / t2_gemini_execute
3. EPIC only: call t3_epic_gate (returns BLOCKED for non-EPIC)
4. Call tier_audit_log to record result
NEVER self-generate for SIMPLE/MODERATE. NEVER skip tier_classify.
""")

def _log(e):
    e["ts"] = datetime.utcnow().isoformat()
    with open(LOG_PATH, "a") as f: f.write(json.dumps(e)+"\n")

def _score(text):
    s = 1.0
    for p in ["TODO","FIXME","pass","...","not implemented","placeholder"]:
        if p.lower() in text.lower(): s -= 0.2
    if len(text) < 50: s -= 0.5
    return max(0.0, min(1.0, round(s, 2)))

def _ollama(base, model, prompt, context, temp, timeout):
    sys = "Elite coder. ONLY complete working code. No placeholders. No TODOs."
    if context: sys += f"\n\nCONTEXT:\n{context}"
    payload = json.dumps({"model":model,"stream":False,
        "options":{"temperature":temp,"num_ctx":131072,"seed":42},
        "messages":[{"role":"system","content":sys},{"role":"user","content":prompt}]
    }).encode()
    req = urllib.request.Request(f"{base}/api/chat", data=payload,
          headers={"Content-Type":"application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
            return {"content":d["message"]["content"],"model":d.get("model",model),
                    "tokens_out":d.get("eval_count",0),
                    "latency_ms":int((time.time()-t0)*1000),"endpoint":f"{base}/api/chat"}
    except urllib.error.URLError as e:
        raise ConnectionError(f"Ollama unreachable at {base}. Run: ollama serve && ollama pull {model}\n{e}")

def _gemini(prompt, context, model, timeout):
    full = f"CONTEXT:\n{context}\n\nTASK:\n{prompt}" if context else prompt
    t0   = time.time()
    try:
        r = subprocess.run(["gemini","-m",model,"-p",full],
            capture_output=True, text=True, timeout=timeout, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"Gemini CLI error: {r.stderr.strip()}\nFix: gemini auth login")
        return {"content":r.stdout.strip(),"model":model,
                "latency_ms":int((time.time()-t0)*1000),"endpoint":f"gemini-cli:{model}"}
    except FileNotFoundError:
        raise RuntimeError("gemini CLI not found. Install + auth: gemini auth login")
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Gemini CLI timeout after {timeout}s")


@mcp.tool(description="""REQUIRED STEP 1. Classify complexity, return assigned tier + next tool to call.
Call BEFORE any execution tool. Returns: complexity, task_type, assigned_tier, model, next_tool.""")
def tier_classify(prompt: str, context: str = "") -> dict:
    text = (prompt+" "+context).lower()
    ctx_lines = context.count("\n")

    SIMPLE_KW   = ["fix","add","docstring","comment","format","rename","unit test",
                   "config","dockerfile","ls","cat","git log","git status","git diff",
                   "grep","find","connect to","explore","navigate","read file",
                   "show file","single function","quick","small","type hint","lint"]
    MODERATE_KW = ["integrate","refactor","feature","schema","api endpoint","component",
                   "auth","crud","middleware","service","module","multi-file",
                   "pagination","validation","getusermedia","permission wiring",
                   "entitlements","ipc","electron","authentication"]
    COMPLEX_KW  = ["analytics","algorithm","optimize","security","statistical",
                   "machine learning","performance","distributed","encryption",
                   "forecasting","regression","ml pipeline","deep learning"]
    EPIC_KW     = ["application","platform","end-to-end","production","enterprise",
                   "greenfield","microservices","full-stack","system design",
                   "complete app","build everything","entire system","saas"]

    def sc(kws): return sum(1 for k in kws if k in text)
    scores = {
        "SIMPLE":   sc(SIMPLE_KW)   + (3 if ctx_lines < 30  else 0),
        "MODERATE": sc(MODERATE_KW) + (2 if 30 <= ctx_lines < 150 else 0),
        "COMPLEX":  sc(COMPLEX_KW)  + (2 if len(text.split()) > 80 else 0),
        "EPIC":     sc(EPIC_KW)     + (3 if ctx_lines > 200 else 0) + (2 if len(text.split()) > 200 else 0),
    }
    order = ["SIMPLE","MODERATE","COMPLEX","EPIC"]
    # SIMPLE wins ties — always classify DOWN not UP
    best_score = max(scores.values())
    complexity = next(k for k in order if scores[k] == best_score)

    TIER = {"SIMPLE":"T1-LOCAL","MODERATE":"T1-CLOUD","COMPLEX":"T2-FLASH","EPIC":"T3"}
    if complexity == "COMPLEX" and any(k in text for k in ["analytics","security","statistics","ml"]):
        TIER["COMPLEX"] = "T2-PRO"
    tier = TIER[complexity]

    MODEL = {"T1-LOCAL":T1_LOCAL_MODEL,"T1-CLOUD":T1_CLOUD_MODEL,
             "T2-PRO":"gemini-2.0-pro","T2-FLASH":"gemini-2.0-flash","T3":"claude-self"}
    FALLBACK = {"T1-LOCAL":["T1-LOCAL","T1-CLOUD","T2-FLASH","T3"],
                "T1-CLOUD":["T1-CLOUD","T2-FLASH","T3"],
                "T2-PRO":["T2-PRO","T2-FLASH","T3"],"T2-FLASH":["T2-FLASH","T3"],"T3":["T3"]}
    NEXT = {"T1-LOCAL":"t1_local_execute","T1-CLOUD":"t1_cloud_execute",
            "T2-PRO":"t2_gemini_execute","T2-FLASH":"t2_gemini_execute","T3":"t3_epic_gate"}

    res = {"complexity":complexity,"assigned_tier":tier,"model":MODEL[tier],
           "fallback_path":FALLBACK[tier],"next_tool":NEXT[tier],
           "scores":scores,"reasoning":f"{complexity} → {tier} ({MODEL[tier]})"}
    _log({"event":"classify","complexity":complexity,"tier":tier})
    return res


@mcp.tool(description="""Execute SIMPLE task on T1-LOCAL: qwen2.5-coder:7b via Ollama localhost.
ONLY for SIMPLE tasks from tier_classify. Real Ollama API call — not Claude generating.
Returns content, quality score. If quality<0.75 → escalate_to field shows next tool.""")
def t1_local_execute(prompt: str, context: str = "",
                     temperature: float = 0.1, timeout_s: int = 90) -> dict:
    try:
        r = _ollama(OLLAMA_LOCAL, T1_LOCAL_MODEL, prompt, context, temperature, timeout_s)
        q = _score(r["content"])
        _log({"event":"t1_local","quality":q,"latency_ms":r["latency_ms"],"passed":q>=QUALITY_GATE})
        return {"status":"SUCCESS","tier":"T1-LOCAL","content":r["content"],"quality":q,
                "passed_gate":q>=QUALITY_GATE,"model":r["model"],"tokens_out":r["tokens_out"],
                "latency_ms":r["latency_ms"],"endpoint":r["endpoint"],
                "escalate_to":"t1_cloud_execute" if q<QUALITY_GATE else None}
    except ConnectionError as e:
        _log({"event":"t1_local_offline"})
        return {"status":"OFFLINE","tier":"T1-LOCAL","error":str(e),
                "action":"Call t1_cloud_execute as fallback",
                "fix_cmd":f"ollama serve && ollama pull {T1_LOCAL_MODEL}"}


@mcp.tool(description="""Execute MODERATE task on T1-CLOUD: qwen3-coder:480b via remote Ollama.
Also T1-LOCAL fallback when offline or quality<0.75. Real Ollama API call at $OLLAMA_CLOUD_HOST.
Returns content, quality score. If quality<0.75 → escalate_to=t2_gemini_execute.""")
def t1_cloud_execute(prompt: str, context: str = "",
                     temperature: float = 0.1, timeout_s: int = 300,
                     is_fallback: bool = False) -> dict:
    if not OLLAMA_CLOUD:
        return {"status":"NOT_CONFIGURED","tier":"T1-CLOUD",
                "error":"OLLAMA_CLOUD_HOST not set",
                "action":"Set env var or call t2_gemini_execute",
                "fix_cmd":"export OLLAMA_CLOUD_HOST=http://your-server:11434"}
    try:
        r = _ollama(OLLAMA_CLOUD, T1_CLOUD_MODEL, prompt, context, temperature, timeout_s)
        q = _score(r["content"])
        _log({"event":"t1_cloud","fallback":is_fallback,"quality":q})
        return {"status":"SUCCESS","tier":"T1-CLOUD","is_fallback":is_fallback,
                "content":r["content"],"quality":q,"passed_gate":q>=QUALITY_GATE,
                "model":r["model"],"latency_ms":r["latency_ms"],"endpoint":r["endpoint"],
                "escalate_to":"t2_gemini_execute" if q<QUALITY_GATE else None}
    except ConnectionError as e:
        _log({"event":"t1_cloud_offline"})
        return {"status":"OFFLINE","tier":"T1-CLOUD","error":str(e),
                "action":"Call t2_gemini_execute as fallback"}


@mcp.tool(description="""Execute COMPLEX task via T2: Gemini CLI with Google user account auth.
NO API KEY — uses 'gemini' CLI command directly. ONLY for COMPLEX tasks.
Also T1-CLOUD fallback. gemini_model: 'gemini-2.0-flash' (fast) or 'gemini-2.0-pro' (deep).
Auth: Google user account via Gemini CLI (gemini auth login). Returns content, quality score.""")
def t2_gemini_execute(prompt: str, context: str = "",
                      gemini_model: str = "gemini-2.0-flash",
                      timeout_s: int = 120, is_fallback: bool = False) -> dict:
    if gemini_model not in ("gemini-2.0-flash","gemini-2.0-pro","gemini-2.5-flash","gemini-2.5-pro"):
        gemini_model = "gemini-2.0-flash"
    try:
        r = _gemini(prompt, context, gemini_model, timeout_s)
        q = _score(r["content"])
        _log({"event":"t2_gemini","model":gemini_model,"fallback":is_fallback,"quality":q})
        return {"status":"SUCCESS","tier":"T2","is_fallback":is_fallback,
                "content":r["content"],"quality":q,"passed_gate":q>=QUALITY_GATE,
                "model":r["model"],"latency_ms":r["latency_ms"],
                "auth_method":"gemini-cli-google-account",
                "escalate_to":"t3_epic_gate with force=True" if q<QUALITY_GATE else None}
    except (RuntimeError, TimeoutError) as e:
        _log({"event":"t2_error","error":str(e)})
        return {"status":"ERROR","tier":"T2","error":str(e),
                "action":"Call t3_epic_gate with force=True as last-resort fallback"}


@mcp.tool(description="""ROUTING GATE — controls T3 (Claude self-generation) access.
BLOCKS non-EPIC tasks. Returns BLOCKED with correct tool if misrouted.
Call only when: (a) complexity=EPIC, OR (b) T1+T2 chain all exhausted, OR (c) force=True with reason.
This is the subscription burn prevention gate. Prevents silent T3 routing fraud.""")
def t3_epic_gate(complexity: str, chain_exhausted: bool = False,
                 force: bool = False, force_reason: str = "",
                 task_summary: str = "") -> dict:
    is_epic     = complexity.upper() == "EPIC"
    is_override = force and bool(force_reason.strip())
    allowed     = is_epic or chain_exhausted or is_override

    if not allowed:
        correct = {"SIMPLE":"t1_local_execute → qwen2.5-coder:7b",
                   "MODERATE":"t1_cloud_execute → qwen3-coder:480b",
                   "COMPLEX":"t2_gemini_execute → gemini-2.0-flash"}.get(complexity.upper(),"tier_classify")
        _log({"event":"T3_BLOCKED","complexity":complexity,"task":task_summary})
        return {
            "status":"BLOCKED",
            "reason":f"ROUTING VIOLATION — complexity={complexity} is NOT EPIC. T3 call blocked.",
            "correct_tool": correct,
            "action":f"Use {correct} instead. Do NOT self-generate.",
            "subscription_impact":"PREVENTED — subscription NOT charged",
        }

    reason = ("complexity=EPIC" if is_epic else
              "full chain exhausted (T1-LOCAL+T1-CLOUD+T2 all failed)" if chain_exhausted else
              f"force override: {force_reason}")
    _log({"event":"T3_APPROVED","complexity":complexity,"reason":reason,"task":task_summary})
    return {
        "status":"APPROVED","reason":reason,
        "instruction":"Generate content directly as T3. COMPLETE implementations only. No TODOs.",
        "subscription_impact":"T3 authorized — subscription usage applies",
    }


@mcp.tool(description="""Check all tier availability at session start or after failures.
Returns per-tier status: Ollama (T1), Gemini CLI (T2), Claude self (T3).""")
def tier_health_check() -> dict:
    results = {}
    # T1-LOCAL
    try:
        req = urllib.request.Request(f"{OLLAMA_LOCAL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as r:
            names = [m["name"] for m in json.loads(r.read()).get("models",[])]
            qwen  = [n for n in names if "qwen2.5" in n]
            results["T1-LOCAL"] = {"online":bool(qwen),"model":T1_LOCAL_MODEL,
                "found":qwen or names[:2],"fix":f"ollama pull {T1_LOCAL_MODEL}" if not qwen else None}
    except Exception as e:
        results["T1-LOCAL"] = {"online":False,"fix":"ollama serve && ollama pull qwen2.5-coder:7b","error":str(e)[:80]}

    # T1-CLOUD
    if OLLAMA_CLOUD:
        try:
            req = urllib.request.Request(f"{OLLAMA_CLOUD}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as r:
                names = [m["name"] for m in json.loads(r.read()).get("models",[])]
                qwen3 = [n for n in names if "qwen3" in n]
                results["T1-CLOUD"] = {"online":bool(qwen3),"model":T1_CLOUD_MODEL,"found":qwen3 or names[:2]}
        except Exception as e:
            results["T1-CLOUD"] = {"online":False,"error":str(e)[:80]}
    else:
        results["T1-CLOUD"] = {"online":False,"error":"OLLAMA_CLOUD_HOST not set",
                               "fix":"export OLLAMA_CLOUD_HOST=http://your-server:11434"}

    # T2 Gemini CLI
    try:
        r = subprocess.run(["gemini","--version"],capture_output=True,text=True,timeout=5)
        results["T2-GEMINI"] = {"online":r.returncode==0,"auth":"Google user account (gemini CLI)",
            "models":["gemini-2.0-flash","gemini-2.0-pro"],"cli":r.stdout.strip()[:50],
            "fix":"gemini auth login" if r.returncode!=0 else None}
    except FileNotFoundError:
        results["T2-GEMINI"] = {"online":False,"fix":"pip install google-cloud-aiplatform && gemini auth login"}

    results["T3-CLAUDE"] = {"online":True,"model":"claude-self","auth":"Claude user account (CLI)",
        "warning":"EPIC + exhausted fallback ONLY. Every call uses subscription."}

    _log({"event":"health_check","online":sum(1 for v in results.values() if v.get("online"))})
    return results


@mcp.tool(description="""Log routing decision for audit. Call after every classify+execute cycle.
Tracks T1/T2/T3 balance, detects fraud, reports subscription health per session.""")
def tier_audit_log(task_summary: str, complexity: str, assigned_tier: str,
                   actual_tier: str, api_call_made: bool,
                   quality_score: float = 0.0, fallback_used: bool = False,
                   fraud_detected: bool = False) -> dict:
    entry = {"event":"routing_decision","task":task_summary,"complexity":complexity,
             "assigned":assigned_tier,"actual":actual_tier,"api_call":api_call_made,
             "quality":quality_score,"fallback":fallback_used,"fraud":fraud_detected,
             "correct":assigned_tier==actual_tier and api_call_made}
    _log(entry)

    try:
        lines = [json.loads(l) for l in LOG_PATH.read_text().strip().split("\n") if l]
        rd = [e for e in lines if e.get("event")=="routing_decision"]
        t1 = sum(1 for e in rd if e.get("actual","").startswith("T1"))
        t2 = sum(1 for e in rd if e.get("actual","").startswith("T2"))
        t3 = sum(1 for e in rd if e.get("actual")=="T3")
        fraud = sum(1 for e in rd if e.get("fraud"))
        ok    = sum(1 for e in rd if e.get("correct"))
    except Exception:
        t1=t2=t3=fraud=ok=0; rd=[]

    return {
        "logged":True,"session_stats":{"total":len(rd),"T1":t1,"T2":t2,"T3":t3,
        "fraud_prevented":fraud,"correct":ok,
        "accuracy":f"{ok/len(rd)*100:.0f}%" if rd else "n/a"},
        "subscription_health": "GOOD" if t3<=1 else f"REVIEW — {t3} T3 calls",
        "log_path":str(LOG_PATH),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
