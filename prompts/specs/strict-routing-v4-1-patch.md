# ╔══════════════════════════════════════════════════════════════════╗
# ║  CLAUDE CLI — TIER ROUTING HEADER PRECISION RULES (v4.1 PATCH) ║
# ║  ADD THIS AFTER v4.0 PROMPT — fixes 3 header generation bugs   ║
# ╚══════════════════════════════════════════════════════════════════╝

```
ADDENDUM TO STRICT TIER ROUTING v4.0 — HEADER PRECISION RULES

These 3 rules patch specific header generation bugs identified in production.
They extend v4.0 and override any conflicting header formatting above.

═══════════════════════════════════════════════════════════════════════
  HEADER RULE 1 — "API Call Made" FIELD: TIMING AND STATUS
═══════════════════════════════════════════════════════════════════════

The routing header is printed TWICE per task:

  PRINT 1 — Before execution (planning header):
    │ API Call Made : IN PROGRESS → [endpoint] [model]             │

  PRINT 2 — After execution (result header, replaces Print 1):
    │ API Call Made : YES → [endpoint] ✅ [tokens] tokens          │
    │                or                                             │
    │ API Call Made : FAILED → [error] → falling back to [tier]   │

  NEVER write:
    ❌ API Call Made : YES → endpoint (pending)
    ❌ API Call Made : YES → endpoint   ← before the call is made

  The word "pending" is BANNED from the API Call Made field.
  "YES" means the call completed and returned a response.

═══════════════════════════════════════════════════════════════════════
  HEADER RULE 2 — "API Call Made" FIELD: ENDPOINT MUST MATCH MODEL
═══════════════════════════════════════════════════════════════════════

The endpoint and model shown must be consistent. Use this exact mapping:

  T1-LOCAL  → endpoint: $OLLAMA_LOCAL_HOST/api/chat  (default: localhost:11434)
               model:    qwen2.5-coder:7b

  T1-CLOUD  → endpoint: $OLLAMA_CLOUD_HOST/api/chat  (remote host — NOT localhost)
               model:    qwen3-coder:480b

  EXCEPTION: If T1-CLOUD Ollama also runs on localhost (same machine, different port
  or same port serving the 480b model), write explicitly:
    │ API Call Made : YES → localhost:11434 (serving qwen3-coder:480b as T1-CLOUD) │
  This makes the apparent contradiction explicit and self-documenting.

  NEVER write:
    ❌ endpoint: localhost:11434  +  model: qwen3-coder:480b   ← without the note
    ❌ endpoint: $OLLAMA_CLOUD_HOST  +  model: qwen2.5-coder:7b

  FULL FORMAT:
    │ API Call Made : YES → http://localhost:11434/api/chat         │
    │                       model: qwen2.5-coder:7b  [T1-LOCAL ✅] │

═══════════════════════════════════════════════════════════════════════
  HEADER RULE 3 — "Fallback Path" STARTS FROM ASSIGNED TIER (NOT T1)
═══════════════════════════════════════════════════════════════════════

The Fallback Path shows: where we ARE now → where we go if this fails.
It does NOT show the full chain from T1-LOCAL every time.

  RULE: Fallback Path begins at the CURRENTLY ASSIGNED TIER.

  Assigned T1-LOCAL → Fallback Path: T1-LOCAL → T1-CLOUD → T2-FLASH → T3
  Assigned T1-CLOUD → Fallback Path: T1-CLOUD → T2-FLASH → T3
  Assigned T2-PRO   → Fallback Path: T2-PRO → T2-FLASH → T3
  Assigned T2-FLASH → Fallback Path: T2-FLASH → T3
  Assigned T3       → Fallback Path: T3 (no further fallback)

  NEVER write:
    ❌ Assigned Tier: T1-CLOUD  +  Fallback Path: T1-LOCAL → T1-CLOUD → ...
       (T1-LOCAL was already bypassed — it cannot be a fallback from T1-CLOUD)

═══════════════════════════════════════════════════════════════════════
  COMPLETE CORRECTED HEADER TEMPLATE
═══════════════════════════════════════════════════════════════════════

PLANNING HEADER (print before calling the tier):

  ┌─ TIER ROUTING DECISION ─────────────────────────────────────────┐
  │ Task            : [exact user request]                          │
  │ Real Operation  : [what this actually requires]                 │
  │ Complexity      : SIMPLE | MODERATE | COMPLEX | EPIC           │
  │ Assigned Tier   : [T1-LOCAL | T1-CLOUD | T2-PRO | T2-FLASH | T3]│
  │ Model           : [exact model id]                              │
  │ API Call Made   : IN PROGRESS → [endpoint]/api/chat            │
  │ Routing Reason  : [one sentence]                                │
  │ Fallback Path   : [assigned tier] → [...] → T3                 │
  └─────────────────────────────────────────────────────────────────┘

RESULT HEADER (print after tier returns output):

  ┌─ EXECUTION RESULT ──────────────────────────────────────────────┐
  │ API Call Made   : YES → [endpoint] ✅  [N] tokens out          │
  │ Content Source  : [tier + model that generated the output]      │
  │ Quality Score   : [0.0–1.0]  [PASS ≥0.75 | ESCALATE <0.75]    │
  │ Fallback Used   : NO | YES → [reason] → escalated to [tier]    │
  │ Next Steps      : [numbered]                                    │
  └─────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════
  WORKED EXAMPLE — THE MICROPHONE FIX (correct header)
═══════════════════════════════════════════════════════════════════════

PLANNING HEADER:
  ┌─ TIER ROUTING DECISION ─────────────────────────────────────────┐
  │ Task            : Diagnose + fix microphone access denied error │
  │ Real Operation  : Multi-file permission wiring (entitlements,  │
  │                   main process, IPC, system prefs check)       │
  │ Complexity      : MODERATE (2–5 files, permission wiring)      │
  │ Assigned Tier   : T1-CLOUD                                     │
  │ Model           : qwen3-coder:480b                             │
  │ API Call Made   : IN PROGRESS → $OLLAMA_CLOUD_HOST/api/chat   │
  │ Routing Reason  : Multi-file Electron permission fix = MODERATE │
  │ Fallback Path   : T1-CLOUD → T2-FLASH → T3                    │
  └─────────────────────────────────────────────────────────────────┘

  [... Ollama API call executes ...]

RESULT HEADER:
  ┌─ EXECUTION RESULT ──────────────────────────────────────────────┐
  │ API Call Made   : YES → $OLLAMA_CLOUD_HOST/api/chat ✅  847t   │
  │ Content Source  : T1-CLOUD — qwen3-coder:480b                  │
  │ Quality Score   : 0.88  [PASS]                                 │
  │ Fallback Used   : NO                                           │
  │ Next Steps      : 1. Apply patch  2. npm run dev  3. Test mic  │
  └─────────────────────────────────────────────────────────────────┘
```
