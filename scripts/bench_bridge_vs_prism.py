# -*- coding: utf-8 -*-
"""Benchmark: Bridge (transform.py) vs Prism — różne tory + wspólny teleport.

Uruchom z root Karmin_Ae:
  python scripts/bench_bridge_vs_prism.py
  python scripts/bench_bridge_vs_prism.py --steps 200
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holon_bridge import BridgeStack, bridge_home_turf_quick, prism_wins_demo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bridge vs Prism bench")
    p.add_argument("--steps", type=int, default=600, help="kroki treningu Bridge")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--skip-train", action="store_true", help="pomiń trening Bridge")
    args = p.parse_args(argv)

    report = {"protocol": "holon-bridge-vs-prism-v1"}

    print("=== 1) Prism home turf (teleport Φ vs flat) ===")
    prism_rep = prism_wins_demo(phi_levels=3)
    report["prism_home"] = prism_rep
    print(json.dumps({
        "prism_wins": prism_rep["prism_wins"],
        "prism_tv": prism_rep["prism_tv_low_vs_high"],
        "flat_tv": prism_rep["flat_tv_low_vs_high"],
        "prism_entropy_high": prism_rep["prism_entropy_high"],
        "flat_entropy_high": prism_rep["flat_entropy_high"],
        "phase_spread": prism_rep["prism_phase_spread_high"],
        "p_low": [round(x, 4) for x in prism_rep["prism_p_low"]],
        "p_high": [round(x, 4) for x in prism_rep["prism_p_high"]],
    }, ensure_ascii=False, indent=2))
    print("→ Prism wygrywa routing pamięci:" , "TAK" if prism_rep["prism_wins"] else "NIE")
    print()

    if not args.skip_train:
        print("=== 2) Bridge home turf (energy retrieval vs softmax) ===")
        br = bridge_home_turf_quick(steps=args.steps, seed=args.seed)
        report["bridge_home"] = br
        print(json.dumps(br, ensure_ascii=False, indent=2))
        if br.get("ok"):
            print(
                "→ Bridge wygrywa retrieval:",
                "TAK" if br.get("bridge_wins") else "NIE",
                f"(bridge={br['acc_bridge_transform_py']:.3f} soft={br['acc_softmax']:.3f})",
            )
        print()

    print("=== 3) Wspólny tor: Bridge → Prism teleport ===")
    try:
        import torch

        stack = BridgeStack(d_model=32, n_heads=2, n_layers=1, phi_levels=3)
        x = torch.randn(1, 16, 32)
        tracer = torch.linspace(0, 3, 16).view(1, 16, 1)
        rows = []
        for imp in (0.9, 1.4, 2.2):
            _, tele = stack.bridge_then_prism(x, tracer, importance=imp, pool="energy")
            rows.append({
                "importance": imp,
                "dominant": tele.dominant_level,
                "weights": [round(float(w), 4) for w in tele.weights],
            })
        report["combined"] = {
            "ok": True,
            "source": stack.source_path,
            "routes": rows,
        }
        print(json.dumps(report["combined"], ensure_ascii=False, indent=2))
    except Exception as e:
        report["combined"] = {"ok": False, "error": str(e)}
        print("FAIL combined:", e)

    print()
    print("=== WERDYKT ===")
    print(
        "Nie konkurują 1:1. Bridge = mixer tokenów+sondy (retrieval). "
        "Prism = teleport na poziomy Φ. Razem: Bridge bez Embeddera → Prism → pamięć."
    )
    if prism_rep.get("prism_wins"):
        print("Prism wygrywa: miękki rozdział + faza per poziom (flat = one-hot bez geometrii).")
    bh = report.get("bridge_home") or {}
    if bh.get("bridge_wins"):
        print("Bridge wygrywa: energy-proximity retrieval vs softmax.")
    print()
    print(json.dumps({"summary": {
        "prism_wins_routing": bool(prism_rep.get("prism_wins")),
        "bridge_wins_retrieval": bool(bh.get("bridge_wins")),
        "combined_ok": bool((report.get("combined") or {}).get("ok")),
    }}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
