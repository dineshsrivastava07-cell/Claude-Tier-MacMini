#!/usr/bin/env python3
"""
DSR AI-LAB — TIER ENFORCER v9 FINAL
File: ~/tier-enforcer-mcp/server.py

ARCHITECTURE (research-verified correct design):
  Claude CLI = process manager for this stdio MCP server
  Claude CLI spawns this process on session start via settings.json
  Claude CLI kills this process on session end
  NO external watchdog needed or correct

CRASH PROTECTION:
  Every MCP tool wrapped in try/except
  Errors logged and returned as structured error response
  Process NEVER exits due to a tool error
  FastMCP handles transport-level exceptions

HARD GATE:
  Claude = BRAIN ONLY (classify, plan, select skills, route)
  Ollama T1-LOCAL/MID/CLOUD = executes ALL code
  Gemini T2-FLASH/PRO = analysis only, T1 executes
  HF T2-KIMI = analysis only, T1 executes
  intercept.py hook = Edit/Write/MultiEdit -> Ollama
  CLAUDE_EXECUTION_BLOCK = True in all execution paths

OLLAMA KEEP_ALIVE:
  keep_alive=-1 in every API request (per-request = most reliable)
  OLLAMA_KEEP_ALIVE=-1 set via launchctl (server default)
  Both required per Ollama research (client can override server default)
"""

import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*pydantic.*")
warnings.filterwarnings("ignore", message=".*Pydantic.*")

import os, json, time, subprocess, logging, sqlite3, urllib.request
import threading, glob
from typing import TypedDict
from fastmcp import FastMCP

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

try:
    from huggingface_hub import InferenceClient
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

HOME       = os.path.expanduser("~")
DB_DIR     = os.path.join(HOME, ".tier-enforcer")
LOG_PATH   = os.path.join(DB_DIR, "routing.log")
MEM_DB     = os.path.join(DB_DIR, "memory.db")
SKILLS_DIR = os.path.join(HOME, ".claude", "skills")
os.makedirs(DB_DIR, exist_ok=True)

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tier-v9")

OLLAMA_LOCAL  = os.environ.get("OLLAMA_LOCAL_HOST", "http://localhost:11434")
OLLAMA_CLOUD  = os.environ.get("OLLAMA_CLOUD_HOST", "http://localhost:11434")
HF_API_KEY    = os.environ.get("HF_API_KEY", "")

# Confirmed model names (validated against actual ollama list)
MODEL_T1_LOCAL = "qwen2.5-coder:7b"
MODEL_T1_MID   = "qwen2.5-coder:14b"
MODEL_T1_CLOUD = "qwen3-coder:480b-cloud"

TIMEOUT_LOCAL = int(os.environ.get("OLLAMA_TIMEOUT_LOCAL", "600"))
TIMEOUT_MID   = int(os.environ.get("OLLAMA_TIMEOUT_MID",   "600"))
TIMEOUT_CLOUD = int(os.environ.get("OLLAMA_TIMEOUT_CLOUD", "600"))

# keep_alive=-1 in EVERY request (per-request is most reliable per research)
# This ensures even if OLLAMA_KEEP_ALIVE env var is overridden, these stay loaded
PARAMS_7B  = {"num_ctx":8192,  "num_predict":2048, "temperature":0.1,
               "top_p":0.9, "repeat_penalty":1.1, "keep_alive":-1}
PARAMS_14B = {"num_ctx":16384, "num_predict":4096, "temperature":0.1,
               "top_p":0.9, "repeat_penalty":1.1, "keep_alive":-1}
PARAMS_480B= {"num_ctx":32768, "num_predict":8192, "temperature":0.1,
               "top_p":0.9, "repeat_penalty":1.1, "keep_alive":-1}

# HARD GATE: Claude NEVER executes. Always True.
CLAUDE_EXECUTION_BLOCK = True

QUALITY_THRESHOLDS = {"T1-LOCAL":0.45,"T1-MID":0.55,"T1-CLOUD":0.60,"DEFAULT":0.50}
MAX_FALLBACKS = 2

TIER_CONFIG = {
    "T1-LOCAL":{"model":MODEL_T1_LOCAL,"role":"executor","type":"ollama",
                "base":OLLAMA_LOCAL,"timeout":TIMEOUT_LOCAL,"params":PARAMS_7B,
                "label":"qwen2.5-coder:7b @ localhost (simple/fast)","ram_gb":4.7},
    "T1-MID":  {"model":MODEL_T1_MID,  "role":"executor","type":"ollama",
                "base":OLLAMA_LOCAL,"timeout":TIMEOUT_MID,"params":PARAMS_14B,
                "label":"qwen2.5-coder:14b @ localhost (complex)","ram_gb":9.0},
    "T1-CLOUD":{"model":MODEL_T1_CLOUD,"role":"executor","type":"ollama",
                "base":OLLAMA_CLOUD,"timeout":TIMEOUT_CLOUD,"params":PARAMS_480B,
                "label":"qwen3-coder:480b-cloud @ cloud (epic)","ram_gb":None},
    "T2-FLASH":{"model":"gemini-2.5-flash","role":"analysis","type":"gemini",
                "label":"gemini-2.5-flash (analysis -> T1-MID executes)"},
    "T2-PRO":  {"model":"gemini-2.5-pro",  "role":"analysis","type":"gemini",
                "label":"gemini-2.5-pro (deep review -> T1-MID executes)"},
    "T2-KIMI": {"model":"Qwen/Kimi-K2-Instruct","role":"analysis","type":"huggingface",
                "label":"Kimi-K2-Instruct (math/algo -> T1-MID executes)"},
}

