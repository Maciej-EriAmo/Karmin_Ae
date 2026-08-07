#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
karmin_session.py — najprostszy rytuał pamięci SE (4 komendy).

  python karmin_session.py start [--project P]
  python karmin_session.py status [--project P]
  python karmin_session.py fact "trwale ustalenie" [--project P]
  python karmin_session.py work "aktywny watek" [--project P]
  python karmin_session.py done --fact "..." --work "..." [--project P]
  python karmin_session.py done          # zapyta interaktywne

Czego NIE musisz: crystallize, Mneme, configure, presetow — to advanced.

Agent: nadal wolno uzywac agent_boot.py (to samo co start --json).
Czlowiek: START.cmd (panel) ALBO te 4 komendy w terminalu.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def _project(cli: str) -> str:
    p = (cli or "").strip()
    if p:
        return p
    try:
        from holon_settings import load_settings

        sp = str(load_settings().get("default_project") or "").strip()
        if sp:
            return sp
    except Exception:
        pass
    try:
        from holon_agent_memory import AgentMemory

        am = AgentMemory.open(profile="agent")
        return am.read_last_project() or ""
    except Exception:
        return ""


def _am(path: str = "holon_memory.json"):
    from holon_agent_memory import AgentMemory

    return AgentMemory.open(memory_path=path, profile="agent")


def cmd_start(args: argparse.Namespace) -> int:
    """Boot handoff (compact) — to samo co agent_boot."""
    from agent_boot import main as boot_main

    argv: List[str] = ["--no-banner"] if args.json else []
    if args.rich:
        argv.append("--rich")
    if args.since:
        argv.extend(["--since", args.since])
    if args.project:
        argv.extend(["--project", args.project])
    elif not args.all_projects:
        proj = _project("")
        if proj:
            argv.extend(["--project", proj])
    if args.all_projects:
        argv.append("--all-projects")
    return int(boot_main(argv) or 0)


def cmd_status(args: argparse.Namespace) -> int:
    from karmin_app import surface_status

    proj = _project(args.project)
    st = surface_status(proj)
    if args.json:
        print(json.dumps(st, ensure_ascii=False, indent=2, default=str))
        return 0
    print(f"project : {st.get('project') or '(all)'}")
    print(f"doctor  : {st.get('doctor_score')}%  ok={st.get('doctor_ok')}")
    print(f"stats   : store={st.get('stats', {}).get('store')} "
          f"facts={st.get('stats', {}).get('facts')} work={st.get('stats', {}).get('work')}")
    print("work:")
    for w in st.get("active_work") or ["(brak — ustaw: session work \"...\")"]:
        print(f"  • {str(w)[:200]}")
    print("facts (top):")
    for f in (st.get("key_facts") or [])[:3]:
        print(f"  • {str(f)[:160]}")
    acts = st.get("recommended_actions") or []
    if acts:
        print("dalej:")
        for a in acts[:3]:
            print(f"  → {a}")
    print()
    print("rytual: start → work/fact → done   |   panel: START.cmd")
    return 0


def cmd_fact(args: argparse.Namespace) -> int:
    text = (args.text or "").strip()
    if not text:
        print("uzycie: session fact \"tresc\" [--project P]", file=sys.stderr)
        return 2
    proj = _project(args.project)
    am = _am(args.path)
    content = text if not proj or text.startswith("[") else f"[{proj}] {text}"
    item = am.remember(content, kind="fact")
    if not args.no_save:
        am.save()
    if proj:
        am.touch_last_project(proj)
    print(f"OK fact id={getattr(item, 'id', '')[:8]}…")
    print(content[:200])
    return 0


