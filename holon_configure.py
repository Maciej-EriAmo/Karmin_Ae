#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
holon_configure.py — konfigurator Karmin_Ae (CLI + GUI).

  python holon_configure.py help
  python holon_configure.py --lang en help
  python holon_configure.py set ui_lang en
  python holon_configure.py gui

Język UI: CLI ``--lang pl|en`` → env ``HOLON_UI_LANG`` → settings ``ui_lang`` → pl.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holon_settings import (
    PRESETS,
    SAFE_OVERRIDE_KEYS,
    apply_preset,
    config_field_help,
    default_settings_path,
    doctor,
    export_env_lines,
    load_config,
    load_settings,
    normalize_lang,
    normalize_settings,
    preset_text,
    public_summary,
    resolve_ui_lang,
    save_settings,
)

# ── i18n ──────────────────────────────────────────────────────────────────

MSG: Dict[str, Dict[str, str]] = {
    "pl": {
        "app_title": "Karmin_Ae — konfigurator pamięci SE",
        "app_sub": "Lokalna pamięć SE (nie SaaS) · profile · handoff · LLM",
        "settings_hdr": "Karmin_Ae / Holon — settings",
        "file": "plik",
        "exists": "istnieje",
        "profile": "profil",
        "preset": "preset",
        "default_project": "default_project",
        "memory_path": "memory_path",
        "ui_lang": "język UI",
        "overrides": "overrides",
        "effective": "effective Config",
        "meta_env": "(meta/env)",
        "presets_hdr": "Presety:",
        "saved": "zapisano",
        "error": "błąd",
        "unknown_key": "nieznany klucz",
        "use_set_override": "Użyj: {keys} lub set-override",
        "profile_must": "profile musi być agent|chat|flat",
        "unknown_preset": "nieznany preset",
        "override_not_allowed": "override niedozwolony",
        "allowed": "dozwolone",
        "cleared_override": "wyczyszczono override",
        "wizard_title": "=== Karmin_Ae wizard (pamięć SE) ===",
        "wizard_hint": "Enter = domyślna wartość w [nawiasach]",
        "next_boot": "Dalej: python agent_boot.py",
        "next_doctor": "       python holon_configure.py doctor",
        "doctor_title": "Karmin_Ae doctor",
        "checks": "Checks",
        "positioning": "Positioning vs typowa chmurowa agent-memory",
        "effective_cfg": "Effective",
        "next": "Next",
        "wrote": "zapisano",
        "top_keys": "Klucze top-level: profile, preset, default_project, memory_path, ui_lang, notes",
        "overrides_hdr": "Overrides:",
        "tk_missing": "tkinter niedostępny w tej instalacji Pythona",
        "btn_save": "Zapisz",
        "btn_doctor": "Doctor",
        "btn_boot": "Jak boot?",
        "btn_help": "Pomoc",
        "btn_close": "Zamknij",
        "lang": "Język",
        "status_file": "plik: {path}",
        "status_saved": "zapisano → {path}",
        "status_doctor": "doctor score={score}%",
        "msg_saved": "Zapisano ustawienia:\n{path}",
        "msg_boot": (
            "W terminalu:\n\n"
            "  cd Karmin_Ae\n"
            "  python agent_boot.py\n\n"
            "Settings wczytywane automatycznie (profile, memory_path, overrides)."
        ),
        "help_title": "POMOC — Karmin_Ae configurator",
        "argparse_desc": "Konfigurator Karmin_Ae / Holon (CLI + GUI)",
        "arg_path": "ścieżka settings (domyślnie holon_settings.json)",
        "arg_lang": "język UI: pl | en (zapis: set ui_lang)",
        "h_show": "pokaż ustawienia + effective Config",
        "h_presets": "lista presetów produktowych",
        "h_use": "zastosuj preset i zapisz",
        "h_set": "ustaw pole top-level (także ui_lang)",
        "h_set_override": "ustaw/clear override Config",
        "h_wizard": "interaktywny setup w terminalu",
        "h_doctor": "diagnostyka + positioning vs SaaS memory",
        "h_export": "wypisz HOLON_* do shella",
        "h_keys": "lista dozwolonych kluczy",
        "h_gui": "okienkowy konfigurator (tkinter)",
        "h_help": "instrukcja obsługi (ten tekst)",
        "h_lang": "ustaw język UI i zapisz (pl|en)",
    },
    "en": {
        "app_title": "Karmin_Ae — SE memory configurator",
        "app_sub": "Local-first SE memory (not SaaS) · profiles · handoff · LLM",
        "settings_hdr": "Karmin_Ae / Holon — settings",
        "file": "file",
        "exists": "exists",
        "profile": "profile",
        "preset": "preset",
        "default_project": "default_project",
        "memory_path": "memory_path",
        "ui_lang": "UI language",
        "overrides": "overrides",
        "effective": "effective Config",
        "meta_env": "(meta/env)",
        "presets_hdr": "Presets:",
        "saved": "saved",
        "error": "error",
        "unknown_key": "unknown key",
        "use_set_override": "Use: {keys} or set-override",
        "profile_must": "profile must be agent|chat|flat",
        "unknown_preset": "unknown preset",
        "override_not_allowed": "override not allowed",
        "allowed": "allowed",
        "cleared_override": "cleared override",
        "wizard_title": "=== Karmin_Ae wizard (SE memory) ===",
        "wizard_hint": "Enter = keep default in [brackets]",
        "next_boot": "Next: python agent_boot.py",
        "next_doctor": "      python holon_configure.py doctor",
        "doctor_title": "Karmin_Ae doctor",
        "checks": "Checks",
        "positioning": "Positioning vs typical cloud agent-memory",
        "effective_cfg": "Effective",
        "next": "Next",
        "wrote": "wrote",
        "top_keys": "Top-level keys: profile, preset, default_project, memory_path, ui_lang, notes",
        "overrides_hdr": "Overrides:",
        "tk_missing": "tkinter is not available in this Python install",
        "btn_save": "Save",
        "btn_doctor": "Doctor",
        "btn_boot": "Boot how-to",
        "btn_help": "Help",
        "btn_close": "Close",
        "lang": "Language",
        "status_file": "file: {path}",
        "status_saved": "saved → {path}",
        "status_doctor": "doctor score={score}%",
        "msg_saved": "Settings saved:\n{path}",
        "msg_boot": (
            "In a terminal:\n\n"
            "  cd Karmin_Ae\n"
            "  python agent_boot.py\n\n"
            "Settings load automatically (profile, memory_path, overrides)."
        ),
        "help_title": "HELP — Karmin_Ae configurator",
        "argparse_desc": "Karmin_Ae / Holon configurator (CLI + GUI)",
        "arg_path": "settings path (default holon_settings.json)",
        "arg_lang": "UI language: pl | en (persist: set ui_lang)",
        "h_show": "show settings + effective Config",
        "h_presets": "list product presets",
        "h_use": "apply preset and save",
        "h_set": "set top-level field (including ui_lang)",
        "h_set_override": "set/clear Config override",
        "h_wizard": "interactive terminal setup",
        "h_doctor": "diagnostics + positioning vs SaaS memory",
        "h_export": "print HOLON_* for the shell",
        "h_keys": "list allowed keys",
        "h_gui": "windowed configurator (tkinter)",
        "h_help": "user guide (this text)",
        "h_lang": "set UI language and save (pl|en)",
    },
}

