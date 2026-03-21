#!/usr/bin/env python3
"""
DSR AI-LAB LANGGRAPH TIER ENGINE v6.1
File: ~/tier-enforcer-mcp/langgraph_tier.py

FIX: removed QUALITY_THRESHOLD (doesn't exist in v6_fixed).
     imports QUALITY_THRESHOLDS + _get_threshold instead.
Single source of truth: server.py
"""
import sys, os

from server import (
    _classify_task,
    _get_executor_tier,
    _build_graph,
    _get_graph,
    ROUTING_RULES,
    TIER_CONFIG,
    FALLBACK_CHAIN,
    QUALITY_THRESHOLDS,       # FIX: was QUALITY_THRESHOLD (singular) — doesn't exist
    _get_threshold,            # FIX: use the per-tier threshold function
    CLAUDE_EXECUTION_BLOCK,
    MASTER_RULE,
    TierState,
    LANGGRAPH_AVAILABLE,
    MAX_FALLBACKS,
)

SINGLE_SOURCE = "server.py → ROUTING_RULES, TIER_CONFIG, nodes"


def build_tier_graph():
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "LangGraph not installed.\n"
            "Fix: pip install langgraph --break-system-packages"
        )
    return _build_graph()


def verify_architecture():
    print("\n=== ARCHITECTURE VERIFICATION ===\n")

    assert CLAUDE_EXECUTION_BLOCK is True
    print("✅ CLAUDE_EXECUTION_BLOCK = True")

    for tier, cfg in TIER_CONFIG.items():
        role = cfg.get("role")
        if role == "executor":
            assert cfg["type"] == "ollama", f"{tier} executor must be ollama"
            print(f"✅ {tier} → EXECUTOR   {cfg['model']}")
        elif role == "analysis":
            print(f"✅ {tier} → ANALYSIS   {cfg['model']}")
        elif role == "brain":
            print(f"✅ {tier} → BRAIN ONLY (Claude, no execution)")

    t3_exec = _get_executor_tier("T3-EPIC")
    assert t3_exec == "T1-CLOUD", f"T3-EPIC must go to T1-CLOUD, got {t3_exec}"
    print(f"✅ T3-EPIC executor = T1-CLOUD ({TIER_CONFIG['T1-CLOUD']['model']})")

    for t2 in ("T2-FLASH", "T2-PRO", "T2-KIMI"):
        e = _get_executor_tier(t2)
        assert e == "T1-MID", f"{t2} executor must be T1-MID, got {e}"
        print(f"✅ {t2} analysis → T1-MID executes")

    if LANGGRAPH_AVAILABLE:
        g = build_tier_graph()
        assert g is not None
        print("✅ LangGraph graph compiled")
    else:
        print("⚠️  LangGraph not installed — soft chain mode")

    print("\n=== ROUTING CLASSIFICATION TEST ===\n")
    tests = [
        ("update readme",                                              "T1-LOCAL"),
        ("implement login function",                                   "T1-MID"),
        ("build the full auth module",                                 "T1-CLOUD"),
        ("debug the failing test",                                     "T2-FLASH"),
        ("security audit the api layer",                               "T2-PRO"),
        ("big o analysis of this algorithm",                           "T2-KIMI"),
        ("design and build complete greenfield platform from scratch", "T3-EPIC"),
    ]
    all_pass = True
    for task, expected in tests:
        tier, cfg, _ = _classify_task(task)
        executor     = _get_executor_tier(tier)
        model        = TIER_CONFIG[executor]["model"]
        threshold    = _get_threshold(executor)
        ok           = tier == expected
        if not ok:
            all_pass = False
        icon = "✅" if ok else "⚠️ "
        print(f"{icon} {task[:45]:<45}  {tier:<12} → {executor:<12} ({model})  threshold={threshold}")

    print(f"\n=== {'PASSED ✅' if all_pass else 'HAS WARNINGS ⚠️'} ===\n")
    return all_pass


def run_test_task(task="implement a binary search function"):
    from server import execute_task
    print(f"\nTest task: '{task}'")
    r = execute_task(task, session_id="verify-test", context="")
    print(f"  mode:           {r.get('mode')}")
    print(f"  classified:     {r.get('classified_tier')}")
    print(f"  executor_tier:  {r.get('executor_tier')}")
    print(f"  executor_model: {r.get('executor_model')}")
    print(f"  claude_blocked: {r.get('claude_blocked')}")
    print(f"  score:          {r.get('score')}")
    print(f"  ok:             {r.get('ok')}")
    if r.get("banner"):
        print(f"  banner:         {r['banner']}")
    return r


if __name__ == "__main__":
    if "--test" in sys.argv:
        task = " ".join(sys.argv[2:]) or "implement a binary search function"
        run_test_task(task)
    else:
        verify_architecture()