def cmd_work(args: argparse.Namespace) -> int:
    text = (args.text or "").strip()
    if not text:
        print("uzycie: session work \"tresc\" [--project P]", file=sys.stderr)
        return 2
    proj = _project(args.project)
    am = _am(args.path)
    item = am.set_work(text, project=proj, max_active=1)
    if not args.no_save:
        am.save()
    print(f"OK work id={getattr(item, 'id', '')[:8]}… (max 1 aktywny)")
    print((item.content or "")[:200])
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    """close sesji — minimalne domkniecie."""
    proj = _project(args.project)
    fact = (args.fact or args.fact_text or "").strip()
    work = (args.work or args.work_text or "").strip()
    if not fact and not work and sys.stdin.isatty():
        print("Koniec sesji — krotko (Enter = puste):")
        if proj:
            print(f"  project=[{proj}]")
        work = input("  next work > ").strip()
        fact = input("  fact summary > ").strip()
    if not fact and not work:
        print("nic do zapisu — podaj --fact i/lub --work (albo tryb interaktywny)", file=sys.stderr)
        return 2
    am = _am(args.path)
    rep = am.close(work=work, fact=fact, project=proj, max_active=1, save=not args.no_save)
    print("OK done (close)")
    if work:
        print(f"  work: {work[:160]}")
    if fact:
        print(f"  fact: {fact[:160]}")
    print(f"  saved={rep.get('saved')} project={proj or rep.get('project')}")
    return 0 if rep.get("ok") else 1


def cmd_help(_args: argparse.Namespace) -> int:
    print(
        """
Karmin_Ae — prosty rytual pamieci (session)

  start [--project P] [--since 24h] [--json]   boot / handoff
  status [--project P]                        co jest w pamieci
  fact  "..." [--project P]                   trwale
  work  "..." [--project P]                   1 aktywny watek
  done  --fact "..." --work "..."             koniec sesji (close)
  done                                        zapyta o fact/work

Przyklad dnia:
  python karmin_session.py start --project Karmazyn
  python karmin_session.py work "kcc: nastepny krok TB.4 lub C-ABI"
  ... praca w KarmazynOs ...
  python karmin_session.py fact "verify_kcc OK; pauza Tor B"
  python karmin_session.py done --work "opcjonalnie C-ABI" --fact "kcc 0.4 green"

Nie musisz na co dzien: crystallize, Mneme, configure, --rich.
Panel: START.cmd   Chat: START_CHAT.cmd   Agent: to samo co start
""".strip()
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    _utf8()
    p = argparse.ArgumentParser(
        prog="karmin_session",
        description="Prosty rytual pamieci SE: start / status / fact / work / done",
    )
    p.add_argument("--path", default="holon_memory.json", help="holon_memory.json")
    sub = p.add_subparsers(dest="cmd", required=False)

    sp = sub.add_parser("help", help="ten opis")
    sp.set_defaults(func=cmd_help)

    sp = sub.add_parser("start", aliases=["boot"], help="boot handoff (compact)")
    sp.add_argument("--project", "-p", default="")
    sp.add_argument("--since", default="")
    sp.add_argument("--json", action="store_true", help="tylko JSON (jak agent_boot --no-banner)")
    sp.add_argument("--rich", action="store_true")
    sp.add_argument("--all-projects", action="store_true")
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("status", help="krotki stan pamieci")
    sp.add_argument("--project", "-p", default="")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("fact", help="zapisz fact")
    sp.add_argument("text", nargs="?", default="")
    sp.add_argument("--project", "-p", default="")
    sp.add_argument("--no-save", action="store_true")
    sp.set_defaults(func=cmd_fact)

    sp = sub.add_parser("work", help="ustaw 1 work")
    sp.add_argument("text", nargs="?", default="")
    sp.add_argument("--project", "-p", default="")
    sp.add_argument("--no-save", action="store_true")
    sp.set_defaults(func=cmd_work)

    sp = sub.add_parser("done", aliases=["end", "close"], help="close sesji")
    sp.add_argument("--fact", default="", help="fact summary")
    sp.add_argument("--work", default="", help="next work")
    sp.add_argument("--fact-text", default="")
    sp.add_argument("--work-text", default="")
    sp.add_argument("--project", "-p", default="")
    sp.add_argument("--no-save", action="store_true")
    sp.set_defaults(func=cmd_done)

    args = p.parse_args(argv)
    if not getattr(args, "path", None):
        args.path = "holon_memory.json"
    if not args.cmd:
        return cmd_help(args)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