HELP_BODY: Dict[str, str] = {
    "pl": """
{title}

CZYM TO JEST
  Lokalny konfigurator pamięci SE (Grok/CLI) — nie chmura.
  Zapisuje holon_settings.json (gitignore). To NIE jest holon_memory.json
  (stan umysłu / fakty).

SZYBKI START
  1) python holon_configure.py wizard
  2) python holon_configure.py doctor
  3) python agent_boot.py
  Opcja okienkowa: python holon_configure.py gui

JĘZYK (PL / EN)
  • Jednorazowo:   python holon_configure.py --lang en help
  • Trwale:        python holon_configure.py set ui_lang en
  • Alias:         python holon_configure.py lang en
  • Env:           set HOLON_UI_LANG=en
  • GUI:           przełącznik Język / Language
  Kolejność: --lang → HOLON_UI_LANG → ui_lang w pliku → pl

KOMENDY
  help              ta instrukcja
  show [--json]     aktualne settings + effective Config
  presets           lista se / se-compact / se-long / chat / lab-flat
  use <preset>      zastosuj preset i zapisz
  set <k> <v>       profile | preset | default_project | memory_path | ui_lang | notes
  set-override k v  override pola Config (np. handoff_max_facts 4)
  set-override k --clear
  wizard            setup krok po kroku
  doctor [--json]   checklista gotowości + positioning vs SaaS
  export-env        HOLON_PROFILE / LLM_* do shella
  keys              dozwolone klucze override
  gui               okienko (tkinter, bez pip)
  lang pl|en        skrót: set ui_lang + zapis

PRESETY
  se           ciągłość agenta (domyślny)
  se-compact   mniej tokenów w handoff
  se-long      większy store / long-horizon
  chat         EriAmo rozmowa
  lab-flat     ablacja bez Prism

ŁAŃCUCH CONFIG
  Config.agent|chat|flat  →  overrides z settings  →  env HOLON_* (wygrywa)

DOKTOR
  Sprawdza: plik settings, memory, agent_boot, AGENTS.md, durable facts,
  hybrid handoff, pojemność store. Pokazuje macierz vs typowa agent-memory SaaS.

WIĘCEJ
  docs/CONFIGURE.md · AGENTS.md · python holon_configure.py --help
""".strip(),
    "en": """
{title}

WHAT THIS IS
  Local SE memory configurator (Grok/CLI) — not a cloud dashboard.
  Writes holon_settings.json (gitignored). This is NOT holon_memory.json
  (mind state / facts store).

QUICK START
  1) python holon_configure.py wizard
  2) python holon_configure.py doctor
  3) python agent_boot.py
  GUI: python holon_configure.py gui

LANGUAGE (PL / EN)
  • One-shot:   python holon_configure.py --lang en help
  • Persistent: python holon_configure.py set ui_lang en
  • Alias:      python holon_configure.py lang en
  • Env:        set HOLON_UI_LANG=en
  • GUI:        Language switch
  Order: --lang → HOLON_UI_LANG → ui_lang in file → pl

COMMANDS
  help              this guide
  show [--json]     current settings + effective Config
  presets           list se / se-compact / se-long / chat / lab-flat
  use <preset>      apply preset and save
  set <k> <v>       profile | preset | default_project | memory_path | ui_lang | notes
  set-override k v  Config override (e.g. handoff_max_facts 4)
  set-override k --clear
  wizard            step-by-step setup
  doctor [--json]   readiness checklist + SaaS positioning
  export-env        HOLON_PROFILE / LLM_* for the shell
  keys              allowed override keys
  gui               window (tkinter, no extra pip)
  lang pl|en        shortcut: set ui_lang + save

PRESETS
  se           agent continuity (default)
  se-compact   fewer handoff tokens
  se-long      larger store / long-horizon
  chat         EriAmo conversation
  lab-flat     ablation without Prism

CONFIG CHAIN
  Config.agent|chat|flat  →  settings overrides  →  env HOLON_* (wins)

DOCTOR
  Checks: settings file, memory, agent_boot, AGENTS.md, durable facts,
  hybrid handoff, store capacity. Shows matrix vs typical SaaS agent-memory.

MORE
  docs/CONFIGURE.md · AGENTS.md · python holon_configure.py --help
""".strip(),
}