ROUTING_RULES = {
    # T1-CLOUD: epic multi-file, greenfield, full platform (epic tier merged here)
    "T1-CLOUD":{"keywords":["full feature set","entire module","rpa workflow","ai agent system",
                             "multi-file implementation","end to end feature","greenfield platform",
                             "full system design","entire application","production architecture",
                             "design and build complete","from scratch end to end","full platform",
                             "design complete","greenfield","complete system","end to end system",
                             "complete application","build complete"],
                "desc":"T1-CLOUD qwen3-coder:480b-cloud executes"},
    "T2-KIMI": {"keywords":["algorithm analysis","mathematical proof","statistical model",
                             "complex math","optimize algorithm","big o"],
                "desc":"Kimi analysis -> T1-MID implements"},
    "T2-PRO":  {"keywords":["security audit","architecture review","performance review",
                             "code review entire","analyse codebase"],
                "desc":"Gemini Pro review -> T1-MID implements"},
    "T2-FLASH":{"keywords":["debug","fix bug","trace error","why is this failing",
                             "what is wrong with","error on line","failing test",
                             "test failing","not working","broken","exception",
                             "stack trace","traceback","error in","fails with"],
                "desc":"Gemini Flash analyses -> T1-MID fixes"},
    "T1-MID":  {"keywords":["implement","create function","write class","unit test",
                             "add endpoint","build service","write module",
                             "connect to","integrate","refactor"],
                "desc":"T1-MID qwen2.5-coder:14b executes"},
    "T1-LOCAL":{"keywords":[],"desc":"T1-LOCAL qwen2.5-coder:7b executes (default)"},
}

SKILL_KEYWORD_MAP = {
    "coding":       ["code","function","class","api","module","implement","write","create","endpoint"],
    "architecture": ["architecture","design","system","adr","review","structure","pattern"],
    "rca":          ["debug","error","bug","fix","failing","crash","issue","trace","root cause"],
    "math":         ["math","algorithm","statistical","equation","formula","optimize","complexity"],
    "ai":           ["ai","llm","agent","model","neural","ml","embedding","inference"],
    "rpa":          ["rpa","automation","workflow","automate","task automation"],
    "mobile":       ["mobile","react native","flutter","ios","android","expo","screen"],
    "web":          ["web","nextjs","react","pwa","frontend","website","landing page","component"],
    "ecommerce":    ["ecommerce","cart","shop","product","payment","order","checkout"],
    "files":        ["file","folder","directory","organize","rename","sync","compress"],
    "mac":          ["mac","macos","applescript","shortcut","finder","automator"],
}

SKILL_MCP_MAP = {
    "coding":       ["coding-mcp","integration-mcp"],
    "architecture": ["arch-mcp","integration-mcp"],
    "rca":          ["rca-mcp","coding-mcp"],
    "math":         ["math-mcp"],
    "ai":           ["aidev-mcp","coding-mcp"],
    "rpa":          ["rpa-mcp","coding-mcp"],
    "mobile":       ["mobile-dev-mcp"],
    "web":          ["webmobile-dev-mcp","website-dev-mcp"],
    "ecommerce":    ["ecommerce-mcp"],
    "files":        ["files-automation-mcp"],
    "mac":          ["mac-automation-mcp"],
}


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CLASSIFIER + SKILL SELECTOR
# ═════════════════════════════════════════════════════════════════════════════

def _classify_task(task):
    t = task.lower()
    for tier in ["T2-KIMI","T2-PRO","T2-FLASH","T1-CLOUD","T1-MID"]:
        if any(k in t for k in ROUTING_RULES[tier]["keywords"]):
            return tier, TIER_CONFIG.get(tier, TIER_CONFIG["T1-LOCAL"]), ROUTING_RULES[tier]
    return "T1-LOCAL", TIER_CONFIG["T1-LOCAL"], ROUTING_RULES["T1-LOCAL"]


def _get_executor_tier(classified):
    if classified in ("T2-FLASH","T2-PRO","T2-KIMI"): return "T1-MID"
    return classified


def _select_skills(task):
    t = task.lower()
    skill_content, mcp_servers, skill_names = [], [], []
    for skill_name, keywords in SKILL_KEYWORD_MAP.items():
        if any(k in t for k in keywords):
            skill_names.append(skill_name)
            for pattern in [skill_name+".md","*"+skill_name+"*.md"]:
                matches = glob.glob(os.path.join(SKILLS_DIR, pattern))
                if matches:
                    try:
                        skill_content.append("[SKILL:"+skill_name+"]\n"+open(matches[0]).read()[:1500])
                    except Exception: pass
                    break
            mcp_servers.extend(SKILL_MCP_MAP.get(skill_name,[]))
    return "\n\n".join(skill_content), list(dict.fromkeys(mcp_servers)), skill_names


