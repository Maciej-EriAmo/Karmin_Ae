#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
karmin_app.py — Control Center Karmin_Ae (ścieżka dla CZŁOWIEKA).

Norma UX: okienko + linia poleceń (hybryda: nie musisz znać PowerShella).
  python karmin_app.py
  START.cmd
  python karmin_app.py -c "fact [Holon] coś"
  python karmin_app.py -c "help"

Agent nadal: python agent_boot.py  (AGENTS.md).
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from holon_settings import (  # noqa: E402
    PRESETS,
    apply_preset,
    doctor,
    load_settings,
    normalize_lang,
    normalize_settings,
    preset_text,
    resolve_ui_lang,
    save_settings,
)


# ── i18n (krótki zestaw pod Control Center) ───────────────────────────────

UI = {
    "pl": {
        "title": "Karmin_Ae — panel sterowania",
        "tab_home": "Start",
        "tab_session": "Sesja SE",
        "tab_memory": "Pamięć",
        "tab_cmd": "Konsola",
        "tab_setup": "Ustawienia",
        "tab_help": "Pomoc",
        "cmd_prompt": "Polecenie ›",
        "cmd_run": "Wykonaj",
        "cmd_hint": "np. help · chat · fact … · work … · boot · doctor  (↑↓ historia)",
        "refresh": "Odśwież",
        "doctor": "Doctor",
        "open_boot": "Pokaż boot (agent)",
        "start_chat": "Chat / brainstorm",
        "adv_configure": "Advanced configure…",
        "copy_hint": "KANON: START.cmd · START_CHAT.cmd · agent_boot.py  |  linia poleceń: help",
        "project": "Projekt",
        "since": "Okno (--since)",
        "load_handoff": "Załaduj handoff",
        "save_md": "Zapisz handoff.md",
        "remember": "Zapisz fact",
        "set_work": "Ustaw work",
        "close_session": "Zamknij sesję (close)",
        "crystallize": "Krystalizuj",
        "fact": "Fact (trwałe)",
        "work": "Work (wątek)",
        "fact_sum": "Fact summary (close)",
        "work_next": "Work next (close)",
        "preset": "Preset",
        "save_cfg": "Zapisz ustawienia",
        "lang": "Język",
        "status_ok": "Gotowe",
        "status_err": "Błąd",
        "home_blurb": (
            "To panel dla Ciebie (człowiek). "
            "Na dole: linia poleceń. Przycisk Chat/brainstorm → EriAmo w nowym oknie. "
            "Agent SE: python agent_boot.py — nie musi tu wchodzić."
        ),
        "help_body": (
            "ŚCIEŻKI\n"
            "• Człowiek: START.cmd / python karmin_app.py\n"
            "• Chat/brainstorm: przycisk lub START_CHAT.cmd / polecenie chat\n"
            "• Linia poleceń: na dole panelu lub zakładka Konsola\n"
            "• Agent SE: python agent_boot.py  (czyta AGENTS.md)\n"
            "• Konfigurator: python holon_configure.py help\n\n"
            "ZAKŁADKI\n"
            "• Start — stan, doctor, Chat/brainstorm\n"
            "• Sesja SE — handoff\n"
            "• Pamięć — formularze fact/work/close\n"
            "• Konsola — historia poleceń + help\n"
            "• Ustawienia — preset, język\n\n"
            "CHAT ≠ AGENT: brainstorm = rozmowa EriAmo; boot = handoff SE.\n"
            "Wspólna pamięć: holon_memory.json\n\n"
            "POLECENIA (skrót): help · chat · status · fact … · work … · boot · "
            "handoff · doctor · crystallize · recall …\n"
            "Pełna lista: wpisz  help  w linii poleceń."
        ),
    },
    "en": {
        "title": "Karmin_Ae — Control Center",
        "tab_home": "Home",
        "tab_session": "SE session",
        "tab_memory": "Memory",
        "tab_cmd": "Console",
        "tab_setup": "Settings",
        "tab_help": "Help",
        "cmd_prompt": "Command ›",
        "cmd_run": "Run",
        "cmd_hint": "e.g. help · chat · fact … · work … · boot · doctor  (↑↓ history)",
        "refresh": "Refresh",
        "doctor": "Doctor",
        "open_boot": "Show agent boot",
        "start_chat": "Chat / brainstorm",
        "adv_configure": "Advanced configure…",
        "copy_hint": "CANON: START.cmd · START_CHAT.cmd · agent_boot.py  |  command bar: help",
        "project": "Project",
        "since": "Window (--since)",
        "load_handoff": "Load handoff",
        "save_md": "Save handoff.md",
        "remember": "Save fact",
        "set_work": "Set work",
        "close_session": "Close session",
        "crystallize": "Crystallize",
        "fact": "Fact (durable)",
        "work": "Work (thread)",
        "fact_sum": "Fact summary (close)",
        "work_next": "Work next (close)",
        "preset": "Preset",
        "save_cfg": "Save settings",
        "lang": "Language",
        "status_ok": "OK",
        "status_err": "Error",
        "home_blurb": (
            "This panel is for you (human). "
            "Bottom: command bar. Chat/brainstorm opens EriAmo in a new window. "
            "SE agent: python agent_boot.py — does not need this window."
        ),
        "help_body": (
            "PATHS\n"
            "• Human: START.cmd / python karmin_app.py\n"
            "• Command line: bottom bar or Console tab\n"
            "• SE agent: python agent_boot.py  (reads AGENTS.md)\n"
            "• Configurator: python holon_configure.py help\n\n"
            "TABS\n"
            "• Home — status, doctor\n"
            "• SE session — handoff\n"
            "• Memory — fact/work/close forms\n"
            "• Console — command history + help\n"
            "• Settings — preset, language\n\n"
            "CHAT / BRAINSTORM\n"
            "• Button «Chat / brainstorm» or command: chat\n"
            "• Opens EriAmo (main_aware) in a new window — shared holon_memory.json\n"
            "• Not the SE agent (boot); this is conversation / brainstorm\n\n"
            "COMMANDS (short): help · status · fact … · work … · boot · chat · "
            "handoff · doctor · crystallize · recall …\n"
            "Full list: type  help  in the command bar."
        ),
    },
}

