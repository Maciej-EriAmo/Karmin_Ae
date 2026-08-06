#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_boot.py — JEDNA komenda startu sesji SE (Grok / CLI) w holonOs.

  cd C:\\Users\\drwis\\holonOs
  python agent_boot.py
  python agent_boot.py --project Karmazyn
  python agent_boot.py --project Holon --full
  python agent_boot.py --since 24h              # B1+B10 hybrid
  python agent_boot.py --compact --no-banner    # mało tokenów
  python agent_boot.py --strict-delta --since 24h

Wypisuje:
  1) handoff JSON (holon-agent-handoff-v1) — kontekst z pamięci
  2) gotowe komendy Mneme / zapis (pomijane przy --compact / --no-banner)
  3) ścieżki absolutne (żeby nie zgadywać)

Po bootcie agent NIE wymyśla kontekstu — korzysta z hitów handoff + Mneme-L.

B10: bez --project → HOLON_DEFAULT_PROJECT lub last_project z meta;
     --since dopełnia work spoza okna (hybrid), chyba że --strict-delta.
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
        help="filtr projektu (Karmazyn | Holon | …); puste = last/env",
    )
    p.add_argument(
        "--full",
        action="store_true",
        help="dołącz pełny digest w handoff (więcej tokenów)",
    )
    p.add_argument(
        "--since",
        default="",
        help="B1/B10: okno delty (24h | 7d | 90m | godziny); hybrid work spoza okna",
    )
    p.add_argument(
        "--strict-delta",
        action="store_true",
        help="B10: wyłącz hybrid — tylko work/facts w oknie --since",
    )
    p.add_argument(
        "--compact",
        action="store_true",
        help="B10: mniej tokenów (krótki protocol, ciaśniejsze limity, bez commands)",
    )
    p.add_argument(
        "--all-projects",
        action="store_true",
        help="nie podstawiaj last_project — handoff bez filtra projektu",
    )
    p.add_argument(
        "--md",
        action="store_true",
        help="B7: wypisz handoff jako Markdown zamiast JSON",
    )
    p.add_argument(
        "--out",
        default="",
        help="B7: zapisz Markdown do pliku (implikuje --md)",
    )
    p.add_argument(
        "--path",
        default=str(ROOT / "holon_memory.json"),
        help="ścieżka holon_memory.json",
    )
    p.add_argument(
        "--no-banner",
        action="store_true",
        help="tylko JSON/MD handoff (pipe-friendly)",
    )
    args = p.parse_args(argv)

    from holon_agent_memory import AgentMemory

    mem_path = args.path
    am = AgentMemory.open(memory_path=mem_path, profile="agent")

    project = (args.project or "").strip()
    project_source = "cli" if project else ""
    if not project and not args.all_projects:
        project = am.read_last_project()
        if project:
            project_source = "last_or_env"

    want_md = bool(args.md or args.out)
    hybrid = False if args.strict_delta else None
    try:
        if want_md:
            md = am.handoff_md(
                project=project,
                include_digest=bool(args.full),
                since=args.since or None,
                out_path=args.out or None,
                compact=bool(args.compact),
                hybrid_since=hybrid,
            )
            if args.out and not args.no_banner:
                print(f"agent_boot: wrote markdown → {args.out} ({len(md)} chars)")
            elif args.out and args.no_banner:
                pass
            else:
                sys.stdout.write(md if md.endswith("\n") else md + "\n")
            return 0
        handoff = am.handoff(
            project=project,
            include_digest=bool(args.full),
            since=args.since or None,
            compact=bool(args.compact),
            hybrid_since=hybrid,
        )
    except ValueError as e:
        print(f"agent_boot: {e}", file=sys.stderr)
        return 2

    # ścieżka „dla mnie” — bez zgadywania
    boot_meta = {
        "root": str(ROOT),
        "cwd_forced": str(Path.cwd()),
        "memory": str(Path(mem_path).resolve()),
        "links": str(Path(str(mem_path).replace(".json", "_links.json")).resolve()),
        "project_resolved": project or None,
        "project_source": project_source or ("all" if args.all_projects else "none"),
        "docs": {
            "agents": str(ROOT / "AGENTS.md"),
            "mneme": str(ROOT / "docs" / "MNEME.md"),
            "workflow": str(ROOT / "docs" / "AGENT_WORKFLOW.md"),
            "karmin": str(ROOT / "docs" / "KARMIN_BRIDGE.md"),
            "b10": str(ROOT / "docs" / "B10_HANDOFF.md"),
        },
    }
    if not args.compact:
        boot_meta["commands"] = {
            "boot": f'python "{ROOT / "agent_boot.py"}"'
            + (f" --project {project}" if project else ""),
            "boot_delta": f'python "{ROOT / "agent_boot.py"}" --since 24h'
            + (f" --project {project}" if project else ""),
            "boot_compact": f'python "{ROOT / "agent_boot.py"}" --compact --no-banner'
            + (f" --project {project}" if project else ""),
            "boot_md": f'python "{ROOT / "agent_boot.py"}" --md'
            + (f" --project {project}" if project else ""),
            "boot_full": f'python "{ROOT / "agent_boot.py"}" --full'
            + (f" --project {project}" if project else ""),
            "mneme_repl": f'python -m holon_mneme --path "{mem_path}" --repl',
            "mneme_recall": f'python -m holon_mneme --path "{mem_path}" "RECALL \\"…\\" TOP 5"',
            "remember_fact": f'python holon_agent_memory.py --path "{mem_path}" remember --fact "…"',
            "set_work": f'python holon_agent_memory.py --path "{mem_path}" set-work "…" --project {project or "Holon"}',
            "close": f'python holon_agent_memory.py --path "{mem_path}" close --work-text "…" --fact-text "…" --project {project or "Holon"}',
            "crystallize": f'python holon_agent_memory.py --path "{mem_path}" crystallize'
            + (f" --project {project}" if project else ""),
            "eval": f'python holon_agent_memory.py --path "{mem_path}" eval',
            "karmin_export": f'python holon_agent_memory.py --path "{mem_path}" karmin-export',
        }
        boot_meta["protocol_short"] = [
            "1. Start: python agent_boot.py [--project X] [--since 24h] [--compact]",
            "2. Hybrid --since dopełnia work spoza okna (wyłącz: --strict-delta)",
            "3. Eksploracja: suggested_mneme w handoff lub python -m holon_mneme",
            "4. Trwałe: remember --fact / close --fact-text",
            "5. Wątek: set-work (domyślnie 1 aktywny) / close --work-text",
            "6. Store szumi: crystallize [--project X]",
            "7. Nie resetuj holon_memory.json; Holon ≠ KarmazynOs kod",
            "8. KarmazynOs: C:\\Users\\drwis\\KarmazynOs",
        ]
    handoff["agent_boot"] = boot_meta

    if args.no_banner:
        print(json.dumps(handoff, ensure_ascii=False, indent=2, default=str))
        return 0

    print("=" * 60)
    print(" HOLON AGENT BOOT — użyj TEJ pamięci, nie cudzej bazy w głowie")
    print("=" * 60)
    print(f" root    : {ROOT}")
    print(f" memory  : {Path(mem_path).resolve()}")
    proj_label = project or "(all)"
    if project_source:
        proj_label = f"{proj_label} [{project_source}]"
    print(f" project : {proj_label}")
    print(f" mode    : {handoff.get('mode')}")
    print(f" store   : {handoff.get('stats', {})}")
    if handoff.get("recommended_actions"):
        print(f" next    : {handoff['recommended_actions'][0]}")
    print("-" * 60)
    print(" HANDOFF JSON")
    print("-" * 60)
    print(json.dumps(handoff, ensure_ascii=False, indent=2, default=str))
    print("-" * 60)
    if not args.compact and "commands" in boot_meta:
        print(" DALEJ (kopiuj / odpalaj):")
        for k, cmd in boot_meta["commands"].items():
            print(f"  [{k}] {cmd}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