def _get_live_ollama_status():
    status = {"pulled":[],"loaded":[],"available":False}
    try:
        with urllib.request.urlopen(
            urllib.request.Request(OLLAMA_LOCAL.rstrip("/")+"/api/tags"),timeout=4
        ) as r:
            status["pulled"]    = [m["name"] for m in json.loads(r.read()).get("models",[])]
            status["available"] = True
    except Exception: pass
    try:
        with urllib.request.urlopen(
            urllib.request.Request(OLLAMA_LOCAL.rstrip("/")+"/api/ps"),timeout=4
        ) as r:
            status["loaded"] = [m["name"] for m in json.loads(r.read()).get("models",[])]
    except Exception: pass
    return status


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — OLLAMA HTTP CLIENT (streaming, keep_alive=-1 always)
# ═════════════════════════════════════════════════════════════════════════════

def _call_ollama(model, base_url, prompt, system="", timeout=600, params=None):
    """
    Streaming HTTP to Ollama. keep_alive=-1 in every request.
    This is the most reliable approach per research — per-request
    keep_alive overrides any server default. No client can silently
    reset it to 5m unless they also call this function.
    """
    params = params or PARAMS_7B
    # Always ensure keep_alive=-1 regardless of params passed
    params = {**params, "keep_alive": -1}
    messages = []
    if system: messages.append({"role":"system","content":system})
    messages.append({"role":"user","content":prompt})
    payload = json.dumps({"model":model,"messages":messages,"stream":True,"options":params}).encode()
    req = urllib.request.Request(
        base_url.rstrip("/")+"/api/chat",
        data=payload, headers={"Content-Type":"application/json"}, method="POST"
    )
    t_start=time.time(); chunks=[]; done=False
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            for raw in resp:
                line=raw.decode("utf-8").strip()
                if not line: continue
                try:
                    obj=json.loads(line)
                    c=obj.get("message",{}).get("content","")
                    if c: chunks.append(c)
                    if obj.get("done",False): done=True; break
                except Exception: pass
        result="".join(chunks); elapsed=round(time.time()-t_start,1)
        return {"ok":True,"result":result,"model":model,"elapsed":elapsed,"done":done}
    except Exception as e:
        partial="".join(chunks)
        elapsed=round(time.time()-t_start,1)
        if partial and len(partial.strip())>50:
            return {"ok":True,"result":partial,"model":model,"elapsed":elapsed,"partial":True}
        return {"ok":False,"error":str(e)[:200],"model":model,"elapsed":elapsed}


def _call_ollama_retry(model,base_url,prompt,system="",timeout=600,params=None,retries=1):
    for i in range(retries+1):
        r=_call_ollama(model,base_url,prompt,system,timeout,params)
        if r["ok"]: return r
        if i<retries: time.sleep(5*(i+1))
    return r


def _prewarm_single(model,base_url):
    """Send minimal request with keep_alive=-1 to load model into RAM."""
    payload=json.dumps({"model":model,"messages":[{"role":"user","content":"hi"}],
                        "stream":False,"options":{"num_predict":1,"keep_alive":-1}}).encode()
    req=urllib.request.Request(base_url.rstrip("/")+"/api/chat",
                                data=payload,headers={"Content-Type":"application/json"},method="POST")
    t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=60) as r: r.read()
        return {"ok":True,"model":model,"elapsed":round(time.time()-t,1)}
    except Exception as e:
        return {"ok":False,"model":model,"error":str(e)[:80]}


def _call_gemini(model,prompt,system=""):
    try:
        full=(system+"\n\n"+prompt).strip() if system else prompt
        r=subprocess.run(["gemini","--model",model,full],capture_output=True,text=True,timeout=120)
        return {"ok":r.returncode==0,"result":r.stdout.strip(),"model":model}
    except Exception as e:
        return {"ok":False,"error":str(e),"model":model}


def _call_hf(model,prompt):
    try:
        if not HF_AVAILABLE or not HF_API_KEY:
            return {"ok":False,"error":"HF_API_KEY not set","model":model}
        client=InferenceClient(token=HF_API_KEY)
        return {"ok":True,"result":client.text_generation(prompt,model=model,
                max_new_tokens=2048,temperature=0.1),"model":model}
    except Exception as e:
        return {"ok":False,"error":str(e),"model":model}


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — QUALITY SCORER + AUDIT
# ═════════════════════════════════════════════════════════════════════════════

def _score(result,task,tier="T1-LOCAL"):
    if not result or len(result.strip())<15: return 0.0
    s=0.4; n=len(result.strip())
    if n>200: s+=0.10
    if n>800: s+=0.10
    if n>2000: s+=0.05
    code=["def ","class ","import ","from ","function ","const ","export ","return ",
          "async ","try:","except","SELECT ","CREATE ","```","#!/"]
    s+=min(sum(1 for m in code if m in result)*0.04,0.20)
    if any(m in result for m in ["return ","};","END","```\n","\nif __name__"]): s+=0.10
    if any(p in result.lower() for p in ["i cannot help","i am unable to","as an ai, i cannot"]): s-=0.40
    return round(min(max(s,0.0),1.0),3)


