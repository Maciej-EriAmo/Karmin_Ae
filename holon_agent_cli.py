# -*- coding: utf-8 -*-
"""holon_agent_cli.py — CLI dispatcher dla ``python holon_agent_memory.py <cmd>``.

Wydzielone z holon_agent_memory.py (był 1 plik >2600 linii mieszający bibliotekę
``AgentMemory`` z argparse/dispatch). Ten plik nie zawiera żadnej logiki pamięci —
tylko parsowanie argumentów i wołanie metod ``AgentMemory``. Biblioteka
(``AgentMemory``, ``AGENT_SEED``, helpery projektu) zostaje w holon_agent_memory.py,
żeby `from holon_agent_memory import AgentMemory` (używane w kilkunastu innych
modułach) się nie zmieniało.

Uruchamiane przez ``if __name__ == "__main__"`` na dole holon_agent_memory.py —
``python holon_agent_memory.py ...`` działa bez zmian, tylko dispatch mieszka
tutaj.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from holon_agent_memory import AgentMemory


def _configure_stdio_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def main(argv: Optional[List[str]] = None) -> int:
    _configure_stdio_utf8()
    p = argparse.ArgumentParser(description="Holon agent memory (Grok/CLI)")
    p.add_argument("cmd", choices=[
        "digest", "remember", "recall", "seed", "stats", "status", "collab-test", "eval",
        "ablation", "llm-slot", "handoff", "handoff-md", "set-work", "close",
        "enter", "leave", "chambers", "separate",
        "boot", "crystallize", "watch-remember",
        "assist", "helper",  # Gemini/SE helper for agent (not chat)
        "karmin-sync", "karmin-export", "karmin-import", "karmin-slot",
        "entangle",
    ])
    p.add_argument("text", nargs="?", default="",
                   help="treść (remember/set-work) lub zapytanie (recall)")
    p.add_argument("--fact", dest="as_fact", action="store_true")
    p.add_argument("--work", dest="as_work", action="store_true")
    p.add_argument(
        "--fact-text",
        default="",
        help="close: treść fact summary (osobno od flagi --fact)",
    )
    p.add_argument(
        "--work-text",
        default="",
        help="close: treść work (alternatywa do positional text)",
    )
    p.add_argument("--kind", default="", help="fact|work|note")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--path", default="holon_memory.json")
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--project", default="",
                   help="filtr / prefiks projektu (Holon, Karmazyn, …)")
    p.add_argument("--no-digest", action="store_true",
                   help="handoff: bez pełnego digest w JSON")
    p.add_argument(
        "--since",
        default="",
        help="handoff B1/B10: okno delty — 24h | 7d | 90m | godziny (np. 12)",
    )
    p.add_argument(
        "--strict-delta",
        action="store_true",
        help="handoff: wyłącz B10 hybrid (tylko work w oknie --since)",
    )
    p.add_argument(
        "--compact",
        action="store_true",
        help="handoff: mniej tokenów (krótki protocol, ciaśniejsze limity)",
    )
    p.add_argument(
        "--max-active",
        type=int,
        default=None,
        help="set-work / close / crystallize: ile work zostawić (domyślnie 1)",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="crystallize: raport bez mutacji store")
    p.add_argument("--sim", type=float, default=None,
                   help="crystallize: próg similarity (domyślnie z Config)")
    p.add_argument(
        "--cross-project",
        action="store_true",
        help="crystallize: pozwól scalać między komorami (domyślnie wyłączone)",
    )
    p.add_argument("--snapshot", default="holon_karmin_snapshot.json",
                   help="ścieżka snapshotu Karmin (export/import)")
    p.add_argument(
        "--out",
        default="",
        help="handoff-md: zapisz Markdown do pliku (np. handoff.md)",
    )
    p.add_argument(
        "--inbox",
        default="remember_inbox.jsonl",
        help="watch-remember: ścieżka JSONL inbox (B4)",
    )
    p.add_argument(
        "--task",
        default="orient",
        help="assist: orient|hygiene|draft-close|ask (Gemini helper)",
    )
    p.add_argument(
        "--ask",
        default="",
        help="assist: pytanie do pomocnika Gemini",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="assist/llm-slot: surowy JSON",
    )
    p.add_argument(
        "--poll",
        type=float,
        default=1.0,
        help="watch-remember: interwał poll (s)",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="watch-remember: jeden poll i wyjście",
    )
    args = p.parse_args(argv)

    am = AgentMemory.open(memory_path=args.path)

    if args.cmd == "digest":
        print(am.digest(project=args.project))
        return 0

    if args.cmd == "status":
        # czytelny status dla człowieka i agenta (JSON); alias Control Center
        from karmin_app import surface_status

        print(
            json.dumps(
                surface_status(args.project),
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0

    if args.cmd == "boot":
        # alias → agent_boot.py (jedna ścieżka dla agenta)
        from agent_boot import main as boot_main
        boot_argv = []
        if args.project:
            boot_argv.extend(["--project", args.project])
        if args.since:
            boot_argv.extend(["--since", args.since])
        if args.strict_delta:
            boot_argv.append("--strict-delta")
        if args.compact:
            boot_argv.append("--compact")
        if not args.no_digest:
            boot_argv.append("--full")
        boot_argv.extend(["--path", args.path])
        return int(boot_main(boot_argv) or 0)

    if args.cmd == "handoff":
        try:
            h = am.handoff(
                project=args.project,
                include_digest=not args.no_digest,
                since=args.since or None,
                compact=bool(args.compact),
                hybrid_since=False if args.strict_delta else None,
            )
        except ValueError as e:
            print(f"handoff: {e}", file=sys.stderr)
            return 2
        print(json.dumps(h, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.cmd == "handoff-md":
        # B7: Markdown. Domyślnie bez digest; dodaj digest: handoff-md digest
        try:
            want_dig = (args.text or "").strip().lower() in (
                "digest", "full", "with-digest",
            ) and not args.no_digest
            md = am.handoff_md(
                project=args.project,
                include_digest=want_dig,
                since=args.since or None,
                out_path=args.out or None,
                compact=bool(args.compact),
                hybrid_since=False if args.strict_delta else None,
            )
        except ValueError as e:
            print(f"handoff-md: {e}", file=sys.stderr)
            return 2
        if args.out:
            print(f"handoff-md: wrote {args.out} ({len(md)} chars)")
        else:
            sys.stdout.write(md if md.endswith("\n") else md + "\n")
        return 0

    if args.cmd == "stats":
        print(json.dumps(am.stats(), indent=2, ensure_ascii=False, default=str))
        return 0

    if args.cmd == "recall":
        q = args.text or "projekt holon agent praca"
        for score, item in am.recall(q, top_k=args.top):
            if args.project and not am._match_project(item.content, args.project):
                continue
            flags = []
            if item.is_fact:
                flags.append("F")
            if item.is_work:
                flags.append("W")
            if item.is_insight:
                flags.append("I")
            tag = "".join(flags) or "-"
            print(f"{score:.3f} [{tag}] {item.content[:300]}")
        return 0

    if args.cmd == "seed":
        n = am.seed()
        if not args.no_save:
            ok = am.save()
            print(f"seed: +{n} (merge/refresh), save={'ok' if ok else 'FAIL'}")
        else:
            print(f"seed: +{n} (bez zapisu)")
        print()
        print(am.digest(project=args.project))
        return 0

    if args.cmd == "set-work":
        text = args.text.strip()
        if not text:
            print('Podaj treść: set-work "..." [--project X]', file=sys.stderr)
            return 2
        item = am.set_work(text, project=args.project, max_active=args.max_active)
        if not args.no_save:
            ok = am.save()
            print(f"set-work id={item.id[:8]}… save={'ok' if ok else 'FAIL'}")
        else:
            print(f"set-work id={item.id[:8]}… (bez zapisu)")
        return 0

    if args.cmd == "chambers":
        print(json.dumps(am.list_chambers(), indent=2, ensure_ascii=False, default=str))
        return 0

    if args.cmd == "separate":
        rep = am.separate_chambers(dry_run=bool(args.dry_run))
        if not args.dry_run and not args.no_save:
            rep["saved"] = bool(am.save())
        print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "enter":
        proj = (args.project or "").strip()
        if not proj:
            print('Użycie: enter --project P', file=sys.stderr)
            return 2
        from agent_boot import main as boot_main
        boot_argv = ["--project", proj, "--path", args.path]
        if args.since:
            boot_argv.extend(["--since", args.since])
        if args.strict_delta:
            boot_argv.append("--strict-delta")
        if args.compact:
            boot_argv.append("--compact")
        if args.no_digest:
            boot_argv.append("--no-banner")
        return int(boot_main(boot_argv) or 0)

    if args.cmd == "leave":
        w = (args.work_text or "").strip() or (
            args.text.strip() if not args.as_fact else ""
        )
        f = (args.fact_text or "").strip()
        if args.as_fact and args.text.strip() and not f:
            f = args.text.strip()
        if args.as_work and args.text.strip() and not w:
            w = args.text.strip()
        try:
            rep = am.leave(
                work=w,
                fact=f,
                project=args.project,
                max_active=args.max_active,
                save=not args.no_save,
            )
        except ValueError as e:
            print(f"leave: {e}", file=sys.stderr)
            return 2
        print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "close":
        # B10: close --work-text "…" --fact-text "…" --project P
        # albo: close "work text" --fact-text "…"
        w = (args.work_text or "").strip() or (
            args.text.strip() if not args.as_fact else ""
        )
        f = (args.fact_text or "").strip()
        if args.as_fact and args.text.strip() and not f:
            f = args.text.strip()
        if args.as_work and args.text.strip() and not w:
            w = args.text.strip()
        try:
            rep = am.close(
                work=w,
                fact=f,
                project=args.project,
                max_active=args.max_active,
                save=not args.no_save,
            )
        except ValueError as e:
            print(f"close: {e}", file=sys.stderr)
            print(
                'Użycie: close --work-text "…" --fact-text "…" --project P',
                file=sys.stderr,
            )
            return 2
        print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "crystallize":
        import json as _json
        rep = am.crystallize(
            project=args.project,
            dry_run=bool(args.dry_run),
            sim_threshold=args.sim,
            max_active_work=args.max_active,
            cross_project_merge=bool(args.cross_project),
        )
        if not args.dry_run and not args.no_save:
            rep["save"] = am.save()
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "entangle":
        import json as _json
        rep = am.entanglement_score(args.project)
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "collab-test":
        import json as _json
        report = am.collab_test()
        for c in report["checks"]:
            mark = "PASS" if c["pass"] else "FAIL"
            extra = f" — {c['detail']}" if c.get("detail") else ""
            print(f"[{mark}] {c['name']}{extra}")
        print()
        print("COLLAB_TEST:", "OK" if report["ok"] else "FAILED")
        print(_json.dumps({"ok": report["ok"], "n_checks": len(report["checks"]),
                           "stats": report["stats"]}, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if args.cmd == "eval":
        import json as _json
        from holon_memory_eval import run_golden_eval
        report = run_golden_eval()
        for c in report["checks"]:
            mark = "PASS" if c["pass"] else "FAIL"
            extra = f" — {c['detail']}" if c.get("detail") else ""
            print(f"[{mark}] {c['name']}{extra}")
        print()
        print("GOLDEN_EVAL:", "OK" if report["ok"] else "FAILED")
        print(_json.dumps(
            {"ok": report["ok"], "n_checks": len(report["checks"])},
            ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if args.cmd == "ablation":
        import json as _json
        from holon_memory_eval import run_ablation_report
        report = run_ablation_report()
        print(_json.dumps(report, indent=2, ensure_ascii=False, default=str))
        print()
        print("ABLATION:", "OK" if report.get("ok") else "FAILED")
        return 0 if report.get("ok") else 1

    if args.cmd == "watch-remember":
        import json as _json
        from holon_remember_watch import RememberInbox, describe_watch_slot
        if args.once:
            w = RememberInbox(
                am, args.inbox, poll_s=args.poll, auto_save=not args.no_save
            )
            rep = w.poll_once()
            print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
            return 0 if rep.get("ok") else 1
        print(_json.dumps(describe_watch_slot(), indent=2, ensure_ascii=False))
        print(f"watching {args.inbox} poll={args.poll}s (Ctrl+C stop)", flush=True)
        w = RememberInbox(
            am, args.inbox, poll_s=args.poll, auto_save=not args.no_save
        )
        try:
            w.run_forever()
        except KeyboardInterrupt:
            print("\n[remember-watch] stop")
        return 0

    if args.cmd == "llm-slot":
        import json as _json
        from holon_llm import describe_llm_slot, build_llm_client
        from holon_helper import describe_helper_slot, build_helper_client
        slot = describe_llm_slot()
        slot["helper"] = describe_helper_slot()
        print(_json.dumps(slot, indent=2, ensure_ascii=False))
        c = build_llm_client(backend="mock", quiet=True)
        print("mock_client:", type(c).__name__ if c else None)
        hc = build_helper_client(quiet=True)
        print(
            "helper_client:",
            type(hc).__name__ if hc else None,
            getattr(hc, "model", None) if hc else "(brak — ustaw GEMINI_API_KEY)",
        )
        return 0

    if args.cmd in ("assist", "helper"):
        import json as _json
        from holon_helper import HolonHelper

        helper = HolonHelper(am, project=args.project or "", quiet=True)
        task = (args.task or "orient").strip()
        ask = (args.ask or args.text or "").strip()
        if ask and task in ("orient", "hygiene", ""):
            task = "ask"
        rep = helper.run(task, text=ask)
        if args.json:
            print(_json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(
                f"[assist] task={rep.task} backend={rep.backend} "
                f"model={rep.model} llm={rep.llm_used} ok={rep.ok}"
            )
            if rep.error:
                print("ERROR:", rep.error)
            if rep.text:
                print(rep.text)
            st = rep.structured or {}
            if st.get("work_text") or st.get("fact_text"):
                print("\nWORK:", st.get("work_text") or "")
                print("FACT:", st.get("fact_text") or "")
            if rep.actions:
                print("\n--- actions ---")
                for a in rep.actions:
                    print(" ", a)
        return 0 if rep.ok else 1

    if args.cmd == "karmin-slot":
        import json as _json
        from holon_backend_karmin import describe_karmin_slot
        print(_json.dumps(describe_karmin_slot(), indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "karmin-sync":
        import json as _json
        rep = am.karmin_sync()
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "karmin-export":
        import json as _json
        rep = am.karmin_export(args.snapshot)
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "karmin-import":
        import json as _json
        rep = am.karmin_import_merge(args.snapshot)
        if rep.get("ok") and not args.no_save:
            rep["holon_save"] = am.save()
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "remember":
        text = args.text.strip()
        if not text:
            print("Podaj treść: remember \"...\" [--fact|--work]", file=sys.stderr)
            return 2
        if args.as_work:
            kind = "work"
        elif args.as_fact:
            kind = "fact"
        elif args.kind:
            kind = args.kind
        else:
            kind = "fact"
        item = am.remember(text, kind=kind, project=args.project)
        if not args.no_save:
            ok = am.save()
            print(f"remembered [{kind}] id={item.id[:8]}… save={'ok' if ok else 'FAIL'}")
        else:
            print(f"remembered [{kind}] id={item.id[:8]}… (bez zapisu)")
        return 0

    return 1
