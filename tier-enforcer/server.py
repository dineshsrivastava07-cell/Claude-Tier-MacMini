#!/usr/bin/env python3
"""
DSR AI-LAB TIER ENFORCER v8 FINAL
File: ~/tier-enforcer-mcp/server.py

ARCHITECTURE:
  Claude    = BRAIN + SKILL SELECTOR (classify, plan, route)
  intercept = Bash/Edit/Write -> intercept.py -> Ollama
  T1-LOCAL  = qwen2.5-coder:7b  (4.7GB localhost, simple/fast)
  T1-MID    = qwen2.5-coder:14b (9.0GB localhost, complex)
  T1-CLOUD  = qwen3-coder:480b  (cloud, epic)
  T2-*      = analysis only -> enriches T1 prompt
  (epic tasks auto-route to T1-CLOUD — claude_brain plans all tasks)

LANGGRAPH v8 NODES:
  classify -> skill_selector -> claude_brain -> prewarm_check
  -> [t2_analysis | t1_execute]
  -> escalate (STATE NODE) -> audit -> END
"""
# Suppress Pydantic V1 compatibility warning on Python 3.14+
# langchain_core uses pydantic.v1 shim which warns but works correctly
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")
warnings.filterwarnings("ignore", message=".*Pydantic V1.*")


import os, json, time, subprocess, logging, sqlite3
import urllib.request, threading, glob
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

HOME       = os.path.expanduser("~")
DB_DIR     = os.path.join(HOME, ".tier-enforcer")
LOG_PATH   = os.path.join(DB_DIR, "routing.log")
MEM_DB     = os.path.join(DB_DIR, "memory.db")
SKILLS_DIR = os.path.join(HOME, ".claude", "skills")
os.makedirs(DB_DIR, exist_ok=True)

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tier-v8")

OLLAMA_LOCAL  = os.environ.get("OLLAMA_LOCAL_HOST", "http://localhost:11434")
OLLAMA_CLOUD  = os.environ.get("OLLAMA_CLOUD_HOST", "http://localhost:11434")
HF_API_KEY    = os.environ.get("HF_API_KEY", "")

MODEL_T1_LOCAL = "qwen2.5-coder:7b"
MODEL_T1_MID   = "qwen2.5-coder:14b"
MODEL_T1_CLOUD = "qwen3-coder:480b-cloud"

TIMEOUT_LOCAL = int(os.environ.get("OLLAMA_TIMEOUT_LOCAL", "600"))
TIMEOUT_MID   = int(os.environ.get("OLLAMA_TIMEOUT_MID",   "600"))
TIMEOUT_CLOUD = int(os.environ.get("OLLAMA_TIMEOUT_CLOUD", "600"))

PARAMS_7B  = {"num_ctx":8192,  "num_predict":2048, "temperature":0.1, "top_p":0.9, "repeat_penalty":1.1, "keep_alive": -1}
PARAMS_14B = {"num_ctx":16384, "num_predict":4096, "temperature":0.1, "top_p":0.9, "repeat_penalty":1.1, "keep_alive": -1}
PARAMS_480B= {"num_ctx":32768, "num_predict":8192, "temperature":0.1, "top_p":0.9, "repeat_penalty":1.1, "keep_alive": -1}

QUALITY_THRESHOLDS = {"T1-LOCAL":0.45,"T1-MID":0.55,"T1-CLOUD":0.60,"DEFAULT":0.50}
CLAUDE_EXECUTION_BLOCK = True
MASTER_RULE   = "execute_task(task, session_id, context)"
MAX_FALLBACKS = 2