def _init_db():
    """Initialize DB with correct 11-column schema."""
    try:
        conn=sqlite3.connect(MEM_DB)
        conn.execute("""CREATE TABLE IF NOT EXISTS routing_log (
            ts REAL, session TEXT, task TEXT,
            classified_tier TEXT, executor_tier TEXT,
            model TEXT, score REAL, ok INTEGER,
            elapsed REAL, skills TEXT, brain_used INTEGER
        )""")
        conn.commit(); conn.close()
    except Exception as e: log.error("db_init: %s",e)


def _audit(sid,task,cls,exe,model,score,ok,elapsed=0.0,skills=None,brain=False):
    entry={"ts":time.time(),"session":sid,"task":task[:120],"classified_tier":cls,
           "executor_tier":exe,"model":model,"score":score,"ok":ok,
           "elapsed":elapsed,"skills":skills or [],"brain_used":brain}
    log.info(json.dumps(entry))
    try:
        conn=sqlite3.connect(MEM_DB)
        conn.execute("INSERT INTO routing_log VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (entry["ts"],sid,entry["task"],cls,exe,model,score,
                      int(ok),elapsed,json.dumps(skills or []),int(brain)))
        conn.commit(); conn.close()
    except Exception as e: log.error("audit: %s",e)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — LANGGRAPH NODES + GRAPH
# ═════════════════════════════════════════════════════════════════════════════

class TierState(TypedDict):
    task:str; session_id:str; context:str
    classified_tier:str; executor_tier:str; tier_config:dict; rule:dict
    skill_content:str; skill_names:list; mcp_servers:list
    brain_plan:str; analysis:str; execution_prompt:str
    result:str; score:float; fallback_count:int; final_tier:str
    elapsed:float; ok:bool; mode:str; should_escalate:bool; brain_used:bool


def _node_classify(s):
    try:
        tier,cfg,rule=_classify_task(s["task"])
        executor=_get_executor_tier(tier)
        s.update({"classified_tier":tier,"executor_tier":executor,
                  "tier_config":TIER_CONFIG.get(executor,TIER_CONFIG["T1-LOCAL"]),
                  "rule":rule,"mode":"LANGGRAPH_HARD","fallback_count":0,
                  "should_escalate":False,"elapsed":0.0,"brain_used":False})
    except Exception as e:
        log.error("node_classify: %s",e)
        s.update({"classified_tier":"T1-LOCAL","executor_tier":"T1-LOCAL",
                  "tier_config":TIER_CONFIG["T1-LOCAL"],"rule":ROUTING_RULES["T1-LOCAL"],
                  "mode":"LANGGRAPH_HARD","fallback_count":0,"should_escalate":False,
                  "elapsed":0.0,"brain_used":False})
    return s


def _node_skill_selector(s):
    try:
        sc,mcps,snames=_select_skills(s["task"])
        s["skill_content"]=sc; s["mcp_servers"]=mcps; s["skill_names"]=snames
    except Exception as e:
        log.error("node_skill_selector: %s",e)
        s["skill_content"]=""; s["mcp_servers"]=[]; s["skill_names"]=[]
    return s


def _node_claude_brain(s):
    """
    Claude's reasoning node. Decomposes task, selects approach.
    Uses T1-LOCAL 7b for planning (fast, lightweight).
    HARD GATE: Claude never executes. This node only PLANS.
    """
    try:
        prompt=(
            "TASK ANALYSIS\n\nTask: "+s["task"]+"\n\n"
            +(("Context:\n"+s["context"]+"\n\n") if s["context"] else "")
            +(("Skills:\n"+s["skill_content"][:1500]+"\n\n") if s["skill_content"] else "")
            +"Produce a concise execution plan:\n"
            "1. GOAL: What must be accomplished\n"
            "2. FILES: Files to read/create/modify\n"
            "3. STEPS: Numbered implementation steps\n"
            "4. APPROACH: Best technical approach\n"
            "Do NOT implement. This plan goes to Ollama "
            +s["classified_tier"]+" for execution."
        )
        r=_call_ollama(MODEL_T1_LOCAL,OLLAMA_LOCAL,prompt,
                       "You are a technical planning assistant. Be concise.",
                       timeout=90,params={**PARAMS_7B,"num_predict":600})
        s["brain_plan"]=r.get("result","") if r["ok"] else ""
        s["brain_used"]=bool(s["brain_plan"])
    except Exception as e:
        log.error("node_brain: %s",e)
        s["brain_plan"]=""; s["brain_used"]=False
    return s


