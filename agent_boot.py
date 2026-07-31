#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_boot.py — JEDNA komenda startu sesji SE (Grok / CLI) w holonOs.

  cd C:\\Users\\drwis\\holonOs
  python agent_boot.py
  python agent_boot.py --project Karmazyn
  python agent_boot.py --project Holon --full

Wypisuje:
  1) handoff JSON (holon-agent-handoff-v1) — kontekst z pamięci
  2) gotowe komendy Mneme / zapis
  3) ścieżki absolutne (żeby nie zgadywać)

Po bootcie agent NIE wymyśla kontekstu — korzysta z hitów handoff + Mneme-L.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# zawsze pracuj z katalogu repo (relative holon_memory.json)
os.chdir(ROOT)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Holon SE session boot for agent")
    p.add_argument(
        "--project",
        default="",
        help="filtr projektu (Karmazyn | Holon | …)",
    )
    p.add_argument(
        "--full",
        action="store_true",
        help="dołącz pełny digest w handoff (więcej tokenów)",
    )
    p.add_argument(
        "--path",
        default=str(ROOT / "holon_memory.json"),
        help="ścieżka holon_memory.json",
    )
    p.add_argument(
        "--no-banner",
        action="store_true",
        help="tylko JSON handoff (pipe-friendly)",
    )
    args = p.parse_args(argv)

    from holon_agent_memory import AgentMemory

    mem_path = args.path
    am = AgentMemory.open(memory_path=mem_path, profile="agent")
    handoff = am.handoff(
        project=args.project,
        include_digest=bool(args.full),
        max_work=5,
        max_facts=10,
    )

    # ścieżka „dla mnie” — bez zgadywania
    handoff["agent_boot"] = {
        "root": str(ROOT),
        "cwd_forced": str(Path.cwd()),
        "memory": str(Path(mem_path).resolve()),
        "links": str(Path(str(mem_path).replace(".json", "_links.json")).resolve()),
        "docs": {
            "agents": str(ROOT / "AGENTS.md"),
            "mneme": str(ROOT / "docs" / "MNEME.md"),
            "workflow": str(ROOT / "docs" / "AGENT_WORKFLOW.md"),
            "karmin": str(ROOT / "docs" / "KARMIN_BRIDGE.md"),
        },
        "commands": {
            "boot": f'python "{ROOT / "agent_boot.py"}"'
            + (f" --project {args.project}" if args.project else ""),
            "boot_full": f'python "{ROOT / "agent_boot.py"}" --full'
            + (f" --project {args.project}" if args.project else ""),
            "mneme_repl": f'python -m holon_mneme --path "{mem_path}" --repl',
            "mneme_recall": f'python -m holon_mneme --path "{mem_path}" "RECALL \\"…\\" TOP 5"',
            "remember_fact": f'python holon_agent_memory.py --path "{mem_path}" remember --fact "…"',
            "set_work": f'python holon_agent_memory.py --path "{mem_path}" set-work "…" --project {args.project or "Holon"}',
            "eval": f'python holon_agent_memory.py --path "{mem_path}" eval',
            "karmin_export": f'python holon_agent_memory.py --path "{mem_path}" karmin-export',
        },
        "protocol_short": [
            "1. Zawsze start: python agent_boot.py [--project X]",
            "2. Eksploracja: python -m holon_mneme (RECALL/NEAR/WALK/HOLD)",
            "3. Trwałe ustalenie: remember --fact lub HOLD fact …",
            "4. Aktywny wątek: set-work / HOLD work … PROJECT …",
            "5. Nie resetuj holon_memory.json; nie myl z KarmazynOs kodem",
            "6. KarmazynOs runtime: C:\\Users\\drwis\\KarmazynOs",
            "7. Karmin_DB skarbiec: C:\\Users\\drwis\\DBase (mirror opcjonalny)",
        ],
    }

    if args.no_banner:
        print(json.dumps(handoff, ensure_ascii=False, indent=2, default=str))
        return 0

    print("=" * 60)
    print(" HOLON AGENT BOOT — użyj TEJ pamięci, nie cudzej bazy w głowie")
    print("=" * 60)
    print(f" root    : {ROOT}")
    print(f" memory  : {Path(mem_path).resolve()}")
    print(f" project : {args.project or '(all)'}")
    print(f" store   : {handoff.get('stats', {})}")
    print("-" * 60)
    print(" HANDOFF JSON")
    print("-" * 60)
    print(json.dumps(handoff, ensure_ascii=False, indent=2, default=str))
    print("-" * 60)
    print(" DALEJ (kopiuj / odpalaj):")
    for k, cmd in handoff["agent_boot"]["commands"].items():
        print(f"  [{k}] {cmd}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