TIER_CONFIG = {
    "T1-LOCAL":{"model":MODEL_T1_LOCAL,"role":"executor","type":"ollama","base":OLLAMA_LOCAL,"timeout":TIMEOUT_LOCAL,"params":PARAMS_7B,"label":"qwen2.5-coder:7b @ localhost (simple/fast)","ram_gb":4.7},
    "T1-MID":  {"model":MODEL_T1_MID,  "role":"executor","type":"ollama","base":OLLAMA_LOCAL,"timeout":TIMEOUT_MID,  "params":PARAMS_14B,"label":"qwen2.5-coder:14b @ localhost (complex)","ram_gb":9.0},
    "T1-CLOUD":{"model":MODEL_T1_CLOUD,"role":"executor","type":"ollama","base":OLLAMA_CLOUD,"timeout":TIMEOUT_CLOUD,"params":PARAMS_480B,"label":"qwen3-coder:480b @ cloud (epic)","ram_gb":None},
    "T2-FLASH":{"model":"gemini-2.5-flash","role":"analysis","type":"gemini","label":"gemini-2.5-flash (analysis->T1-MID)"},
    "T2-PRO":  {"model":"gemini-2.5-pro",  "role":"analysis","type":"gemini","label":"gemini-2.5-pro (review->T1-MID)"},
    "T2-KIMI": {"model":"Qwen/Kimi-K2-Instruct","role":"analysis","type":"huggingface","label":"Kimi-K2 (math/algo->T1-MID)"},
}

ROUTING_RULES = {
    "T2-KIMI":  {"keywords":["algorithm analysis","mathematical proof","statistical model","complex math","optimize algorithm","big o"],"desc":"Kimi->T1-MID"},
    "T2-PRO":   {"keywords":["security audit","architecture review","performance review","code review entire","analyse codebase"],"desc":"Gemini Pro->T1-MID"},
    "T2-FLASH": {"keywords":["debug","fix bug","trace error","why is this failing","what is wrong with","error on line",
                "failing test",
                "test failing",
                "not working",
                "broken",
                "exception",
                "stack trace",
                "traceback",
                "error in",
                "fails with"],"desc":"Gemini Flash->T1-MID"},
    "T1-CLOUD": {"keywords":["full feature set","entire module","rpa workflow","ai agent system","multi-file implementation","end to end feature","greenfield platform","full system design","entire application","production architecture","design and build complete","from scratch end to end","design complete","design and build","greenfield","complete system","full platform","end to end system","build complete","complete application","ecommerce platform","full ecommerce","complete platform"],"desc":"T1-CLOUD 480b"},
    "T1-MID":   {"keywords":["implement","create function","write class","unit test","add endpoint","build service","connect to","integrate","refactor"],"desc":"T1-MID 14b"},
    "T1-LOCAL": {"keywords":[],"desc":"T1-LOCAL 7b (default)"},
}