CMD_HELP_TEXT = """
Karmin_Ae — linia poleceń (w panelu; nie trzeba PowerShella)

  help                         ta lista
  status [projekt]             stan JSON (skrót tekstowy)
  project <nazwa>              ustaw projekt sesji panelu
  since <24h|7d|…|off>         okno handoff
  boot [--project P] [--since 24h]
  handoff [--project P] [--since 24h]
  handoff-md                   zapisz handoff.md
  fact <tekst>                 remember fact (trwałe)
  work <tekst>                 set-work (aktywny wątek)
  close fact=<…> work=<…>      albo: close --fact "…" --work "…"
  crystallize [projekt]
  doctor
  recall <zapytanie>
  digest [projekt]
  use <preset>                 se | se-compact | se-long | chat | lab-flat
  eval                         golden eval (dłuższe)
  clear                        wyczyść konsolę
  chat | brainstorm              start czatu EriAmo (brainstorm) w nowym oknie
  chat aware | chat secure     warianty: aware / secure
  ! <polecenie>                surowy subprocess w katalogu repo
                               np. ! python agent_boot.py --project Holon

Przykłady:
  fact [Holon] boot działa z panelu
  work [Karmazyn] następny: shell client
  boot --project Holon --since 24h
  chat
  brainstorm
  close fact=sesja OK work=dalej crystallize optional

Jednorazowo z terminala (bez GUI):
  python karmin_app.py -c "status Holon"
  python karmin_app.py -c "fact [Holon] notatka"
  python karmin_app.py -c "chat"
""".strip()


CHAT_MODES = {
    "basic": ("main.py", "EriAmo basic"),
    "aware": ("main_aware.py", "EriAmo aware (notatki/zadania) — brainstorm"),
    "secure": ("main_secure.py", "EriAmo secure (scanner)"),
    "brainstorm": ("main_aware.py", "Brainstorm / EriAmo aware"),
}


def launch_chat(mode: str = "brainstorm") -> Dict[str, Any]:
    """
    Otwórz czat EriAmo w osobnym oknie konsoli (ukłon dla zapominalskich).
    Domyślnie brainstorm = main_aware (notatki + kontekst).
    """
    key = (mode or "brainstorm").strip().lower()
    if key in ("chat", "default", ""):
        key = "brainstorm"
    if key not in CHAT_MODES:
        return {
            "ok": False,
            "output": f"nieznany tryb chatu: {mode!r}\n"
            f"dostępne: {', '.join(sorted(CHAT_MODES))}",
        }
    script_name, label = CHAT_MODES[key]
    script = ROOT / script_name
    if not script.is_file():
        return {"ok": False, "output": f"brak pliku: {script}"}

    try:
        if sys.platform == "win32":
            # Osobne okno konsoli z pętlą Ty: / EriAmo:
            flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(ROOT),
                creationflags=flags,
            )
        else:
            subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(ROOT),
                start_new_session=True,
            )
        return {
            "ok": True,
            "output": (
                f"Uruchomiono czat: {label}\n"
                f"  skrypt: {script_name}\n"
                f"  pamięć: holon_memory.json (wspólna z SE)\n"
                f"  w oknie czatu: quit = koniec\n"
                f"  SE agent nadal: python agent_boot.py"
            ),
        }
    except Exception as e:
        return {"ok": False, "output": f"{type(e).__name__}: {e}"}



def tr(lang: str, key: str) -> str:
    pack = UI.get(normalize_lang(lang)) or UI["pl"]
    return pack.get(key) or UI["pl"].get(key) or key


def open_am(project: str = ""):
    from holon_agent_memory import AgentMemory

    return AgentMemory.open(memory_path="holon_memory.json", profile="agent")


