#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
karmin_app.py — Control Center Karmin_Ae (ścieżka dla CZŁOWIEKA).

Norma UX: okienko, nie CLI.
  python karmin_app.py
  START.cmd   (dwuklik Windows)

Agent nadal: python agent_boot.py  (AGENTS.md).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        "tab_setup": "Ustawienia",
        "tab_help": "Pomoc",
        "refresh": "Odśwież",
        "doctor": "Doctor",
        "open_boot": "Pokaż boot (agent)",
        "copy_hint": "Agent startuje: python agent_boot.py",
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
            "Agent (Grok) używa CLI: agent_boot.py — nie musi otwierać tego okna."
        ),
        "help_body": (
            "ŚCIEŻKI\n"
            "• Człowiek: START.cmd / python karmin_app.py\n"
            "• Agent SE: python agent_boot.py  (czyta AGENTS.md)\n"
            "• Konfigurator CLI: python holon_configure.py help\n\n"
            "ZAKŁADKI\n"
            "• Start — stan, doctor, co robić\n"
            "• Sesja SE — podgląd handoff (jak agent po bootcie)\n"
            "• Pamięć — fact / work / close / crystallize bez terminala\n"
            "• Ustawienia — preset, projekt, język\n\n"
            "CLI zostaje dla power-userów i agentów — to normalne."
        ),
    },
    "en": {
        "title": "Karmin_Ae — Control Center",
        "tab_home": "Home",
        "tab_session": "SE session",
        "tab_memory": "Memory",
        "tab_setup": "Settings",
        "tab_help": "Help",
        "refresh": "Refresh",
        "doctor": "Doctor",
        "open_boot": "Show agent boot",
        "copy_hint": "Agent starts with: python agent_boot.py",
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
            "The agent (Grok) uses CLI: agent_boot.py — it does not need this window."
        ),
        "help_body": (
            "PATHS\n"
            "• Human: START.cmd / python karmin_app.py\n"
            "• SE agent: python agent_boot.py  (reads AGENTS.md)\n"
            "• CLI configurator: python holon_configure.py help\n\n"
            "TABS\n"
            "• Home — status, doctor, what to do\n"
            "• SE session — handoff preview (what the agent sees)\n"
            "• Memory — fact / work / close / crystallize without a terminal\n"
            "• Settings — preset, project, language\n\n"
            "CLI remains for power users and agents — that is fine."
        ),
    },
}


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
            "configure": "python holon_configure.py gui",
            "help": "python holon_configure.py help",
        },
        "memory_path": str(Path(am.memory_path).resolve()),
        "root": str(ROOT),
    }


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
    tab_setup = ttk.Frame(nb, padding=10)
    tab_help = ttk.Frame(nb, padding=10)
    for t, fr in [
        ("tab_home", tab_home),
        ("tab_session", tab_sess),
        ("tab_memory", tab_mem),
        ("tab_setup", tab_setup),
        ("tab_help", tab_help),
    ]:
        nb.add(fr, text=tr(lang_state["lang"], t))

    status_var = tk.StringVar(value="")
    home_text = scrolledtext.ScrolledText(tab_home, wrap="word", height=22, font=("Consolas", 10))
    home_text.pack(fill="both", expand=True, pady=(0, 8))

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

    bottom = ttk.Frame(root)
    bottom.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Label(bottom, textvariable=status_var, foreground="#333").pack(side="left")

    labels_need_refresh: List[Any] = []

    def set_status(msg: str, ok: bool = True) -> None:
        status_var.set(msg)
        root.update_idletasks()

    def apply_lang() -> None:
        lang = normalize_lang(lang_var.get())
        lang_state["lang"] = lang
        root.title(tr(lang, "title"))
        # retitle tabs
        for i, key in enumerate(
            ["tab_home", "tab_session", "tab_memory", "tab_setup", "tab_help"]
        ):
            nb.tab(i, text=tr(lang, key))
        help_box.delete("1.0", "end")
        help_box.insert("1.0", tr(lang, "help_body"))
        _, desc = preset_text(preset_var.get() or "se", lang)
        setup_desc.configure(text=desc)
        btn_refresh.configure(text=tr(lang, "refresh"))
        btn_doctor.configure(text=tr(lang, "doctor"))
        btn_boot.configure(text=tr(lang, "open_boot"))
        btn_load.configure(text=tr(lang, "load_handoff"))
        btn_md.configure(text=tr(lang, "save_md"))
        btn_fact.configure(text=tr(lang, "remember"))
        btn_work.configure(text=tr(lang, "set_work"))
        btn_close.configure(text=tr(lang, "close_session"))
        btn_crys.configure(text=tr(lang, "crystallize"))
        btn_save_cfg.configure(text=tr(lang, "save_cfg"))

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
    home_btns = ttk.Frame(tab_home)
    home_btns.pack(fill="x")
    btn_refresh = ttk.Button(home_btns, text="Refresh", command=refresh_home)
    btn_doctor = ttk.Button(home_btns, text="Doctor", command=do_doctor)
    btn_boot = ttk.Button(home_btns, text="Boot", command=do_boot_preview)
    btn_refresh.pack(side="left", padx=3)
    btn_doctor.pack(side="left", padx=3)
    btn_boot.pack(side="left", padx=3)

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
    ttk.Button(
        setup_btns,
        text="CLI configure…",
        command=lambda: subprocess.Popen(
            [sys.executable, str(ROOT / "holon_configure.py"), "gui"], cwd=str(ROOT)
        ),
    ).pack(side="left", padx=3)

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

    p = argparse.ArgumentParser(description="Karmin_Ae Control Center (human GUI)")
    p.add_argument("--lang", default="", choices=["", "pl", "en"])
    p.add_argument(
        "--status",
        action="store_true",
        help="print JSON status (no GUI) — also useful for agents",
    )
    p.add_argument("--project", default="")
    args = p.parse_args(argv)
    if args.status:
        print(json.dumps(surface_status(args.project), ensure_ascii=False, indent=2, default=str))
        return 0
    return run_gui(args.lang or None)


if __name__ == "__main__":
    raise SystemExit(main())