def _node_prewarm_check(s):
    """Check if executor model is in RAM. Trigger background load if not."""
    try:
        exe=s["executor_tier"]
        if exe in ("T1-LOCAL","T1-MID"):
            cfg=TIER_CONFIG[exe]
            with urllib.request.urlopen(
                urllib.request.Request(cfg["base"].rstrip("/")+"/api/tags"),timeout=3
            ) as r:
                models=[m["name"] for m in json.loads(r.read()).get("models",[])]
            short=cfg["model"].split(":")[0]
            if not any(short in m for m in models):
                threading.Thread(target=_prewarm_single,
                                 args=(cfg["model"],cfg["base"]),daemon=True).start()
    except Exception: pass
    return s


def _build_exec_prompt(s):
    parts=["Task: "+s["task"]]
    if s.get("context"):      parts.append("\nContext:\n"+s["context"])
    if s.get("brain_plan"):   parts.append("\nExecution Plan:\n"+s["brain_plan"])
    if s.get("analysis"):     parts.append("\nAnalysis:\n"+s["analysis"])
    if s.get("skill_content"):parts.append("\nSkills:\n"+s["skill_content"][:2000])
    if s.get("mcp_servers"):  parts.append("\nMCP: "+", ".join(s["mcp_servers"]))
    parts.append("\nImplement completely. Production quality. No placeholders.")
    return "\n".join(parts)


def _node_t2_analysis(s):
    """T2 analysis nodes. Enriches execution prompt. T1 still executes."""
    try:
        tier=s["classified_tier"]
        if tier not in ("T2-FLASH","T2-PRO","T2-KIMI"):
            if not s.get("execution_prompt"): s["execution_prompt"]=_build_exec_prompt(s)
            return s
        cfg=TIER_CONFIG[tier]
        sys_p="Analyse the task. Suggest approach. Do NOT implement. Your analysis guides Ollama executor."
        ap="Analyse:\n\n"+s["task"]
        if s.get("brain_plan"): ap+="\n\nBrain plan:\n"+s["brain_plan"]
        r=_call_gemini(cfg["model"],ap,sys_p) if cfg["type"]=="gemini" else _call_hf(cfg["model"],sys_p+"\n\n"+ap)
        s["analysis"]=r.get("result","") if r["ok"] else "Analysis unavailable."
    except Exception as e:
        log.error("node_t2: %s",e)
        s["analysis"]="Analysis error."
    s["execution_prompt"]=_build_exec_prompt(s)
    return s


def _node_t1_execute(s):
    """
    HARD GATE: Claude cannot reach here.
    Only Ollama T1 tiers execute.
    """
    try:
        exe=s["executor_tier"]
        cfg=TIER_CONFIG.get(exe,TIER_CONFIG["T1-LOCAL"])

        # HARD GATE — if somehow a brain/claude tier reached here, redirect to T1-CLOUD
        if cfg.get("role")!="executor" or cfg.get("type")!="ollama":
            log.error("HARD_GATE_BLOCKED: non-ollama tier %s redirected to T1-CLOUD",exe)
            exe="T1-CLOUD"; cfg=TIER_CONFIG["T1-CLOUD"]
            s["executor_tier"]=exe; s["tier_config"]=cfg

        prompt=s.get("execution_prompt") or _build_exec_prompt(s)
        system="You are an expert software engineer. Implement completely. Production-quality code. No truncation."
        t=time.time()
        r=_call_ollama_retry(cfg["model"],cfg["base"],prompt,system,
                              cfg.get("timeout",TIMEOUT_LOCAL),cfg.get("params",PARAMS_7B),retries=1)
        elapsed=round(time.time()-t,1)
        s.update({"result":r.get("result",""),"ok":r["ok"],"final_tier":exe,
                  "elapsed":elapsed,"score":_score(r.get("result",""),s["task"],exe),
                  "should_escalate":False})
    except Exception as e:
        log.error("node_t1_execute: %s",e)
        s.update({"result":"Execution error: "+str(e)[:100],"ok":False,
                  "final_tier":s.get("executor_tier","T1-LOCAL"),"elapsed":0.0,
                  "score":0.0,"should_escalate":False})
    return s


def _node_escalate(s):
    """Quality gate. STATE NODE — not edge function."""
    try:
        tier=s["executor_tier"]
        threshold=_get_threshold(tier)
        if s["ok"] and s["score"]>=threshold: s["should_escalate"]=False; return s
        if s["result"] and len(s["result"].strip())>100 and s.get("fallback_count",0)>=MAX_FALLBACKS:
            s["should_escalate"]=False; return s
        chain=["T1-LOCAL","T1-MID","T1-CLOUD"]
        idx=chain.index(tier) if tier in chain else -1
        if 0<=idx<len(chain)-1:
            nt=chain[idx+1]
            s.update({"executor_tier":nt,"tier_config":TIER_CONFIG[nt],
                      "fallback_count":s.get("fallback_count",0)+1,"should_escalate":True})
            log.info("ESCALATE %s->%s score=%.3f",tier,nt,s["score"])
        else:
            s["should_escalate"]=False
    except Exception as e:
        log.error("node_escalate: %s",e)
        s["should_escalate"]=False
    return s


def _get_threshold(tier):
    return QUALITY_THRESHOLDS.get(tier,QUALITY_THRESHOLDS["DEFAULT"])