def surface_status(project: str = "") -> Dict[str, Any]:
    """Jedna paczka stanu dla GUI / CLI status."""
    from holon_agent_memory import AgentMemory
    from holon_settings import load_config, load_settings

    s = load_settings()
    cfg = load_config(settings=s)
    am = AgentMemory.open(memory_path=str(s.get("memory_path") or "holon_memory.json"))
    st = am.stats()
    proj = (project or s.get("default_project") or am.read_last_project() or "").strip()
    handoff = am.handoff(
        project=proj,
        include_digest=False,
        compact=True,
        hybrid_since=True,
    )
    works = [
        (w.get("content") if isinstance(w, dict) else str(w))
        for w in (handoff.get("active_work") or [])
    ]
    facts = [
        (f.get("content") if isinstance(f, dict) else str(f))
        for f in (handoff.get("key_facts") or [])[:4]
    ]
    actions = handoff.get("recommended_actions") or []
    doc = doctor(root=ROOT)
    return {
        "project": proj,
        "stats": st,
        "profile": cfg.profile,
        "preset": s.get("preset"),
        "ui_lang": s.get("ui_lang") or "pl",
        "active_work": works,
        "key_facts": facts,
        "recommended_actions": actions,
        "doctor_score": doc.get("score"),
        "doctor_ok": doc.get("ok"),
        "surfaces": {
            "human_gui": "python karmin_app.py   # or START.cmd",
            "agent_boot": "python agent_boot.py",
            "chat_brainstorm": "python karmin_app.py -c chat   # or button Chat/brainstorm",
            "configure": "python holon_configure.py gui",
            "help": "python holon_configure.py help",
        },
        "memory_path": str(Path(am.memory_path).resolve()),
        "root": str(ROOT),
    }