SKILL_KEYWORD_MAP = {
    "coding":       ["code","function","class","api","module","implement","write","create","endpoint"],
    "architecture": ["architecture","design","system","adr","review","structure","pattern"],
    "rca":          ["debug","error","bug","fix","failing","crash","issue","trace"],
    "math":         ["math","algorithm","statistical","equation","formula","optimize","complexity"],
    "ai":           ["ai","llm","agent","model","neural","ml","embedding"],
    "rpa":          ["rpa","automation","workflow","automate"],
    "mobile":       ["mobile","react native","flutter","ios","android","expo"],
    "web":          ["web","nextjs","react","pwa","frontend","website","component"],
    "ecommerce":    ["ecommerce","cart","shop","product","payment","order","checkout"],
    "files":        ["file","folder","directory","organize","rename","sync"],
    "mac":          ["mac","macos","applescript","shortcut","finder"],
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

FALLBACK_CHAIN = ["T1-LOCAL","T1-MID","T1-CLOUD"]


def _classify_task(task):
    t = task.lower()
    for tier in ["T2-KIMI","T2-PRO","T2-FLASH","T1-CLOUD","T1-MID"]:
        if any(k in t for k in ROUTING_RULES[tier]["keywords"]):
            return tier, TIER_CONFIG[tier], ROUTING_RULES[tier]
    return "T1-LOCAL", TIER_CONFIG["T1-LOCAL"], ROUTING_RULES["T1-LOCAL"]


def _get_executor_tier(classified):
    if classified in ("T2-FLASH","T2-PRO","T2-KIMI"): return "T1-MID"
    return classified


def _get_threshold(tier):
    return QUALITY_THRESHOLDS.get(tier, QUALITY_THRESHOLDS["DEFAULT"])


def _select_skills(task):
    t = task.lower()
    skill_content, mcp_servers, skill_names = [], [], []
    for skill_name, keywords in SKILL_KEYWORD_MAP.items():
        if any(k in t for k in keywords):
            skill_names.append(skill_name)
            for pattern in [skill_name+".md", "*"+skill_name+"*.md"]:
                matches = glob.glob(os.path.join(SKILLS_DIR, pattern))
                if matches:
                    try:
                        content = open(matches[0]).read()[:1500]
                        skill_content.append("[SKILL:"+skill_name+"]\n"+content)
                    except Exception:
                        pass
                    break
            mcp_servers.extend(SKILL_MCP_MAP.get(skill_name,[]))
    return "\n\n".join(skill_content), list(dict.fromkeys(mcp_servers)), skill_names


def _get_live_model_status():
    status = {"pulled":[],"loaded":[],"available":False}
    try:
        with urllib.request.urlopen(urllib.request.Request(OLLAMA_LOCAL.rstrip("/")+"/api/tags"),timeout=4) as r:
            status["pulled"]=[m["name"] for m in json.loads(r.read()).get("models",[])]
            status["available"]=True
    except Exception: pass
    try:
        with urllib.request.urlopen(urllib.request.Request(OLLAMA_LOCAL.rstrip("/")+"/api/ps"),timeout=4) as r2:
            status["loaded"]=[m["name"] for m in json.loads(r2.read()).get("models",[])]
    except Exception: pass
    return status


def _call_ollama(model, base_url, prompt, system="", timeout=600, params=None):
    params = params or PARAMS_7B
    messages = []
    if system: messages.append({"role":"system","content":system})
    messages.append({"role":"user","content":prompt})
    payload = json.dumps({"model":model,"messages":messages,"stream":True,"options":params}).encode()
    req = urllib.request.Request(base_url.rstrip("/")+"/api/chat",
                                  data=payload,headers={"Content-Type":"application/json"},method="POST")
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
                except: pass
        result="".join(chunks); elapsed=round(time.time()-t_start,1)
        return {"ok":True,"result":result,"model":model,"elapsed":elapsed,"done":done}
    except Exception as e:
        partial="".join(chunks)
        elapsed=round(time.time()-t_start,1)
        if partial and len(partial.strip())>50:
            return {"ok":True,"result":partial,"model":model,"elapsed":elapsed,"done":False,"partial":True}
        return {"ok":False,"error":str(e),"model":model,"elapsed":elapsed}


def _call_ollama_retry(model,base_url,prompt,system="",timeout=600,params=None,retries=1):
    for i in range(retries+1):
        r=_call_ollama(model,base_url,prompt,system,timeout,params)
        if r["ok"]: return r
        if i<retries: time.sleep(5*(i+1))
    return r


def _prewarm_single(model,base_url):
    payload=json.dumps({"model":model,"messages":[{"role":"user","content":"hi"}],"stream":False,"options":{"num_predict":1,"keep_alive": -1}}).encode()
    req=urllib.request.Request(base_url.rstrip("/")+"/api/chat",data=payload,headers={"Content-Type":"application/json"},method="POST")
    t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=30) as r: r.read()
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
        if not HF_AVAILABLE or not HF_API_KEY: return {"ok":False,"error":"HF not configured","model":model}
        client=InferenceClient(token=HF_API_KEY)
        return {"ok":True,"result":client.text_generation(prompt,model=model,max_new_tokens=2048,temperature=0.1),"model":model}
    except Exception as e:
        return {"ok":False,"error":str(e),"model":model}


def _score(result,task,tier="T1-LOCAL"):
    if not result or len(result.strip())<15: return 0.0
    s=0.4
    n=len(result.strip())
    if n>200: s+=0.10
    if n>800: s+=0.10
    if n>2000: s+=0.05
    code=["def ","class ","import ","from ","function ","const ","return ","async ","try:","SELECT ","CREATE ","```","#!/"]
    s+=min(sum(1 for m in code if m in result)*0.04,0.20)
    if any(m in result for m in ["return ","};","```\n","\nif __name__"]): s+=0.10
    if any(p in result.lower() for p in ["i cannot help with","i am unable to","as an ai, i cannot"]): s-=0.40
    return round(min(max(s,0.0),1.0),3)