def t(lang: str, key: str, **kw: Any) -> str:
    pack = MSG.get(normalize_lang(lang)) or MSG["pl"]
    s = pack.get(key) or MSG["pl"].get(key) or key
    return s.format(**kw) if kw else s


def _lang_of(args: argparse.Namespace) -> str:
    return getattr(args, "lang_resolved", None) or resolve_ui_lang(
        getattr(args, "lang", None)
    )


def _print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def cmd_help(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    body = HELP_BODY.get(lang) or HELP_BODY["pl"]
    print(body.format(title=t(lang, "help_title")))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    s = load_settings(args.path)
    if args.json:
        _print_json(public_summary(s))
        return 0
    cfg = load_config(settings=s)
    path = args.path or default_settings_path()
    print(t(lang, "settings_hdr"))
    print(f"  {t(lang, 'file'):16}: {path}")
    print(f"  {t(lang, 'exists'):16}: {Path(path).is_file()}")
    print(f"  {t(lang, 'profile'):16}: {s.get('profile')}")
    print(f"  {t(lang, 'preset'):16}: {s.get('preset')}")
    print(f"  {t(lang, 'ui_lang'):16}: {s.get('ui_lang') or 'pl'}")
    print(
        f"  {t(lang, 'default_project'):16}: "
        f"{s.get('default_project') or t(lang, 'meta_env')}"
    )
    print(f"  {t(lang, 'memory_path'):16}: {s.get('memory_path')}")
    print(f"  {t(lang, 'overrides'):16}: {s.get('overrides') or {}}")
    print(f"  {t(lang, 'effective')}:")
    print(
        f"    top_n_recall={cfg.top_n_recall}  prune_max={cfg.hard_prune_store_max}"
    )
    print(
        f"    handoff facts/work={cfg.handoff_max_facts}/{cfg.handoff_max_work}  "
        f"hybrid={cfg.handoff_hybrid_since}"
    )
    print(
        f"    crystallize_sim={cfg.crystallize_sim_threshold}  prism={cfg.use_prism}"
    )
    print(
        f"    llm={cfg.llm_backend} model={cfg.llm_model or '-'} "
        f"url={cfg.llm_base_url or '-'}"
    )
    return 0


def cmd_presets(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    for name in PRESETS:
        label, desc = preset_text(name, lang)
        prof = PRESETS[name]["profile"]
        print(f"{name:12}  [{prof}]  {label}")
        print(f"              {desc}")
        if PRESETS[name].get("overrides"):
            print(f"              overrides={PRESETS[name]['overrides']}")
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    s = load_settings(args.path)
    try:
        s = apply_preset(args.preset, s)
    except ValueError as e:
        print(f"{t(lang, 'error')}: {e}", file=sys.stderr)
        return 2
    # keep language when applying preset
    if getattr(args, "lang", None):
        s["ui_lang"] = normalize_lang(args.lang)
    path = save_settings(s, args.path)
    print(f"preset={args.preset} profile={s['profile']} → {path}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    s = load_settings(args.path)
    key = args.key.strip()
    val = args.value
    simple = {
        "profile": "profile",
        "preset": "preset",
        "default_project": "default_project",
        "memory_path": "memory_path",
        "ui_lang": "ui_lang",
        "lang": "ui_lang",
        "language": "ui_lang",
        "notes": "notes",
    }
    if key not in simple:
        print(
            f"{t(lang, 'error')}: {t(lang, 'unknown_key')} {key!r}. "
            + t(lang, "use_set_override", keys=", ".join(sorted(set(simple.values())))),
            file=sys.stderr,
        )
        return 2
    field = simple[key]
    if field == "profile":
        val = str(val).strip().lower()
        if val not in ("agent", "chat", "flat"):
            print(f"{t(lang, 'error')}: {t(lang, 'profile_must')}", file=sys.stderr)
            return 2
    if field == "preset":
        val = str(val).strip().lower()
        if val and val not in PRESETS:
            print(f"{t(lang, 'error')}: {t(lang, 'unknown_preset')} {val}", file=sys.stderr)
            return 2
    if field == "ui_lang":
        val = normalize_lang(str(val))
    s[field] = val
    s = normalize_settings(s)
    path = save_settings(s, args.path)
    print(f"set {field}={s[field]!r} → {path}")
    return 0


def cmd_lang(args: argparse.Namespace) -> int:
    """Skrót: zapisz ui_lang."""
    args.key = "ui_lang"
    args.value = args.code
    return cmd_set(args)


def cmd_set_override(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    s = load_settings(args.path)
    key = args.key.strip()
    if key not in SAFE_OVERRIDE_KEYS:
        print(f"{t(lang, 'error')}: {t(lang, 'override_not_allowed')}: {key}", file=sys.stderr)
        print(f"{t(lang, 'allowed')}:", ", ".join(sorted(SAFE_OVERRIDE_KEYS)), file=sys.stderr)
        return 2
    overs = dict(s.get("overrides") or {})
    if args.clear or args.value in (None, "", "null", "NONE"):
        overs.pop(key, None)
        print(f"{t(lang, 'cleared_override')} {key}")
    else:
        overs[key] = args.value
        print(f"override {key}={args.value!r}")
    s["overrides"] = overs
    path = save_settings(s, args.path)
    print(f"{t(lang, 'saved')} → {path}")
    return 0


def cmd_wizard(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    print(t(lang, "wizard_title"))
    print(t(lang, "wizard_hint") + "\n")
    s = load_settings(args.path)

    print(t(lang, "presets_hdr"))
    for name in PRESETS:
        label, _ = preset_text(name, lang)
        print(f"  {name:12} — {label}")
    preset = input(f"preset [{s.get('preset') or 'se'}]: ").strip() or (
        s.get("preset") or "se"
    )
    try:
        s = apply_preset(preset, s)
    except ValueError as e:
        print(f"{t(lang, 'error')}: {e}", file=sys.stderr)
        return 2

    cur_lang = s.get("ui_lang") or lang
    ui = input(f"ui_lang / language [{cur_lang}]: ").strip()
    if ui:
        s["ui_lang"] = normalize_lang(ui)
    elif args.lang:
        s["ui_lang"] = normalize_lang(args.lang)

    proj = input(f"default_project [{s.get('default_project') or ''}]: ").strip()
    if proj:
        s["default_project"] = proj

    mem = input(f"memory_path [{s.get('memory_path')}]: ").strip()
    if mem:
        s["memory_path"] = mem

    llm = input(
        f"llm_backend [{s.get('overrides', {}).get('llm_backend', 'auto')}]: "
    ).strip()
    if llm:
        s.setdefault("overrides", {})["llm_backend"] = llm
    model = input("llm_model []: ").strip()
    if model:
        s.setdefault("overrides", {})["llm_model"] = model
    url = input("llm_base_url []: ").strip()
    if url:
        s.setdefault("overrides", {})["llm_base_url"] = url

    path = save_settings(s, args.path)
    print(f"\n{t(lang, 'saved')} → {path}")
    print(t(lang, "next_boot"))
    print(t(lang, "next_doctor"))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    rep = doctor(root=ROOT, settings_path=args.path)
    if args.json:
        _print_json(rep)
        return 0 if rep.get("ok") else 1
    print(f"{t(lang, 'doctor_title')}  score={rep['score']}%  ok={rep['ok']}")
    print(f"\n{t(lang, 'checks')}:")
    for c in rep["checks"]:
        mark = "OK " if c["ok"] else "!! "
        print(f"  {mark} {c['name']}: {c['detail']}")
    print(f"\n{t(lang, 'positioning')}:")
    for row in rep["positioning"]:
        print(f"  • {row['capability']}")
        print(f"      Karmin_Ae={row['karmin_ae']}  typical_saas={row['typical_saas_memory']}")
    print(f"\n{t(lang, 'effective_cfg')}:")
    for k, v in rep["config_effective"].items():
        print(f"  {k}: {v}")
    print(f"\n{t(lang, 'next')}:")
    for n in rep["next"]:
        print(f"  {n}")
    return 0 if rep.get("ok") else 1


def cmd_export_env(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    s = load_settings(args.path)
    lines = export_env_lines(s)
    # also export UI lang for shells
    lines.append(f"HOLON_UI_LANG={s.get('ui_lang') or 'pl'}")
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"{t(lang, 'wrote')} {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    lang = _lang_of(args)
    print(t(lang, "top_keys"))
    print(t(lang, "overrides_hdr"))
    help_map = dict(config_field_help())
    for k in sorted(SAFE_OVERRIDE_KEYS):
        h = help_map.get(k, "")
        print(f"  {k:28} {h}")
    return 0


# ── GUI ───────────────────────────────────────────────────────────────────


def cmd_gui(args: argparse.Namespace) -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        print(t(_lang_of(args), "tk_missing"), file=sys.stderr)
        return 2

    settings_path = args.path or str(default_settings_path())
    s = load_settings(settings_path)
    lang_state = {"lang": resolve_ui_lang(args.lang, settings=s)}

    root = tk.Tk()
    root.minsize(540, 520)
    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frm.columnconfigure(1, weight=1)

    title_var = tk.StringVar()
    sub_var = tk.StringVar()
    desc_var = tk.StringVar()
    status = tk.StringVar()

    widgets: Dict[str, Any] = {}

    def row_label(r: int, text: str, key: str = "") -> ttk.Label:
        lab = ttk.Label(frm, text=text)
        lab.grid(row=r, column=0, sticky="w", pady=3)
        if key:
            widgets[key] = lab
        return lab

    ttk.Label(frm, textvariable=title_var, font=("", 12, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 4)
    )
    ttk.Label(frm, textvariable=sub_var, foreground="#444").grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(0, 10)
    )

    lang_var = tk.StringVar(value=lang_state["lang"])
    row_label(2, "Language", "lab_lang")
    lang_cb = ttk.Combobox(
        frm, textvariable=lang_var, values=["pl", "en"], state="readonly", width=10
    )
    lang_cb.grid(row=2, column=1, sticky="w", pady=3)

    preset_var = tk.StringVar(value=s.get("preset") or "se")
    row_label(3, "Preset", "lab_preset")
    preset_cb = ttk.Combobox(
        frm,
        textvariable=preset_var,
        values=list(PRESETS.keys()),
        state="readonly",
        width=28,
    )
    preset_cb.grid(row=3, column=1, sticky="ew", pady=3)

    profile_var = tk.StringVar(value=s.get("profile") or "agent")
    row_label(4, "Profile", "lab_profile")
    ttk.Combobox(
        frm,
        textvariable=profile_var,
        values=["agent", "chat", "flat"],
        state="readonly",
        width=28,
    ).grid(row=4, column=1, sticky="ew", pady=3)

    ttk.Label(frm, textvariable=desc_var, wraplength=380).grid(
        row=5, column=0, columnspan=3, sticky="w", pady=4
    )

    proj_var = tk.StringVar(value=s.get("default_project") or "")
    row_label(6, "default_project", "lab_proj")
    ttk.Entry(frm, textvariable=proj_var).grid(row=6, column=1, sticky="ew", pady=3)

    mem_var = tk.StringVar(value=s.get("memory_path") or "holon_memory.json")
    row_label(7, "memory_path", "lab_mem")
    ttk.Entry(frm, textvariable=mem_var).grid(row=7, column=1, sticky="ew", pady=3)

    ttk.Separator(frm).grid(row=8, column=0, columnspan=3, sticky="ew", pady=8)

    overs = dict(s.get("overrides") or {})
    facts_var = tk.StringVar(value=str(overs.get("handoff_max_facts", "")))
    row_label(9, "handoff_max_facts", "lab_facts")
    ttk.Entry(frm, textvariable=facts_var, width=12).grid(row=9, column=1, sticky="w", pady=3)

    work_var = tk.StringVar(value=str(overs.get("handoff_max_work", "")))
    row_label(10, "handoff_max_work", "lab_work")
    ttk.Entry(frm, textvariable=work_var, width=12).grid(row=10, column=1, sticky="w", pady=3)

    llm_var = tk.StringVar(value=str(overs.get("llm_backend", "auto")))
    row_label(11, "llm_backend", "lab_llm")
    ttk.Combobox(
        frm,
        textvariable=llm_var,
        values=["auto", "ollama", "local", "openai", "mock"],
        width=28,
    ).grid(row=11, column=1, sticky="ew", pady=3)

    model_var = tk.StringVar(value=str(overs.get("llm_model", "")))
    row_label(12, "llm_model", "lab_model")
    ttk.Entry(frm, textvariable=model_var).grid(row=12, column=1, sticky="ew", pady=3)

    url_var = tk.StringVar(value=str(overs.get("llm_base_url", "")))
    row_label(13, "llm_base_url", "lab_url")
    ttk.Entry(frm, textvariable=url_var).grid(row=13, column=1, sticky="ew", pady=3)

    ttk.Label(frm, textvariable=status, foreground="#333").grid(
        row=14, column=0, columnspan=3, sticky="w", pady=(10, 4)
    )

    btns = ttk.Frame(frm)
    btns.grid(row=15, column=0, columnspan=3, sticky="ew", pady=12)
    btn_save = ttk.Button(btns, text="Save")
    btn_doc = ttk.Button(btns, text="Doctor")
    btn_boot = ttk.Button(btns, text="Boot")
    btn_help = ttk.Button(btns, text="Help")
    btn_close = ttk.Button(btns, text="Close", command=root.destroy)
    for b in (btn_save, btn_doc, btn_boot, btn_help):
        b.pack(side="left", padx=4)
    btn_close.pack(side="right", padx=4)

    def refresh_i18n(_e=None) -> None:
        lang = normalize_lang(lang_var.get())
        lang_state["lang"] = lang
        root.title(t(lang, "app_title"))
        title_var.set(t(lang, "app_title"))
        sub_var.set(t(lang, "app_sub"))
        if "lab_lang" in widgets:
            widgets["lab_lang"].configure(text=t(lang, "lang"))
        label, desc = preset_text(preset_var.get() or "se", lang)
        desc_var.set(desc)
        btn_save.configure(text=t(lang, "btn_save"))
        btn_doc.configure(text=t(lang, "btn_doctor"))
        btn_boot.configure(text=t(lang, "btn_boot"))
        btn_help.configure(text=t(lang, "btn_help"))
        btn_close.configure(text=t(lang, "btn_close"))
        status.set(t(lang, "status_file", path=settings_path))

    def on_preset(_e=None) -> None:
        name = preset_var.get()
        if name in PRESETS:
            profile_var.set(PRESETS[name]["profile"])
            _, desc = preset_text(name, lang_state["lang"])
            desc_var.set(desc)

    def collect() -> Dict[str, Any]:
        data = normalize_settings(
            {
                "profile": profile_var.get(),
                "preset": preset_var.get(),
                "default_project": proj_var.get().strip(),
                "memory_path": mem_var.get().strip() or "holon_memory.json",
                "ui_lang": normalize_lang(lang_var.get()),
                "overrides": {},
            }
        )
        try:
            data = apply_preset(preset_var.get() or "se", data)
        except ValueError:
            pass
        data["profile"] = profile_var.get()
        data["default_project"] = proj_var.get().strip()
        data["memory_path"] = mem_var.get().strip() or "holon_memory.json"
        data["ui_lang"] = normalize_lang(lang_var.get())
        o: Dict[str, Any] = dict(data.get("overrides") or {})
        if facts_var.get().strip():
            o["handoff_max_facts"] = facts_var.get().strip()
        if work_var.get().strip():
            o["handoff_max_work"] = work_var.get().strip()
        if llm_var.get().strip():
            o["llm_backend"] = llm_var.get().strip()
        if model_var.get().strip():
            o["llm_model"] = model_var.get().strip()
        if url_var.get().strip():
            o["llm_base_url"] = url_var.get().strip()
        data["overrides"] = o
        return normalize_settings(data)

    def do_save() -> None:
        lang = lang_state["lang"]
        data = collect()
        path = save_settings(data, settings_path)
        status.set(t(lang, "status_saved", path=path))
        messagebox.showinfo("Karmin_Ae", t(lang, "msg_saved", path=path))

    def do_doctor() -> None:
        lang = lang_state["lang"]
        save_settings(collect(), settings_path)
        rep = doctor(root=ROOT, settings_path=settings_path)
        lines = [f"score={rep['score']}% ok={rep['ok']}", ""]
        for c in rep["checks"]:
            lines.append(f"{'OK' if c['ok'] else '!!'} {c['name']}: {c['detail']}")
        lines.append("")
        lines.append(t(lang, "positioning") + ":")
        for row in rep["positioning"][:5]:
            lines.append(
                f"  {row['capability']}: Ae={row['karmin_ae']} saas={row['typical_saas_memory']}"
            )
        messagebox.showinfo(t(lang, "btn_doctor"), "\n".join(lines))
        status.set(t(lang, "status_doctor", score=rep["score"]))

    def do_boot() -> None:
        messagebox.showinfo(t(lang_state["lang"], "btn_boot"), t(lang_state["lang"], "msg_boot"))

    def do_help() -> None:
        lang = lang_state["lang"]
        body = HELP_BODY.get(lang) or HELP_BODY["pl"]
        messagebox.showinfo(
            t(lang, "btn_help"),
            body.format(title=t(lang, "help_title"))[:3500],
        )

    btn_save.configure(command=do_save)
    btn_doc.configure(command=do_doctor)
    btn_boot.configure(command=do_boot)
    btn_help.configure(command=do_help)
    lang_cb.bind("<<ComboboxSelected>>", refresh_i18n)
    preset_cb.bind("<<ComboboxSelected>>", on_preset)

    refresh_i18n()
    on_preset()
    root.mainloop()
    return 0


def build_parser(lang: str = "pl") -> argparse.ArgumentParser:
    lang = normalize_lang(lang)
    p = argparse.ArgumentParser(
        prog="holon_configure",
        description=t(lang, "argparse_desc"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python holon_configure.py help\n"
            "  python holon_configure.py --lang en help\n"
            "  python holon_configure.py set ui_lang en\n"
            "  python holon_configure.py wizard\n"
            "  python holon_configure.py gui\n"
        ),
    )
    p.add_argument("--path", default="", help=t(lang, "arg_path"))
    p.add_argument(
        "--lang",
        default="",
        choices=["", "pl", "en"],
        help=t(lang, "arg_lang"),
    )
    sub = p.add_subparsers(dest="cmd", required=False)

    def add(name: str, help_key: str, **kwargs):
        sp = sub.add_parser(name, help=t(lang, help_key), **kwargs)
        return sp

    sp = add("help", "h_help")
    sp.set_defaults(func=cmd_help)

    sp = add("show", "h_show")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_show)

    sp = add("presets", "h_presets")
    sp.set_defaults(func=cmd_presets)

    sp = add("use", "h_use")
    sp.add_argument("preset", help="se | se-compact | se-long | chat | lab-flat")
    sp.set_defaults(func=cmd_use)

    sp = add("set", "h_set")
    sp.add_argument("key")
    sp.add_argument("value")
    sp.set_defaults(func=cmd_set)

    sp = add("lang", "h_lang")
    sp.add_argument("code", choices=["pl", "en"])
    sp.set_defaults(func=cmd_lang)

    sp = add("set-override", "h_set_override")
    sp.add_argument("key")
    sp.add_argument("value", nargs="?", default="")
    sp.add_argument("--clear", action="store_true")
    sp.set_defaults(func=cmd_set_override)

    sp = add("wizard", "h_wizard")
    sp.set_defaults(func=cmd_wizard)

    sp = add("doctor", "h_doctor")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_doctor)

    sp = add("export-env", "h_export")
    sp.add_argument("--out", default="", help="output file")
    sp.set_defaults(func=cmd_export_env)

    sp = add("keys", "h_keys")
    sp.set_defaults(func=cmd_keys)

    sp = add("gui", "h_gui")
    sp.set_defaults(func=cmd_gui)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # pre-parse --lang for argparse help language
    pre_lang = None
    if "--lang" in argv:
        i = argv.index("--lang")
        if i + 1 < len(argv):
            pre_lang = argv[i + 1]
    lang_hint = resolve_ui_lang(pre_lang)
    p = build_parser(lang_hint)
    args = p.parse_args(argv)
    args.path = args.path or None
    args.lang = (args.lang or "").strip() or None
    args.lang_resolved = resolve_ui_lang(args.lang)
    if not args.cmd:
        return cmd_help(args)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