def _parse_kv_flags(parts: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """Wyciąga --key val oraz key=val; reszta jako positional."""
    flags: Dict[str, str] = {}
    rest: List[str] = []
    i = 0
    while i < len(parts):
        p = parts[i]
        if p.startswith("--") and i + 1 < len(parts):
            flags[p[2:].replace("-", "_")] = parts[i + 1]
            i += 2
            continue
        if "=" in p and not p.startswith("-"):
            k, _, v = p.partition("=")
            flags[k.strip().replace("-", "_")] = v.strip().strip('"').strip("'")
            i += 1
            continue
        rest.append(p)
        i += 1
    return flags, rest


def run_line(
    line: str,
    *,
    project: str = "",
    since: str = "",
) -> Dict[str, Any]:
    """
    Wykonaj jedno polecenie mini-języka panelu.
    Zwraca {ok, output, project, since, clear?}
    """
    raw = (line or "").strip()
    if not raw:
        return {"ok": True, "output": "", "project": project, "since": since}

    # surowy subprocess
    if raw.startswith("!"):
        cmd = raw[1:].strip()
        if not cmd:
            return {"ok": False, "output": "puste !polecenie", "project": project, "since": since}
        try:
            # Windows-friendly: shell=True for simple user commands in repo
            r = subprocess.run(
                cmd,
                cwd=str(ROOT),
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
            out = (r.stdout or "") + (r.stderr or "")
            return {
                "ok": r.returncode == 0,
                "output": out.strip() or f"(exit {r.returncode})",
                "project": project,
                "since": since,
            }
        except Exception as e:
            return {"ok": False, "output": str(e), "project": project, "since": since}

    try:
        parts = shlex.split(raw, posix=False)
    except ValueError:
        parts = raw.split()
    if not parts:
        return {"ok": True, "output": "", "project": project, "since": since}

    cmd = parts[0].lower().replace("_", "-")
    args = parts[1:]
    flags, pos = _parse_kv_flags(args)
    proj = flags.get("project") or project
    snc = flags.get("since") if "since" in flags else since

    def am_open():
        return open_am()

    try:
        if cmd in ("help", "?", "h"):
            return {"ok": True, "output": CMD_HELP_TEXT, "project": proj, "since": snc}

        if cmd == "clear":
            return {"ok": True, "output": "", "project": proj, "since": snc, "clear": True}

        if cmd == "project":
            name = " ".join(pos).strip() or flags.get("name", "")
            if not name:
                return {
                    "ok": True,
                    "output": f"project={proj or '(none)'}",
                    "project": proj,
                    "since": snc,
                }
            return {
                "ok": True,
                "output": f"project → {name}",
                "project": name,
                "since": snc,
            }

        if cmd == "since":
            val = (pos[0] if pos else flags.get("value", "")).strip()
            if val.lower() in ("off", "none", "-", "0"):
                val = ""
            return {
                "ok": True,
                "output": f"since → {val or '(full)'}",
                "project": proj,
                "since": val,
            }

        if cmd == "status":
            p = " ".join(pos).strip() or proj
            st = surface_status(p)
            lines = [
                f"project={st.get('project')}",
                f"doctor={st.get('doctor_score')}% ok={st.get('doctor_ok')}",
                f"profile={st.get('profile')} preset={st.get('preset')}",
                f"stats={st.get('stats')}",
                "work:",
            ]
            for w in st.get("active_work") or []:
                lines.append(f"  • {str(w)[:180]}")
            lines.append("facts:")
            for f in st.get("key_facts") or []:
                lines.append(f"  • {str(f)[:180]}")
            return {"ok": True, "output": "\n".join(lines), "project": p or proj, "since": snc}

        if cmd == "boot":
            argv = [sys.executable, str(ROOT / "agent_boot.py"), "--compact", "--no-banner"]
            if proj:
                argv.extend(["--project", proj])
            if snc:
                argv.extend(["--since", snc])
            r = subprocess.run(
                argv, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            out = (r.stdout or r.stderr or "").strip()
            return {
                "ok": r.returncode == 0,
                "output": out[:80000],
                "project": proj,
                "since": snc,
            }

        if cmd in ("handoff", "ho"):
            am = am_open()
            h = am.handoff(
                project=proj or "",
                include_digest=False,
                since=snc or None,
                compact=False,
                hybrid_since=True,
            )
            return {
                "ok": True,
                "output": json.dumps(h, ensure_ascii=False, indent=2, default=str)[:80000],
                "project": proj,
                "since": snc,
            }

        if cmd in ("handoff-md", "handoff_md", "md"):
            am = am_open()
            outp = ROOT / "handoff.md"
            am.handoff_md(
                project=proj or "",
                include_digest=False,
                since=snc or None,
                out_path=str(outp),
                compact=False,
                hybrid_since=True,
            )
            return {
                "ok": True,
                "output": f"wrote {outp}",
                "project": proj,
                "since": snc,
            }

        if cmd == "remember" and pos and pos[0].lower() in ("fact", "work"):
            # remember fact …  |  remember work …
            sub = pos[0].lower()
            text = " ".join(pos[1:]).strip()
            cmd = "fact" if sub == "fact" else "work"
            pos = text.split() if text else []
            # re-join as single blob via pos list rebuild
            if text:
                pos = [text]  # one token path: we'll join pos

        if cmd in ("fact", "remember"):
            text = " ".join(pos).strip()
            if not text:
                return {"ok": False, "output": "użycie: fact <tekst>", "project": proj, "since": snc}
            am = am_open()
            content = text if not proj or text.startswith("[") else f"[{proj}] {text}"
            item = am.remember(content, kind="fact")
            am.save()
            return {
                "ok": True,
                "output": f"fact saved id={getattr(item, 'id', '')[:8]}…\n{content[:200]}",
                "project": proj,
                "since": snc,
            }

        if cmd in ("work", "set-work", "setwork"):
            text = " ".join(pos).strip()
            if not text:
                return {"ok": False, "output": "użycie: work <tekst>", "project": proj, "since": snc}
            am = am_open()
            item = am.set_work(text, project=proj or "")
            am.save()
            return {
                "ok": True,
                "output": f"work set id={getattr(item, 'id', '')[:8]}…\n{text[:200]}",
                "project": proj,
                "since": snc,
            }

        if cmd == "close":
            fact_t = flags.get("fact") or flags.get("fact_text") or ""
            work_t = flags.get("work") or flags.get("work_text") or ""
            if not fact_t and not work_t and pos:
                # close single blob as fact if no flags
                fact_t = " ".join(pos)
            am = am_open()
            rep = am.close(work=work_t, fact=fact_t, project=proj or "", save=True)
            return {
                "ok": True,
                "output": json.dumps(rep, ensure_ascii=False, indent=2, default=str)[:4000],
                "project": proj,
                "since": snc,
            }

        if cmd in ("crystallize", "crystal"):
            p = " ".join(pos).strip() or proj
            am = am_open()
            rep = am.crystallize(project=p or "", dry_run=False)
            am.save()
            return {
                "ok": True,
                "output": json.dumps(rep, ensure_ascii=False, indent=2, default=str)[:6000],
                "project": p or proj,
                "since": snc,
            }

        if cmd == "doctor":
            rep = doctor(root=ROOT)
            lines = [f"score={rep.get('score')}% ok={rep.get('ok')}"]
            for c in rep.get("checks") or []:
                lines.append(f"{'OK' if c.get('ok') else '!!'} {c.get('name')}: {c.get('detail')}")
            return {"ok": True, "output": "\n".join(lines), "project": proj, "since": snc}

        if cmd == "recall":
            q = " ".join(pos).strip()
            if not q:
                return {"ok": False, "output": "użycie: recall <zapytanie>", "project": proj, "since": snc}
            am = am_open()
            hits = am.recall(q, top_k=8)
            lines = [f"recall {q!r} → {len(hits)}"]
            for score, item in hits:
                c = getattr(item, "content", str(item))[:160]
                lines.append(f"  {score:.3f}  {c}")
            return {"ok": True, "output": "\n".join(lines), "project": proj, "since": snc}

        if cmd == "digest":
            p = " ".join(pos).strip() or proj
            am = am_open()
            text = am.digest(project=p or "")
            return {"ok": True, "output": text[:20000], "project": p or proj, "since": snc}

        if cmd == "use":
            name = (pos[0] if pos else "").strip()
            if not name:
                return {"ok": False, "output": "użycie: use se|se-compact|…", "project": proj, "since": snc}
            s = apply_preset(name, load_settings())
            path = save_settings(s)
            return {
                "ok": True,
                "output": f"preset={name} profile={s.get('profile')} → {path}",
                "project": proj,
                "since": snc,
            }

        if cmd == "eval":
            r = subprocess.run(
                [sys.executable, str(ROOT / "holon_agent_memory.py"), "eval"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
            out = (r.stdout or "") + (r.stderr or "")
            return {
                "ok": r.returncode == 0,
                "output": out[-12000:],
                "project": proj,
                "since": snc,
            }

        if cmd in ("chat", "brainstorm", "eria"):
            mode = "brainstorm"
            if cmd == "chat" and pos:
                mode = pos[0].lower()
            elif cmd == "brainstorm":
                mode = "brainstorm"
            elif cmd == "eria":
                mode = (pos[0].lower() if pos else "brainstorm")
            # chat aware / chat secure as two tokens already in pos
            if cmd == "chat" and not pos:
                mode = "brainstorm"
            res = launch_chat(mode)
            return {
                "ok": res.get("ok", False),
                "output": res.get("output", ""),
                "project": proj,
                "since": snc,
            }

        return {
            "ok": False,
            "output": f"nieznane polecenie: {cmd!r}\nwpisz: help",
            "project": proj,
            "since": snc,
        }
    except Exception as e:
        return {"ok": False, "output": f"{type(e).__name__}: {e}", "project": project, "since": since}


def run_gui(lang: Optional[str] = None) -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext, ttk
    except ImportError:
        print("tkinter missing — fallback: python holon_configure.py wizard", file=sys.stderr)
        return 2

    settings = load_settings()
    lang_state = {"lang": resolve_ui_lang(lang, settings=settings)}

    root = tk.Tk()
    root.minsize(720, 560)
    root.geometry("860x620")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    tab_home = ttk.Frame(nb, padding=10)
    tab_sess = ttk.Frame(nb, padding=10)
    tab_mem = ttk.Frame(nb, padding=10)
    tab_cmd = ttk.Frame(nb, padding=10)
    tab_setup = ttk.Frame(nb, padding=10)
    tab_help = ttk.Frame(nb, padding=10)
    for t, fr in [
        ("tab_home", tab_home),
        ("tab_session", tab_sess),
        ("tab_memory", tab_mem),
        ("tab_cmd", tab_cmd),
        ("tab_setup", tab_setup),
        ("tab_help", tab_help),
    ]:
        nb.add(fr, text=tr(lang_state["lang"], t))

    status_var = tk.StringVar(value="")
    home_text = scrolledtext.ScrolledText(tab_home, wrap="word", height=22, font=("Consolas", 10))
    home_text.pack(fill="both", expand=True, pady=(0, 8))

    # Console tab
    cmd_log = scrolledtext.ScrolledText(tab_cmd, wrap="word", height=26, font=("Consolas", 10))
    cmd_log.pack(fill="both", expand=True, pady=(0, 4))
    cmd_log.insert("1.0", CMD_HELP_TEXT + "\n\n")
    cmd_log.configure(state="disabled")

    # Session
    proj_var = tk.StringVar(value=settings.get("default_project") or "")
    since_var = tk.StringVar(value="24h")
    row = ttk.Frame(tab_sess)
    row.pack(fill="x", pady=4)
    ttk.Label(row, text="project").pack(side="left")
    ttk.Entry(row, textvariable=proj_var, width=18).pack(side="left", padx=6)
    ttk.Label(row, text="since").pack(side="left")
    ttk.Combobox(
        row, textvariable=since_var, values=["", "24h", "7d", "12h"], width=8
    ).pack(side="left", padx=6)
    sess_text = scrolledtext.ScrolledText(tab_sess, wrap="word", height=24, font=("Consolas", 10))
    sess_text.pack(fill="both", expand=True, pady=6)

    # Memory
    mem_proj = tk.StringVar(value=proj_var.get())
    mem_boxes: Dict[str, Any] = {}

    def mem_box(parent, key: str, label: str, h: int = 3):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=3)
        ttk.Label(f, text=label, width=18).pack(side="left", anchor="n")
        e = tk.Text(f, height=h, wrap="word")
        e.pack(side="left", fill="x", expand=True)
        mem_boxes[key] = e

    def box_get(key: str) -> str:
        w = mem_boxes.get(key)
        return w.get("1.0", "end").strip() if w is not None else ""

    ttk.Label(tab_mem, text="project").pack(anchor="w")
    ttk.Entry(tab_mem, textvariable=mem_proj).pack(fill="x", pady=2)
    mem_box(tab_mem, "fact", "fact (durable)", 4)
    mem_box(tab_mem, "work", "work (thread)", 3)
    mem_box(tab_mem, "close_fact", "close → fact summary", 2)
    mem_box(tab_mem, "close_work", "close → next work", 2)
    mem_btns = ttk.Frame(tab_mem)
    mem_btns.pack(fill="x", pady=8)

    # Setup
    preset_var = tk.StringVar(value=settings.get("preset") or "se")
    lang_var = tk.StringVar(value=lang_state["lang"])
    def_proj_var = tk.StringVar(value=settings.get("default_project") or "")
    ttk.Label(tab_setup, text="preset").pack(anchor="w")
    ttk.Combobox(
        tab_setup, textvariable=preset_var, values=list(PRESETS.keys()), state="readonly"
    ).pack(fill="x", pady=2)
    ttk.Label(tab_setup, text="default_project").pack(anchor="w")
    ttk.Entry(tab_setup, textvariable=def_proj_var).pack(fill="x", pady=2)
    ttk.Label(tab_setup, text="ui_lang").pack(anchor="w")
    ttk.Combobox(
        tab_setup, textvariable=lang_var, values=["pl", "en"], state="readonly"
    ).pack(fill="x", pady=2)
    setup_desc = ttk.Label(tab_setup, text="", wraplength=700)
    setup_desc.pack(anchor="w", pady=8)
    setup_btns = ttk.Frame(tab_setup)
    setup_btns.pack(fill="x", pady=8)

    help_box = scrolledtext.ScrolledText(tab_help, wrap="word", height=28, font=("Segoe UI", 10))
    help_box.pack(fill="both", expand=True)

    # Global command bar (hybryda: CLI w GUI)
    cmd_bar = ttk.Frame(root, padding=(8, 4))
    cmd_bar.pack(fill="x", side="bottom")
    cmd_prompt_lbl = ttk.Label(cmd_bar, text="›")
    cmd_prompt_lbl.pack(side="left")
    cmd_var = tk.StringVar()
    cmd_entry = ttk.Entry(cmd_bar, textvariable=cmd_var, font=("Consolas", 11))
    cmd_entry.pack(side="left", fill="x", expand=True, padx=6)
    btn_cmd_run = ttk.Button(cmd_bar, text="Run")
    btn_cmd_run.pack(side="left")
    cmd_hint_lbl = ttk.Label(root, text="", foreground="#666", font=("", 8))
    cmd_hint_lbl.pack(fill="x", side="bottom", padx=10)

    bottom = ttk.Frame(root)
    bottom.pack(fill="x", padx=8, pady=(0, 4), side="bottom")
    ttk.Label(bottom, textvariable=status_var, foreground="#333").pack(side="left")

    cmd_history: List[str] = []
    cmd_hist_i = {"i": -1}

    def set_status(msg: str, ok: bool = True) -> None:
        status_var.set(msg)
        root.update_idletasks()

    def console_append(text: str) -> None:
        cmd_log.configure(state="normal")
        cmd_log.insert("end", text)
        if not text.endswith("\n"):
            cmd_log.insert("end", "\n")
        cmd_log.see("end")
        cmd_log.configure(state="disabled")

    def apply_lang() -> None:
        lang = normalize_lang(lang_var.get())
        lang_state["lang"] = lang
        root.title(tr(lang, "title"))
        # retitle tabs
        for i, key in enumerate(
            ["tab_home", "tab_session", "tab_memory", "tab_cmd", "tab_setup", "tab_help"]
        ):
            nb.tab(i, text=tr(lang, key))
        help_box.delete("1.0", "end")
        help_box.insert("1.0", tr(lang, "help_body"))
        _, desc = preset_text(preset_var.get() or "se", lang)
        setup_desc.configure(text=desc)
        btn_refresh.configure(text=tr(lang, "refresh"))
        btn_doctor.configure(text=tr(lang, "doctor"))
        btn_boot.configure(text=tr(lang, "open_boot"))
        btn_chat.configure(text=tr(lang, "start_chat"))
        btn_load.configure(text=tr(lang, "load_handoff"))
        btn_md.configure(text=tr(lang, "save_md"))
        btn_fact.configure(text=tr(lang, "remember"))
        btn_work.configure(text=tr(lang, "set_work"))
        btn_close.configure(text=tr(lang, "close_session"))
        btn_crys.configure(text=tr(lang, "crystallize"))
        btn_save_cfg.configure(text=tr(lang, "save_cfg"))
        btn_adv_cfg.configure(text=tr(lang, "adv_configure"))
        cmd_prompt_lbl.configure(text=tr(lang, "cmd_prompt"))
        btn_cmd_run.configure(text=tr(lang, "cmd_run"))
        cmd_hint_lbl.configure(text=tr(lang, "cmd_hint"))

    def execute_command(line: Optional[str] = None) -> None:
        raw = (line if line is not None else cmd_var.get()).strip()
        if not raw:
            return
        if not line:
            cmd_history.append(raw)
            cmd_hist_i["i"] = len(cmd_history)
            cmd_var.set("")
        console_append(f"\n› {raw}\n")
        set_status("…")

        def work():
            res = run_line(
                raw,
                project=proj_var.get().strip() or mem_proj.get().strip(),
                since=since_var.get().strip(),
            )

            def ui():
                if res.get("project") is not None and res.get("project") != proj_var.get():
                    if "project →" in (res.get("output") or "") or raw.lower().startswith("project"):
                        proj_var.set(res.get("project") or "")
                        mem_proj.set(res.get("project") or "")
                if "since →" in (res.get("output") or "") or raw.lower().startswith("since"):
                    since_var.set(res.get("since") or "")
                # always sync context from result
                if res.get("project"):
                    proj_var.set(res["project"])
                    mem_proj.set(res["project"])
                if "since" in res:
                    since_var.set(res.get("since") or "")
                if res.get("clear"):
                    cmd_log.configure(state="normal")
                    cmd_log.delete("1.0", "end")
                    cmd_log.configure(state="disabled")
                out = res.get("output") or ""
                if out:
                    console_append(out + "\n")
                mark = "OK" if res.get("ok") else "ERR"
                set_status(f"{mark} · {raw[:60]}")
                # long output → show console
                if len(out) > 200 or raw.lower().split()[0] in (
                    "boot",
                    "handoff",
                    "help",
                    "eval",
                    "digest",
                    "status",
                    "doctor",
                ):
                    nb.select(tab_cmd)
                if res.get("ok") and raw.lower().split()[0] in (
                    "fact",
                    "work",
                    "close",
                    "crystallize",
                    "remember",
                ):
                    refresh_home()

            root.after(0, ui)

        threading.Thread(target=work, daemon=True).start()

    def cmd_on_enter(_e=None):
        execute_command()
        return "break"

    def cmd_hist_up(_e=None):
        if not cmd_history:
            return "break"
        cmd_hist_i["i"] = max(0, cmd_hist_i["i"] - 1)
        cmd_var.set(cmd_history[cmd_hist_i["i"]])
        cmd_entry.icursor("end")
        return "break"

    def cmd_hist_down(_e=None):
        if not cmd_history:
            return "break"
        cmd_hist_i["i"] = min(len(cmd_history), cmd_hist_i["i"] + 1)
        if cmd_hist_i["i"] >= len(cmd_history):
            cmd_var.set("")
        else:
            cmd_var.set(cmd_history[cmd_hist_i["i"]])
        cmd_entry.icursor("end")
        return "break"

    btn_cmd_run.configure(command=execute_command)
    cmd_entry.bind("<Return>", cmd_on_enter)
    cmd_entry.bind("<Up>", cmd_hist_up)
    cmd_entry.bind("<Down>", cmd_hist_down)
    cmd_entry.focus_set()

    def refresh_home() -> None:
        try:
            data = surface_status(proj_var.get().strip())
            lang = lang_state["lang"]
            lines = [
                tr(lang, "title"),
                tr(lang, "home_blurb"),
                "",
                f"root     : {data['root']}",
                f"memory   : {data['memory_path']}",
                f"project  : {data['project'] or '(all)'}",
                f"profile  : {data['profile']}  preset={data['preset']}",
                f"doctor   : {data['doctor_score']}%  ok={data['doctor_ok']}",
                f"stats    : {data['stats']}",
                "",
                "=== active_work ===",
            ]
            for w in data["active_work"] or ["(none)"]:
                lines.append(f"  • {w[:200]}")
            lines.append("")
            lines.append("=== key_facts (top) ===")
            for f in data["key_facts"] or ["(none)"]:
                lines.append(f"  • {str(f)[:200]}")
            lines.append("")
            lines.append("=== recommended_actions ===")
            for a in data["recommended_actions"] or ["(none)"]:
                lines.append(f"  → {a}")
            lines.append("")
            lines.append("=== surfaces ===")
            for k, v in data["surfaces"].items():
                lines.append(f"  {k}: {v}")
            lines.append("")
            lines.append(tr(lang, "copy_hint"))
            home_text.delete("1.0", "end")
            home_text.insert("1.0", "\n".join(lines))
            if not proj_var.get().strip() and data["project"]:
                proj_var.set(data["project"])
                mem_proj.set(data["project"])
            set_status(tr(lang, "status_ok"))
        except Exception as e:
            set_status(f"{tr(lang_state['lang'], 'status_err')}: {e}", ok=False)
            messagebox.showerror("Karmin_Ae", str(e))

    def do_doctor() -> None:
        rep = doctor(root=ROOT)
        lines = [f"score={rep['score']}% ok={rep['ok']}", ""]
        for c in rep["checks"]:
            lines.append(f"{'OK' if c['ok'] else '!!'} {c['name']}: {c['detail']}")
        messagebox.showinfo(tr(lang_state["lang"], "doctor"), "\n".join(lines))
        refresh_home()

    def do_boot_preview() -> None:
        """Uruchom agent_boot --compact --no-banner w tle i pokaż wynik."""
        set_status("boot…")

        def work():
            try:
                cmd = [sys.executable, str(ROOT / "agent_boot.py"), "--compact", "--no-banner"]
                p = proj_var.get().strip()
                if p:
                    cmd.extend(["--project", p])
                since = since_var.get().strip()
                if since:
                    cmd.extend(["--since", since])
                r = subprocess.run(
                    cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8"
                )
                out = r.stdout or r.stderr or ""

                def ui():
                    sess_text.delete("1.0", "end")
                    sess_text.insert("1.0", out[:120000])
                    nb.select(tab_sess)
                    set_status(tr(lang_state["lang"], "status_ok") if r.returncode == 0 else f"exit {r.returncode}")

                root.after(0, ui)
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("boot", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def load_handoff() -> None:
        try:
            am = open_am()
            proj = proj_var.get().strip()
            since = since_var.get().strip() or None
            h = am.handoff(
                project=proj,
                include_digest=False,
                since=since,
                compact=False,
                hybrid_since=True,
            )
            sess_text.delete("1.0", "end")
            sess_text.insert(
                "1.0", json.dumps(h, ensure_ascii=False, indent=2, default=str)[:120000]
            )
            set_status(tr(lang_state["lang"], "status_ok"))
        except Exception as e:
            messagebox.showerror("handoff", str(e))

    def save_md() -> None:
        try:
            am = open_am()
            out = ROOT / "handoff.md"
            am.handoff_md(
                project=proj_var.get().strip(),
                include_digest=False,
                since=since_var.get().strip() or None,
                out_path=str(out),
                compact=False,
                hybrid_since=True,
            )
            set_status(f"→ {out}")
            messagebox.showinfo("handoff", f"Saved:\n{out}")
        except Exception as e:
            messagebox.showerror("handoff", str(e))

    def do_remember() -> None:
        text = box_get("fact")
        if not text:
            return
        try:
            am = open_am()
            proj = mem_proj.get().strip()
            content = text if not proj or text.startswith("[") else f"[{proj}] {text}"
            am.remember(content, kind="fact")
            am.save()
            set_status("fact saved")
            refresh_home()
        except Exception as e:
            messagebox.showerror("remember", str(e))

    def do_set_work() -> None:
        text = box_get("work")
        if not text:
            return
        try:
            am = open_am()
            proj = mem_proj.get().strip()
            am.set_work(text, project=proj)
            am.save()
            set_status("work set")
            refresh_home()
        except Exception as e:
            messagebox.showerror("set-work", str(e))

    def do_close() -> None:
        try:
            am = open_am()
            am.close(
                work=box_get("close_work"),
                fact=box_get("close_fact"),
                project=mem_proj.get().strip(),
                save=True,
            )
            set_status("session closed")
            refresh_home()
        except Exception as e:
            messagebox.showerror("close", str(e))

    def do_crystallize() -> None:
        try:
            am = open_am()
            rep = am.crystallize(project=mem_proj.get().strip(), dry_run=False)
            am.save()
            messagebox.showinfo("crystallize", json.dumps(rep, ensure_ascii=False, indent=2)[:2000])
            refresh_home()
        except Exception as e:
            messagebox.showerror("crystallize", str(e))

    def do_save_cfg() -> None:
        try:
            s = load_settings()
            s = apply_preset(preset_var.get() or "se", s)
            s["default_project"] = def_proj_var.get().strip()
            s["ui_lang"] = normalize_lang(lang_var.get())
            s = normalize_settings(s)
            path = save_settings(s)
            apply_lang()
            set_status(f"saved {path}")
            messagebox.showinfo("settings", f"OK\n{path}")
            refresh_home()
        except Exception as e:
            messagebox.showerror("settings", str(e))

    # buttons
    def do_start_chat() -> None:
        res = launch_chat("brainstorm")
        console_append(f"\n› chat / brainstorm\n{res.get('output', '')}\n")
        if res.get("ok"):
            set_status(tr(lang_state["lang"], "start_chat") + " OK")
            messagebox.showinfo(
                tr(lang_state["lang"], "start_chat"),
                res.get("output", ""),
            )
        else:
            set_status(tr(lang_state["lang"], "status_err"))
            messagebox.showerror("chat", res.get("output", "error"))

    home_btns = ttk.Frame(tab_home)
    home_btns.pack(fill="x")
    btn_refresh = ttk.Button(home_btns, text="Refresh", command=refresh_home)
    btn_doctor = ttk.Button(home_btns, text="Doctor", command=do_doctor)
    btn_boot = ttk.Button(home_btns, text="Boot", command=do_boot_preview)
    btn_chat = ttk.Button(home_btns, text="Chat", command=do_start_chat)
    btn_refresh.pack(side="left", padx=3)
    btn_doctor.pack(side="left", padx=3)
    btn_boot.pack(side="left", padx=3)
    btn_chat.pack(side="left", padx=3)

    sess_btns = ttk.Frame(tab_sess)
    sess_btns.pack(fill="x", pady=4)
    btn_load = ttk.Button(sess_btns, text="Load", command=load_handoff)
    btn_md = ttk.Button(sess_btns, text="MD", command=save_md)
    btn_load.pack(side="left", padx=3)
    btn_md.pack(side="left", padx=3)

    btn_fact = ttk.Button(mem_btns, text="Fact", command=do_remember)
    btn_work = ttk.Button(mem_btns, text="Work", command=do_set_work)
    btn_close = ttk.Button(mem_btns, text="Close", command=do_close)
    btn_crys = ttk.Button(mem_btns, text="Crystallize", command=do_crystallize)
    for b in (btn_fact, btn_work, btn_close, btn_crys):
        b.pack(side="left", padx=3)

    btn_save_cfg = ttk.Button(setup_btns, text="Save", command=do_save_cfg)
    btn_save_cfg.pack(side="left", padx=3)
    btn_adv_cfg = ttk.Button(
        setup_btns,
        text="Advanced configure…",
        command=lambda: subprocess.Popen(
            [sys.executable, str(ROOT / "holon_configure.py"), "gui"], cwd=str(ROOT)
        ),
    )
    btn_adv_cfg.pack(side="left", padx=3)

    lang_var.trace_add("write", lambda *_: None)
    preset_var.trace_add(
        "write",
        lambda *_: setup_desc.configure(
            text=preset_text(preset_var.get() or "se", lang_state["lang"])[1]
        ),
    )

    apply_lang()
    refresh_home()
    root.mainloop()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Karmin_Ae Control Center (human GUI + command line)",
        epilog='Example: python karmin_app.py -c "fact [Holon] hello"',
    )
    p.add_argument("--lang", default="", choices=["", "pl", "en"])
    p.add_argument(
        "--status",
        action="store_true",
        help="print JSON status (no GUI) — also useful for agents",
    )
    p.add_argument(
        "-c",
        "--command",
        default="",
        help="run one panel command without GUI (then exit)",
    )
    p.add_argument("--project", default="")
    p.add_argument("--since", default="")
    args = p.parse_args(argv)
    if args.status:
        print(json.dumps(surface_status(args.project), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command:
        res = run_line(args.command, project=args.project, since=args.since)
        out = res.get("output") or ""
        if out:
            print(out)
        return 0 if res.get("ok") else 1
    return run_gui(args.lang or None)


if __name__ == "__main__":
    raise SystemExit(main())