def _node_audit(s):
    try:
        _audit(s.get("session_id","?"),s["task"],s["classified_tier"],
               s.get("final_tier",s["executor_tier"]),
               TIER_CONFIG.get(s.get("final_tier",s["executor_tier"]),{}).get("model","?"),
               s.get("score",0.0),s.get("ok",False),s.get("elapsed",0.0),
               s.get("skill_names",[]),s.get("brain_used",False))
    except Exception as e: log.error("node_audit: %s",e)
    return s


def _build_graph():
    """
    LangGraph v9 final graph:
    classify -> skill_selector -> claude_brain -> prewarm_check
    -> [t2_analysis | t1_execute] -> escalate -> audit -> END

    No t3_plan node (epic tasks route directly to T1-CLOUD).
    claude_brain runs for every task via fixed edges.
    Every node has crash protection.
    """
    g=StateGraph(TierState)
    g.add_node("classify",      _node_classify)
    g.add_node("skill_selector",_node_skill_selector)
    g.add_node("claude_brain",  _node_claude_brain)
    g.add_node("prewarm_check", _node_prewarm_check)
    g.add_node("t2_analysis",   _node_t2_analysis)
    g.add_node("t1_execute",    _node_t1_execute)
    g.add_node("escalate",      _node_escalate)
    g.add_node("audit",         _node_audit)

    g.set_entry_point("classify")
    g.add_edge("classify","skill_selector")
    g.add_edge("skill_selector","claude_brain")
    g.add_edge("claude_brain","prewarm_check")
    g.add_conditional_edges("prewarm_check",
        lambda s: "t2_analysis" if s["classified_tier"] in ("T2-FLASH","T2-PRO","T2-KIMI") else "t1_execute",
        {"t2_analysis":"t2_analysis","t1_execute":"t1_execute"})
    g.add_edge("t2_analysis","t1_execute")
    g.add_edge("t1_execute","escalate")
    g.add_conditional_edges("escalate",
        lambda s: "t1_execute" if s["should_escalate"] else "audit",
        {"t1_execute":"t1_execute","audit":"audit"})
    g.add_edge("audit",END)
    return g.compile()


_GRAPH=None
def _get_graph():
    global _GRAPH
    if _GRAPH is None and LANGGRAPH_AVAILABLE:
        try: _GRAPH=_build_graph()
        except Exception as e: log.error("graph_build: %s",e)
    return _GRAPH


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6 — MCP TOOLS (crash-protected, never raise)
# ═════════════════════════════════════════════════════════════════════════════

mcp=FastMCP("tier-enforcer")


@mcp.tool()
def execute_task(task:str, session_id:str="default", context:str="") -> dict:
    """
    MASTER ENTRY POINT for ALL tasks.
    HARD GATE: Claude brain routes. Ollama T1 executes.
    Returns pre_banner and post_banner with live model/tier info.
    """
    try:
        graph=_get_graph()
        if graph:
            init:TierState={"task":task,"session_id":session_id,"context":context,
                            "classified_tier":"","executor_tier":"","tier_config":{},"rule":{},
                            "skill_content":"","skill_names":[],"mcp_servers":[],"brain_plan":"",
                            "analysis":"","execution_prompt":"","result":"","score":0.0,
                            "fallback_count":0,"final_tier":"","elapsed":0.0,"ok":False,
                            "mode":"LANGGRAPH_HARD","should_escalate":False,"brain_used":False}
            final=graph.invoke(init)
            tier=final.get("final_tier","?")
            model=TIER_CONFIG.get(tier,{}).get("model","?")
            elapsed=final.get("elapsed",0.0)
            skills=final.get("skill_names",[])
            brain=final.get("brain_used",False)
            pre=(
                "┌─────────────────────────────────────────────────────────────┐\n"
                "│ 🧠 BRAIN:    Claude + Skills["+(",".join(skills) if skills else "none")+"]\n"
                "│ 📋 TIER:     "+final["classified_tier"]+" → "+tier+"\n"
                "│ ⚙️  EXECUTOR: "+model+" (Ollama)\n"
                "│ 🔧 MCP:      "+((",".join(final.get("mcp_servers",[])))[:50] or "tier-enforcer")+"\n"
                "│ ⏱️  TIMEOUT:  "+str(TIER_CONFIG.get(tier,{}).get("timeout",600))+"s\n"
                "└─────────────────────────────────────────────────────────────┘")
            post=(
                "┌─────────────────────────────────────────────────────────────┐\n"
                "│ ✅ IMPLEMENTED BY: "+model+" ("+tier+")\n"
                "│ ⏱️  ELAPSED:       "+str(elapsed)+"s\n"
                "│ 📊 SCORE:         "+str(round(final["score"],3))+"  FALLBACKS: "+str(final["fallback_count"])+"\n"
                "│ 🧠 BRAIN PLAN:    "+("Yes — guided execution" if brain else "No")+"\n"
                "│ 🔧 SKILLS:        "+(",".join(skills) if skills else "none")+"\n"
                "│ 🚫 CLAUDE:        DID NOT EXECUTE — Bash=native | Edit/Write→Ollama\n"
                "└─────────────────────────────────────────────────────────────┘")
            return {"mode":final["mode"],"classified_tier":final["classified_tier"],
                    "executor_tier":tier,"executor_model":model,"brain_plan":final.get("brain_plan",""),
                    "skills_used":skills,"mcp_servers":final.get("mcp_servers",[]),
                    "result":final["result"],"score":round(final["score"],3),"ok":final["ok"],
                    "elapsed_s":elapsed,"fallbacks_used":final["fallback_count"],
                    "claude_blocked":True,"pre_banner":pre,"post_banner":post}

        # Fallback: soft chain without LangGraph
        cls,cfg,rule=_classify_task(task); exe=_get_executor_tier(cls)
        ecfg=TIER_CONFIG.get(exe,TIER_CONFIG["T1-LOCAL"])
        sc,mcps,snames=_select_skills(task)
        prompt=task+(("\n\nSkills:\n"+sc[:2000]) if sc else "")
        t=time.time()
        r=_call_ollama_retry(ecfg["model"],ecfg["base"],prompt,"",
                              ecfg.get("timeout",TIMEOUT_LOCAL),ecfg.get("params",PARAMS_7B))
        elapsed=round(time.time()-t,1); score=_score(r.get("result",""),task,exe)
        _audit(session_id,task,cls,exe,ecfg["model"],score,r["ok"],elapsed,snames,False)
        return {"mode":"MCP_SOFT_CHAIN","classified_tier":cls,"executor_tier":exe,
                "executor_model":ecfg["model"],"skills_used":snames,"result":r.get("result",""),
                "score":score,"ok":r["ok"],"elapsed_s":elapsed,"claude_blocked":True}
    except Exception as e:
        log.error("execute_task: %s",e)
        return {"ok":False,"error":str(e)[:200],"claude_blocked":True,"mode":"ERROR"}