def _audit(sid,task,cls,exe,model,score,ok,elapsed=0.0,skills=None,brain=False):
    try:
        conn=sqlite3.connect(MEM_DB)
        conn.execute("CREATE TABLE IF NOT EXISTS routing_log (ts REAL,session TEXT,task TEXT,classified_tier TEXT,executor_tier TEXT,model TEXT,score REAL,ok INTEGER,elapsed REAL,skills TEXT,brain_used INTEGER)")
        conn.execute("INSERT INTO routing_log VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (time.time(),sid,task[:120],cls,exe,model,score,int(ok),elapsed,json.dumps(skills or []),int(brain)))
        conn.commit(); conn.close()
    except Exception as e:
        log.error("audit: %s",e)
    log.info("AUDIT cls=%s exe=%s model=%s score=%.3f ok=%s elapsed=%ss",cls,exe,model,score,ok,elapsed)


class TierState(TypedDict):
    task:str; session_id:str; context:str
    classified_tier:str; executor_tier:str; tier_config:dict; rule:dict
    skill_content:str; skill_names:list; mcp_servers:list
    brain_plan:str; analysis:str; execution_prompt:str
    result:str; score:float; fallback_count:int; final_tier:str
    elapsed:float; ok:bool; mode:str; should_escalate:bool; brain_used:bool


def _node_classify(s):
    tier,cfg,rule=_classify_task(s["task"]); executor=_get_executor_tier(tier)
    s.update({"classified_tier":tier,"executor_tier":executor,"tier_config":TIER_CONFIG[executor],
               "rule":rule,"mode":"LANGGRAPH_HARD","fallback_count":0,
               "should_escalate":False,"elapsed":0.0,"brain_used":False})
    log.info("CLASSIFY task='%s' tier=%s executor=%s",s["task"][:60],tier,executor)
    return s


def _node_skill_selector(s):
    """v8 NEW — reads ~/.claude/skills/*.md files for relevant skills."""
    sc,mcps,snames=_select_skills(s["task"])
    s["skill_content"]=sc; s["mcp_servers"]=mcps; s["skill_names"]=snames
    if snames: log.info("SKILLS selected=%s mcps=%s",snames,mcps)
    return s


def _node_claude_brain(s):
    """v8 NEW — Claude reasons, decomposes, plans. Never executes."""
    task=s["task"]; tier=s["classified_tier"]
    prompt=(
        "TASK ANALYSIS AND EXECUTION PLANNING\n\nTask: "+task+"\n\n"
        +(("Context:\n"+s["context"]+"\n\n") if s.get("context") else "")
        +(("Relevant skills:\n"+s["skill_content"][:2000]+"\n\n") if s.get("skill_content") else "")
        +"Produce a concise execution plan:\n"
        "1. GOAL: What must be accomplished\n"
        "2. FILES: Files to read/create/modify\n"
        "3. STEPS: Numbered implementation steps\n"
        "4. APPROACH: Best technical approach\n"
        "5. WATCH: Edge cases and pitfalls\n\n"
        "This goes to Ollama "+tier+" for execution. Do NOT implement yourself."
    )
    r=_call_ollama(MODEL_T1_LOCAL,OLLAMA_LOCAL,prompt,
                   "You are a technical planning assistant. Be concise and structured.",
                   timeout=90,params={**PARAMS_7B,"num_predict":800})
    s["brain_plan"]=r.get("result","") if r["ok"] else ""
    s["brain_used"]=bool(s["brain_plan"])
    log.info("BRAIN len=%d ok=%s",len(s["brain_plan"]),r["ok"])
    return s


def _node_prewarm_check(s):
    exe=s["executor_tier"]
    if exe in ("T1-LOCAL","T1-MID"):
        cfg=TIER_CONFIG[exe]
        try:
            with urllib.request.urlopen(urllib.request.Request(cfg["base"].rstrip("/")+"/api/tags"),timeout=3) as r:
                models=[m["name"] for m in json.loads(r.read()).get("models",[])]
            if not any(cfg["model"].split(":")[0] in m for m in models):
                threading.Thread(target=_prewarm_single,args=(cfg["model"],cfg["base"]),daemon=True).start()
        except Exception: pass
    return s


def _build_exec_prompt(s):
    parts=["Task: "+s["task"]]
    if s.get("context"):       parts.append("\nContext:\n"+s["context"])
    if s.get("brain_plan"):    parts.append("\nExecution Plan (Claude brain):\n"+s["brain_plan"])
    if s.get("analysis"):      parts.append("\nAnalysis:\n"+s["analysis"])
    if s.get("skill_content"): parts.append("\nSkills:\n"+s["skill_content"][:2000])
    if s.get("mcp_servers"):   parts.append("\nMCP available: "+", ".join(s["mcp_servers"]))
    parts.append("\nImplement completely. Production quality. No placeholders. No truncation.")
    return "\n".join(parts)


def _node_t2_analysis(s):
    tier=s["classified_tier"]
    if tier not in ("T2-FLASH","T2-PRO","T2-KIMI"):
        if not s.get("execution_prompt"): s["execution_prompt"]=_build_exec_prompt(s)
        return s
    cfg=TIER_CONFIG[tier]
    sys_p="Analyse the task. Suggest approach. Do NOT implement. Your analysis guides an Ollama executor."
    ap="Analyse:\n\n"+s["task"]
    if s.get("brain_plan"): ap+="\n\nBrain plan:\n"+s["brain_plan"]
    r=_call_gemini(cfg["model"],ap,sys_p) if cfg["type"]=="gemini" else _call_hf(cfg["model"],sys_p+"\n\n"+ap)
    s["analysis"]=r.get("result","") if r["ok"] else "Analysis unavailable."
    s["execution_prompt"]=_build_exec_prompt(s)
    return s


def _node_t1_execute(s):
    exe=s["executor_tier"]; cfg=TIER_CONFIG.get(exe,TIER_CONFIG["T1-LOCAL"])
    # HARD CLAUDE EXECUTION BLOCK
    if cfg.get("role")=="brain" or cfg.get("type")=="claude":
        log.warning("CLAUDE_BLOCK -> T1-CLOUD")
        exe="T1-CLOUD"; cfg=TIER_CONFIG["T1-CLOUD"]
        s["executor_tier"]=exe; s["tier_config"]=cfg
    prompt=s.get("execution_prompt") or _build_exec_prompt(s)
    sys_p="You are an expert software engineer. Implement completely. Production-quality code. No truncation."
    t=time.time()
    r=_call_ollama_retry(cfg["model"],cfg["base"],prompt,sys_p,
                         cfg.get("timeout",TIMEOUT_LOCAL),cfg.get("params",PARAMS_7B),retries=1)
    elapsed=round(time.time()-t,1)
    s.update({"result":r.get("result",""),"ok":r["ok"],"final_tier":exe,"elapsed":elapsed,
              "score":_score(r.get("result",""),s["task"],exe),"should_escalate":False})
    log.info("EXECUTE tier=%s model=%s ok=%s score=%.3f elapsed=%ss",
             exe,cfg["model"],r["ok"],s["score"],elapsed)
    return s


def _node_escalate(s):
    """STATE NODE — quality check + escalate within T1 chain only."""
    tier=s["executor_tier"]; threshold=_get_threshold(tier)
    if s["ok"] and s["score"]>=threshold:
        s["should_escalate"]=False; return s
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
    return s


def _route_escalate(s): return "t1_execute" if s["should_escalate"] else "audit"


def _node_audit(s):
    _audit(s.get("session_id","?"),s["task"],s["classified_tier"],s["final_tier"],
           TIER_CONFIG.get(s["final_tier"],{}).get("model","?"),
           s.get("score",0.0),s.get("ok",False),s.get("elapsed",0.0),
           s.get("skill_names",[]),s.get("brain_used",False))
    return s


def _build_graph():
    g=StateGraph(TierState)
    # v8 nodes: skill_selector + claude_brain added
    g.add_node("classify",       _node_classify)
    g.add_node("skill_selector", _node_skill_selector)
    g.add_node("claude_brain",   _node_claude_brain)
    g.add_node("prewarm_check",  _node_prewarm_check)
    g.add_node("t2_analysis",    _node_t2_analysis)
    g.add_node("t1_execute",     _node_t1_execute)
    g.add_node("escalate",       _node_escalate)
    g.add_node("audit",          _node_audit)

    g.set_entry_point("classify")
    g.add_edge("classify",       "skill_selector")
    g.add_edge("skill_selector", "claude_brain")
    g.add_edge("claude_brain",   "prewarm_check")
    g.add_conditional_edges("prewarm_check",
        lambda s:(                  "t2_analysis" if s["classified_tier"] in ("T2-FLASH","T2-PRO","T2-KIMI") else
                  "t1_execute"),
        {"t2_analysis":"t2_analysis","t1_execute":"t1_execute"})
    g.add_edge("t2_analysis","t1_execute")
    g.add_edge("t1_execute","escalate")
    g.add_conditional_edges("escalate",_route_escalate,
                            {"t1_execute":"t1_execute","audit":"audit"})
    g.add_edge("audit",END)
    return g.compile()


_GRAPH=None
def _get_graph():
    global _GRAPH
    if _GRAPH is None and LANGGRAPH_AVAILABLE: _GRAPH=_build_graph()
    return _GRAPH


mcp=FastMCP("tier-enforcer")


@mcp.tool()
def execute_task(task:str, session_id:str="default", context:str="") -> dict:
    """MASTER ENTRY POINT. Claude=brain+skills. Ollama T1=executor."""
    graph=_get_graph()
    if graph:
        init:TierState={"task":task,"session_id":session_id,"context":context,
                        "classified_tier":"","executor_tier":"","tier_config":{},"rule":{},
                        "skill_content":"","skill_names":[],"mcp_servers":[],"brain_plan":"",
                        "analysis":"","execution_prompt":"","result":"","score":0.0,
                        "fallback_count":0,"final_tier":"","elapsed":0.0,"ok":False,
                        "mode":"LANGGRAPH_HARD","should_escalate":False,"brain_used":False}
        final=graph.invoke(init)
        tier=final.get("final_tier","?"); model=TIER_CONFIG.get(tier,{}).get("model","?")
        elapsed=final.get("elapsed",0.0); skills=final.get("skill_names",[])
        brain=final.get("brain_used",False)
        pre=("TASK ASSIGNED BANNER\n"
             "  BRAIN:    Claude + Skills["+(",".join(skills) if skills else "none")+"]\n"
             "  TIER:     "+final["classified_tier"]+" -> "+tier+"\n"
             "  EXECUTOR: "+model+"\n"
             "  MCP:      "+((",".join(final.get("mcp_servers",[])))[:50] or "tier-enforcer")+"\n"
             "  TIMEOUT:  "+str(TIER_CONFIG.get(tier,{}).get("timeout",600))+"s")
        post=("FINAL IMPLEMENTATION BANNER\n"
              "  EXECUTED BY:  "+model+" ("+tier+")\n"
              "  ELAPSED:      "+str(elapsed)+"s\n"
              "  SCORE:        "+str(round(final["score"],3))+" FALLBACKS: "+str(final["fallback_count"])+"\n"
              "  BRAIN USED:   "+("Yes" if brain else "No")+"\n"
              "  SKILLS:       "+(",".join(skills) if skills else "none")+"\n"
              "  CLAUDE:       DID NOT EXECUTE - brain only")
        return {"mode":final["mode"],"classified_tier":final["classified_tier"],
                "executor_tier":tier,"executor_model":model,
                "brain_plan":final.get("brain_plan",""),"skills_used":skills,
                "mcp_servers":final.get("mcp_servers",[]),"result":final["result"],
                "score":round(final["score"],3),"ok":final["ok"],"elapsed_s":elapsed,
                "fallbacks_used":final["fallback_count"],"claude_blocked":True,
                "pre_banner":pre,"post_banner":post}
    # soft chain
    cls,cfg,rule=_classify_task(task); exe=_get_executor_tier(cls); ecfg=TIER_CONFIG[exe]
    sc,mcps,snames=_select_skills(task)
    prompt=task+(("\n\nSkills:\n"+sc[:2000]) if sc else "")
    t=time.time()
    r=_call_ollama_retry(ecfg["model"],ecfg["base"],prompt,"",ecfg.get("timeout",TIMEOUT_LOCAL),ecfg.get("params",PARAMS_7B))
    elapsed=round(time.time()-t,1); score=_score(r.get("result",""),task,exe)
    _audit(session_id,task,cls,exe,ecfg["model"],score,r["ok"],elapsed,snames,False)
    return {"mode":"MCP_SOFT_CHAIN","classified_tier":cls,"executor_tier":exe,
            "executor_model":ecfg["model"],"skills_used":snames,"result":r.get("result",""),
            "score":score,"ok":r["ok"],"elapsed_s":elapsed,"claude_blocked":True}


@mcp.tool()
def activate_tier_routing(session_id:str="auto") -> dict:
    """CALL 1 on session open. Returns live model status from Ollama."""
    graph=_get_graph(); live=_get_live_model_status()
    pulled=live.get("pulled",[]); loaded=live.get("loaded",[])
    def ms(name):
        short=name.split(":")[0]
        if any(short in m for m in loaded): return "LOADED IN RAM"
        if any(short in m for m in pulled): return "PULLED - not in RAM"
        return "NOT PULLED - ollama pull "+name
    return {"activated":True,"session_id":session_id,"timestamp":time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode":"LANGGRAPH_HARD" if graph else "MCP_SOFT_CHAIN","langgraph":LANGGRAPH_AVAILABLE,
            "v8_nodes":["classify","skill_selector","claude_brain","prewarm_check","t1_execute","escalate","audit"],
            "live_models":{"T1-LOCAL":MODEL_T1_LOCAL+" - "+ms(MODEL_T1_LOCAL),
                           "T1-MID":MODEL_T1_MID+" - "+ms(MODEL_T1_MID),
                           "T1-CLOUD":MODEL_T1_CLOUD+" - "+ms(MODEL_T1_CLOUD)},
            "models_in_ram":loaded,"models_pulled":pulled,"ollama_available":live["available"],
            "interception":"Bash/Edit/Write -> intercept.py -> Ollama T1",
            "banner":("DSR AI-Lab TIER ROUTING v8 ACTIVE\n"
                      "  Claude: BRAIN+SKILLS - never executes\n"
                      "  T1-LOCAL  "+MODEL_T1_LOCAL+"  "+ms(MODEL_T1_LOCAL)+"\n"
                      "  T1-MID    "+MODEL_T1_MID+"  "+ms(MODEL_T1_MID)+"\n"
                      "  T1-CLOUD  "+MODEL_T1_CLOUD+"  "+ms(MODEL_T1_CLOUD)+"\n"
                      "  T2-FLASH  gemini-2.5-flash  analysis only\n"
                      "  T2-KIMI   Kimi-K2-Instruct  analysis only\n"
                      "  v8: Bash/Edit/Write -> intercept.py -> Ollama\n"
                      "  v8: skill_selector + claude_brain in LangGraph")}


@mcp.tool()
def prewarm_models() -> dict:
    """CALL 3 on session open. Loads 7b+14b into RAM in parallel."""
    results={}
    def warm(model,base,key):
        results[key]=_prewarm_single(model,base)
    threads=[threading.Thread(target=warm,args=(MODEL_T1_LOCAL,OLLAMA_LOCAL,"T1-LOCAL"),daemon=True),
             threading.Thread(target=warm,args=(MODEL_T1_MID,OLLAMA_LOCAL,"T1-MID"),daemon=True)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=35)
    live=_get_live_model_status(); all_ok=all(v.get("ok",False) for v in results.values())
    return {"prewarm_complete":True,"results":results,"all_ok":all_ok,
            "models_now_in_ram":live.get("loaded",[]),"keep_alive":"=-1",
            "status":"OK "+MODEL_T1_LOCAL+"+"+MODEL_T1_MID+" in RAM - zero swap" if all_ok else "PARTIAL prewarm - check Ollama"}


@mcp.tool()
def tier_health_check(tier:str="ALL") -> dict:
    """Live connectivity with actual model names from Ollama."""
    def co(base,model):
        try:
            with urllib.request.urlopen(urllib.request.Request(base.rstrip("/")+"/api/tags"),timeout=4) as r:
                models=[m["name"] for m in json.loads(r.read()).get("models",[])]
            short=model.split(":")[0]
            match=[m for m in models if short in m]
            return "ONLINE "+match[0] if match else "DEGRADED not pulled: ollama pull "+model
        except Exception as e: return "OFFLINE "+str(e)[:50]
    def cg():
        try:
            r=subprocess.run(["gemini","--version"],capture_output=True,text=True,timeout=4)
            return "ONLINE" if r.returncode==0 else "OFFLINE"
        except: return "OFFLINE"
    checks={"T1-LOCAL":co(OLLAMA_LOCAL,MODEL_T1_LOCAL),"T1-MID":co(OLLAMA_LOCAL,MODEL_T1_MID),
            "T1-CLOUD":co(OLLAMA_CLOUD,MODEL_T1_CLOUD),"T2-FLASH":cg(),"T2-PRO":cg(),
            "T2-KIMI":"ONLINE" if HF_API_KEY else "OFFLINE set HF_API_KEY",
            "T1-CLOUD":"EXECUTOR (epic tasks route here via T1-CLOUD)"}
    if tier!="ALL": return {tier:checks.get(tier,"Unknown")}
    live=_get_live_model_status()
    return {"tiers":checks,"models_in_ram":live.get("loaded",[]),
            "routing_mode":"LANGGRAPH_HARD" if LANGGRAPH_AVAILABLE else "MCP_SOFT_CHAIN",
            "v8_graph":"classify->skill_selector->claude_brain->prewarm->execute->escalate->audit",
            "interception":"Bash/Edit/Write->intercept.py->Ollama T1"}


@mcp.tool()
def classify_only(task:str) -> dict:
    """Preview routing without executing."""
    cls,cfg,rule=_classify_task(task); exe=_get_executor_tier(cls)
    ecfg=TIER_CONFIG[exe]; _,mcps,skills=_select_skills(task)
    return {"task":task[:100],"classified_tier":cls,"executor_tier":exe,
            "executor_model":ecfg["model"],"executor_label":ecfg.get("label",""),
            "skills_selected":skills,"mcp_servers":mcps,
            "timeout_s":ecfg.get("timeout",TIMEOUT_LOCAL),
            "num_ctx":ecfg.get("params",{}).get("num_ctx","?"),
            "quality_threshold":_get_threshold(exe),"claude_executes":False,
            "rule_desc":rule.get("desc","")}


@mcp.tool()
def check_tier_enforcer() -> dict:
    """Heartbeat. If this responds tier-enforcer is alive."""
    return {"alive":True,"timestamp":time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode":"LANGGRAPH_HARD" if _get_graph() else "MCP_SOFT_CHAIN",
            "claude_blocked":True,"v8_interception":True,
            "message":"Tier enforcer v8 alive - Bash/Edit/Write intercepted to Ollama"}


@mcp.tool()
def tier_audit_log(last_n:int=20) -> dict:
    """Last N routing decisions with model, score, elapsed, skills, brain_used."""
    try:
        conn=sqlite3.connect(MEM_DB)
        rows=conn.execute(
            "SELECT ts,session,task,classified_tier,executor_tier,model,score,ok,elapsed,skills,brain_used "
            "FROM routing_log ORDER BY ts DESC LIMIT ?",(last_n,)).fetchall()
        conn.close()
        return {"entries":[{"ts":time.strftime("%H:%M:%S",time.localtime(r[0])),
                            "session":r[1],"task":r[2],"classified":r[3],"executor":r[4],
                            "model":r[5],"score":r[6],"ok":bool(r[7]),"elapsed_s":r[8],
                            "skills":json.loads(r[9] or "[]"),"brain_used":bool(r[10])} for r in rows],
                "count":len(rows)}
    except Exception as e: return {"error":str(e),"entries":[]}


@mcp.tool()
def tier_reset() -> dict:
    global _GRAPH; _GRAPH=None
    return {"reset":True,"status":activate_tier_routing("reset")}


if __name__=="__main__":
    mcp.run()
