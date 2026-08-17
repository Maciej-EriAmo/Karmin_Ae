#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_boot.py — JEDNA komenda startu sesji SE (Grok / CLI) w Karmin_Ae.

  cd C:\\Users\\drwis\\Karmin_Ae
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


def _configure_stdio_utf8() -> None:
    """Windows cp1250/cp852 kruszy się na „…” / PL w JSON — UTF-8 + replace."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def _safe_out(text: str, *, end: str = "\n") -> None:
    """Print odporny na UnicodeEncodeError (konsola Windows)."""
    try:
        sys.stdout.write(text + end)
        sys.stdout.flush()
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        raw = (text + end).encode(enc, errors="replace")
        try:
            sys.stdout.buffer.write(raw)
            sys.stdout.buffer.flush()
        except Exception:
            sys.stdout.write(text.encode("ascii", errors="replace").decode("ascii") + end)


def main(argv=None) -> int:
    _configure_stdio_utf8()
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
        default=True,
        help="B10: krotki handoff (domyslnie ON: 1 work, 3 facts, bez chronicle)",
    )
    p.add_argument(
        "--rich",
        action="store_true",
        help="pelnieszy handoff (wylacza compact; wiecej factow/chronicle/commands)",
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

    # settings: profile / memory_path (CLI --path wygrywa gdy inny niż default)
    try:
        from holon_settings import load_config, load_settings, resolve_memory_path

        _settings = load_settings()
        mem_path = resolve_memory_path(
            cli_path=args.path if args.path != str(ROOT / "holon_memory.json") else None,
            settings=_settings,
            root=ROOT,
        )
        _cfg = load_config(profile="agent", settings=_settings)
    except Exception:
        mem_path = args.path
        _cfg = None
        _settings = None

    am = AgentMemory.open(
        memory_path=mem_path,
        profile="agent",
        cfg=_cfg,
        use_settings=False,  # już załadowane wyżej
    )

    project = (args.project or "").strip()
    project_source = "cli" if project else ""
    if not project and not args.all_projects:
        project = am.read_last_project()
        if project:
            project_source = "last_or_env"

    # B13: wejdź do komory (zapisz poprzednią). --all-projects = bęben,
    # enforce 1 work *na komorę*, nigdy globalnie.
    entered = {}
    try:
        entered = am.enter(project)
        dem = {"demoted": int(entered.get("demoted") or 0)}
        if entered.get("restored_work") or dem.get("demoted"):
            am.save()
    except Exception:
        try:
            dem = am.enforce_max_work(project=project or "", max_active=1, save=True)
        except Exception:
            dem = {"demoted": 0}

    want_md = bool(args.md or args.out)
    hybrid = False if args.strict_delta else None
    # domyslnie compact; --rich = pelny; --full = digest (osobno)
    use_compact = False if args.rich else True
    try:
        if want_md:
            md = am.handoff_md(
                project=project,
                include_digest=bool(args.full),
                since=args.since or None,
                out_path=args.out or None,
                compact=use_compact,
                hybrid_since=hybrid,
            )
            if args.out and not args.no_banner:
                print(f"agent_boot: wrote markdown → {args.out} ({len(md)} chars)")
            elif args.out and args.no_banner:
                pass
            else:
                _safe_out(md if md.endswith("\n") else md)
            return 0
        handoff = am.handoff(
            project=project,
            include_digest=bool(args.full),
            since=args.since or None,
            compact=use_compact,
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
    if not use_compact:
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
            "enter": f'python holon_agent_memory.py --path "{mem_path}" enter --project {project or "Holon"}',
            "leave": f'python holon_agent_memory.py --path "{mem_path}" leave --work-text "…" --fact-text "…" --project {project or "Holon"}',
            "chambers": f'python holon_agent_memory.py --path "{mem_path}" chambers',
            "close": f'python holon_agent_memory.py --path "{mem_path}" close --work-text "…" --fact-text "…" --project {project or "Holon"}',
            "crystallize": f'python holon_agent_memory.py --path "{mem_path}" crystallize'
            + (f" --project {project}" if project else ""),
            "eval": f'python holon_agent_memory.py --path "{mem_path}" eval',
            "karmin_export": f'python holon_agent_memory.py --path "{mem_path}" karmin-export',
            "human_gui": f'python "{ROOT / "karmin_app.py"}"  # or START.cmd',
            "status": f'python "{ROOT / "karmin_app.py"}" --status',
            "configure": f'python "{ROOT / "holon_configure.py"}" gui',
        }
        boot_meta["protocol_short"] = [
            "1. Start: python agent_boot.py [--project X] [--since 24h] (compact ON)",
            "2. Pelnieszy handoff: --rich",
            "3. enter P -> praca -> leave/close (zapis komory)",
            "4. Obrót: enter Q (inna komora zostaje) albo koniec",
            "5. Store szumi: crystallize [--project X]",
            "6. Human: START.cmd | Chat: START_CHAT.cmd",
        ]
    boot_meta["handoff_compact"] = use_compact
    if dem.get("demoted"):
        boot_meta["work_demoted"] = dem
    if entered:
        boot_meta["enter"] = {
            "previous": entered.get("previous"),
            "switched": entered.get("switched"),
            "restored_work": entered.get("restored_work"),
        }
    # Dwa tory: agent=CLI, człowiek=GUI (norma UX poza power-userami)
    handoff["surfaces"] = {
        "agent": {
            "boot": "python agent_boot.py",
            "contract": "AGENTS.md",
            "assist": "python holon_agent_memory.py assist  # Ollama gemma3:4b helper",
            "assist_close": "python holon_agent_memory.py assist --task draft-close",
            "remember": 'python holon_agent_memory.py remember --fact "..."',
            "set_work": 'python holon_agent_memory.py set-work "..."',
            "enter": "python holon_agent_memory.py enter --project P",
            "leave": 'python holon_agent_memory.py leave --work-text "..." --fact-text "..." --project P',
            "chambers": "python holon_agent_memory.py chambers",
            "close": 'python holon_agent_memory.py close --work-text "..." --fact-text "..."',
            "status_json": "python karmin_app.py --status",
            "chat_brainstorm": "python karmin_app.py -c chat",
        },
        "human": {
            "gui": "START.cmd  OR  python karmin_app.py",
            "chat": "START_CHAT.cmd  OR  chat / brainstorm in panel",
            "configure": "python holon_configure.py gui",
            "help": "python holon_configure.py help",
            "note": "GUI is the normal human path; CLI is for power users and agents.",
        },
    }
    handoff["agent_boot"] = boot_meta

    payload = json.dumps(handoff, ensure_ascii=False, indent=2, default=str)

    if args.no_banner:
        _safe_out(payload)
        return 0

    _safe_out("=" * 60)
    _safe_out(" KARMIN_AE BOOT — Agent Edition SE (silnik Holon); nie cudza baza")
    _safe_out(" human UI: START.cmd / python karmin_app.py   |   agent: this boot")
    _safe_out("=" * 60)
    _safe_out(f" root    : {ROOT}")
    _safe_out(f" memory  : {Path(mem_path).resolve()}")
    proj_label = project or "(all)"
    if project_source:
        proj_label = f"{proj_label} [{project_source}]"
    _safe_out(f" project : {proj_label}")
    _safe_out(f" mode    : {handoff.get('mode')}")
    _safe_out(f" store   : {handoff.get('stats', {})}")
    if handoff.get("recommended_actions"):
        _safe_out(f" next    : {handoff['recommended_actions'][0]}")
    _safe_out("-" * 60)
    _safe_out(" HANDOFF JSON")
    _safe_out("-" * 60)
    _safe_out(payload)
    _safe_out("-" * 60)
    if not use_compact and "commands" in boot_meta:
        _safe_out(" DALEJ (kopiuj / odpalaj):")
        for k, cmd in boot_meta["commands"].items():
            _safe_out(f"  [{k}] {cmd}")
    _safe_out("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