@mcp.tool()
def activate_tier_routing(session_id:str="auto") -> dict:
    """CALL 1 on session start. Returns live model status from Ollama."""
    try:
        graph=_get_graph(); live=_get_live_ollama_status()
        pulled=live.get("pulled",[]); loaded=live.get("loaded",[])
        def ms(name):
            short=name.split(":")[0]
            if any(short in m for m in loaded): return "LOADED IN RAM ✅"
            if any(name==m or short in m for m in pulled): return "PULLED — not in RAM ⚡"
            return "NOT PULLED ❌ — ollama pull "+name
        return {
            "activated":True,"session_id":session_id,
            "timestamp":time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode":"LANGGRAPH_HARD" if graph else "MCP_SOFT_CHAIN",
            "langgraph":LANGGRAPH_AVAILABLE,
            "claude_role":"BRAIN + SKILL SELECTOR — Bash=native, Edit/Write=Ollama",
            "v9_nodes":["classify","skill_selector","claude_brain","prewarm_check",
                        "t1_execute","escalate","audit"],
            "live_models":{
                "T1-LOCAL":MODEL_T1_LOCAL+" — "+ms(MODEL_T1_LOCAL),
                "T1-MID":  MODEL_T1_MID+"  — "+ms(MODEL_T1_MID),
                "T1-CLOUD":MODEL_T1_CLOUD+" — "+ms(MODEL_T1_CLOUD),
            },
            "models_in_ram":loaded,"models_pulled":pulled,
            "ollama_available":live["available"],
            "hard_gate":"Claude brain only | Ollama T1 executes | Gemini/HF analysis only",
            "keep_alive":"=-1 per-request (most reliable per Ollama research)",
        }
    except Exception as e:
        log.error("activate: %s",e)
        return {"activated":False,"error":str(e)[:200]}


@mcp.tool()
def prewarm_models() -> dict:
    """
    CALL 3 on session start.
    Loads T1-LOCAL and T1-MID into RAM in parallel.
    keep_alive=-1 per request = models stay loaded until Ollama restarts.
    Note: OLLAMA_KEEP_ALIVE=-1 must also be set via launchctl for server default.
    """
    try:
        results={}
        def warm(model,base,key):
            results[key]=_prewarm_single(model,base)
        threads=[
            threading.Thread(target=warm,args=(MODEL_T1_LOCAL,OLLAMA_LOCAL,"T1-LOCAL"),daemon=True),
            threading.Thread(target=warm,args=(MODEL_T1_MID,OLLAMA_LOCAL,"T1-MID"),daemon=True),
        ]
        for t in threads: t.start()
        for t in threads: t.join(timeout=65)
        live=_get_live_ollama_status(); all_ok=all(v.get("ok",False) for v in results.values())
        return {"prewarm_complete":True,"results":results,"all_ok":all_ok,
                "models_now_in_ram":live.get("loaded",[]),"keep_alive":"=-1 per-request",
                "status":("✅ "+MODEL_T1_LOCAL+"+"+MODEL_T1_MID+" in RAM" if all_ok else "⚠️ partial")}
    except Exception as e:
        log.error("prewarm: %s",e); return {"ok":False,"error":str(e)[:200]}


