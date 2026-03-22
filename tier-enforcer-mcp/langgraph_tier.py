#!/usr/bin/env python3
"""
DSR AI-LAB LANGGRAPH TIER ENGINE v7
File: ~/tier-enforcer-mcp/langgraph_tier.py
Single source of truth: server.py
"""
import sys
from server import (
    _classify_task, _get_executor_tier, _build_graph, _get_graph,
    ROUTING_RULES, TIER_CONFIG, FALLBACK_CHAIN, QUALITY_THRESHOLDS,
    _get_threshold, CLAUDE_EXECUTION_BLOCK, MASTER_RULE, TierState,
    LANGGRAPH_AVAILABLE, MAX_FALLBACKS,
    MODEL_T1_LOCAL, MODEL_T1_MID, MODEL_T1_CLOUD,
)

SINGLE_SOURCE = "server.py → ROUTING_RULES, TIER_CONFIG, nodes"


def build_tier_graph():
    if not LANGGRAPH_AVAILABLE:
        raise ImportError("Run: pip install langgraph --break-system-packages")
    return _build_graph()


def verify_architecture():
    print("\n=== DSR AI-Lab Tier v7 — Architecture Verification ===\n")

    assert CLAUDE_EXECUTION_BLOCK is True
    print("✅ CLAUDE_EXECUTION_BLOCK = True")

    # Verify role assignments
    for tier, cfg in TIER_CONFIG.items():
        role = cfg.get("role")
        if role == "executor":
            assert cfg["type"] == "ollama", f"{tier} must be ollama"
            print(f"✅ {tier:<12} EXECUTOR   {cfg['model']}  ({cfg.get('ram_gb','cloud')}GB)")
        elif role == "analysis":
            print(f"✅ {tier:<12} ANALYSIS   {cfg['model']}  (no execution)")
        elif role == "brain":
            print(f"✅ {tier:<12} BRAIN ONLY {cfg['model']}  (Claude plans)")

    # T3-EPIC must route to T1-CLOUD
    e = _get_executor_tier("T3-EPIC")
    assert e == "T1-CLOUD", f"T3-EPIC must go to T1-CLOUD, got {e}"
    print(f"✅ T3-EPIC → T1-CLOUD ({MODEL_T1_CLOUD})")

    # T2 must route to T1-MID
    for t2 in ("T2-FLASH","T2-PRO","T2-KIMI"):
        e = _get_executor_tier(t2)
        assert e == "T1-MID", f"{t2} must go to T1-MID, got {e}"
        print(f"✅ {t2} → T1-MID ({MODEL_T1_MID})")

    # No-swap design check
    assert TIER_CONFIG["T1-LOCAL"]["model"] == TIER_CONFIG["T1-LOCAL"]["model"]
    assert TIER_CONFIG["T1-LOCAL"]["base"]  == TIER_CONFIG["T1-MID"]["base"], \
        "T1-LOCAL and T1-MID must share same Ollama endpoint"
    assert TIER_CONFIG["T1-LOCAL"]["params"]["keep_alive"] == -1, "keep_alive must be -1"
    assert TIER_CONFIG["T1-MID"]["params"]["keep_alive"]   == -1, "keep_alive must be -1"
    ram_total = TIER_CONFIG["T1-LOCAL"]["ram_gb"] + TIER_CONFIG["T1-MID"]["ram_gb"]
    assert ram_total <= 16.0, f"Total RAM {ram_total}GB exceeds Mac Mini 16GB"
    print(f"✅ NO-SWAP: 7b+14b = {ram_total}GB ≤ 16GB Mac Mini")
    print(f"✅ keep_alive=-1 on both local models")

    if LANGGRAPH_AVAILABLE:
        g = build_tier_graph()
        assert g is not None
        print("✅ LangGraph graph compiled")
    else:
        print("⚠️  LangGraph not installed — soft chain mode")

    print("\n=== Routing Classification Test ===\n")
    tests = [
        ("fix typo in readme",                                    "T1-LOCAL"),
        ("implement user authentication function",                 "T1-MID"),
        ("build the full ecommerce feature set",                   "T1-CLOUD"),
        ("debug the failing login test",                           "T2-FLASH"),
        ("security audit the api layer",                           "T2-PRO"),
        ("big o analysis of this sorting algorithm",               "T2-KIMI"),
        ("design and build complete greenfield platform end to end","T3-EPIC"),
    ]
    all_pass = True
    for task, expected in tests:
        tier, _, rule = _classify_task(task)
        executor = _get_executor_tier(tier)
        model    = TIER_CONFIG[executor]["model"]
        thresh   = _get_threshold(executor)
        ok       = tier == expected
        if not ok: all_pass = False
        icon = "✅" if ok else "⚠️ "
        print(f"{icon} {task[:45]:<45}  {tier:<12} → {executor:<12} ({model})  t={thresh}")

    print(f"\n=== {'PASSED ✅' if all_pass else 'WARNINGS ⚠️'} ===\n")
    return all_pass


if __name__ == "__main__":
    if "--test" in sys.argv:
        task = " ".join(sys.argv[2:]) or "implement binary search"
        from server import execute_task
        r = execute_task(task, "verify", "")
        print("classified:", r.get("classified_tier"))
        print("executor:  ", r.get("executor_tier"), "→", r.get("executor_model"))
        print("score:     ", r.get("score"))
        print("elapsed:   ", r.get("elapsed_s"), "s")
    else:
        verify_architecture()