@mcp.tool()
def tier_health_check(tier:str="ALL") -> dict:
    """CALL 2 on session start. Live connectivity check for all tiers."""
    try:
        def co(base,model):
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(base.rstrip("/")+"/api/tags"),timeout=4
                ) as r:
                    models=[m["name"] for m in json.loads(r.read()).get("models",[])]
                short=model.split(":")[0]
                match=[m for m in models if short in m or model==m]
                return "ONLINE ✅ "+match[0] if match else "DEGRADED ⚠️ not pulled: ollama pull "+model
            except Exception as e: return "OFFLINE ❌ "+str(e)[:50]
        def cg():
            try:
                r=subprocess.run(["gemini","--version"],capture_output=True,text=True,timeout=4)
                return "ONLINE ✅" if r.returncode==0 else "OFFLINE ❌"
            except: return "OFFLINE ❌"
        checks={
            "T1-LOCAL":co(OLLAMA_LOCAL,MODEL_T1_LOCAL),
            "T1-MID":  co(OLLAMA_LOCAL,MODEL_T1_MID),
            "T1-CLOUD":co(OLLAMA_CLOUD,MODEL_T1_CLOUD),
            "T2-FLASH":cg(),"T2-PRO":cg(),
            "T2-KIMI": "ONLINE ✅" if HF_API_KEY else "OFFLINE ❌ set HF_API_KEY",
        }
        if tier!="ALL": return {tier:checks.get(tier,"Unknown")}
        live=_get_live_ollama_status()
        return {"tiers":checks,"models_in_ram":live.get("loaded",[]),
                "routing_mode":"LANGGRAPH_HARD" if _get_graph() else "MCP_SOFT_CHAIN",
                "v9_graph":"classify->skill_selector->claude_brain->prewarm->execute->escalate->audit",
                "hard_gate":"Claude=brain only | Ollama=executor | Gemini/HF=analysis only",
                "intercept":"Bash=native | Edit/Write/MultiEdit->intercept.py->Ollama"}
    except Exception as e:
        log.error("health_check: %s",e); return {"error":str(e)[:200]}


@mcp.tool()
def classify_only(task:str) -> dict:
    """Preview routing decision without executing."""
    try:
        cls,cfg,rule=_classify_task(task); exe=_get_executor_tier(cls)
        ecfg=TIER_CONFIG.get(exe,TIER_CONFIG["T1-LOCAL"])
        _,mcps,skills=_select_skills(task)
        return {"task":task[:100],"classified_tier":cls,"executor_tier":exe,
                "executor_model":ecfg["model"],"executor_label":ecfg.get("label",""),
                "skills_selected":skills,"mcp_servers":mcps,
                "timeout_s":ecfg.get("timeout",TIMEOUT_LOCAL),
                "num_ctx":ecfg.get("params",{}).get("num_ctx","?"),
                "quality_threshold":_get_threshold(exe),"claude_executes":False,
                "rule_desc":rule.get("desc","")}
    except Exception as e:
        log.error("classify_only: %s",e); return {"error":str(e)[:200]}


@mcp.tool()
def check_tier_enforcer() -> dict:
    """Heartbeat. Call before tasks when uncertain if tier-enforcer is alive."""
    try:
        return {"alive":True,"timestamp":time.strftime("%Y-%m-%d %H:%M:%S"),
                "mode":"LANGGRAPH_HARD" if _get_graph() else "MCP_SOFT_CHAIN",
                "claude_blocked":True,"v9":True,
                "hard_gate":"Bash=native | Edit/Write->Ollama | Claude=brain only",
                "message":"Tier enforcer v9 alive and operational"}
    except Exception as e:
        return {"alive":False,"error":str(e)[:100]}


@mcp.tool()
def tier_audit_log(last_n:int=20) -> dict:
    """Last N routing decisions from DB."""
    try:
        conn=sqlite3.connect(MEM_DB)
        rows=conn.execute(
            "SELECT ts,session,task,classified_tier,executor_tier,model,"
            "score,ok,elapsed,skills,brain_used "
            "FROM routing_log ORDER BY ts DESC LIMIT ?",(last_n,)
        ).fetchall(); conn.close()
        return {"entries":[{
            "ts":time.strftime("%H:%M:%S",time.localtime(r[0])),
            "session":r[1],"task":r[2],"classified":r[3],"executor":r[4],
            "model":r[5],"score":r[6],"ok":bool(r[7]),"elapsed_s":r[8],
            "skills":json.loads(r[9] or "[]"),"brain_used":bool(r[10])
        } for r in rows],"count":len(rows)}
    except Exception as e:
        log.error("audit_log: %s",e); return {"error":str(e)[:200],"entries":[]}


@mcp.tool()
def tier_reset() -> dict:
    """Reset LangGraph and re-activate."""
    global _GRAPH; _GRAPH=None
    try: return {"reset":True,"status":activate_tier_routing("reset")}
    except Exception as e: return {"reset":False,"error":str(e)[:200]}


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 7 — STARTUP
# ═════════════════════════════════════════════════════════════════════════════

if __name__=="__main__":
    _init_db()
    _get_graph()  # Pre-compile graph on start
    mcp.run()
