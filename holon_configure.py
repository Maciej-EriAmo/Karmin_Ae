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
        "err_url_not_http": (
            "llm_base_url musi być http(s)://… (API OpenAI-compatible).\n"
            "Dla Ollamy zostaw puste albo wpisz: http://localhost:11434/v1\n"
            "Ścieżka do folderu modeli (np. .ollama\\models) NIE jest base_url."
        ),
        "err_backend": "llm_backend musi być jednym z: {choices}",
        "err_int": "{key} musi być liczbą całkowitą, dostano: {value!r}",
        "hint_url": "puste = Ollama auto · np. http://localhost:11434/v1 · NIE folder modeli",
        "hint_model": "np. gemma3:4b (nazwa z ollama list)",
        "unknown_key": "nieznany klucz",
        "use_set_override": "Użyj: {keys} lub set-override",
        "profile_must": "profile musi być agent|chat|flat",
        "unknown_preset": "nieznany preset",
        "override_not_allowed": "override niedozwolony",
        "allowed": "dozwolone",
        "cleared_override": "wyczyszczono override",
        "wizard_title": "=== Karmin_Ae wizard (pamięć SE) ===",
        "wizard_hint": "Enter = zostaw wartość w [nawiasach] · '-' = wyczyść pole",
        "wizard_sec_base": "— Podstawowe —",
        "wizard_sec_llm": "— LLM (Ollama / URL) —",
        "wizard_llm_note": (
            "backend=ollama → model z `ollama list`; base_url zostaw puste.\n"
            "base_url = tylko http(s)://… (API), NIGDY ścieżka do .ollama\\models."
        ),
        "wizard_ask_preset": "preset",
        "wizard_ask_lang": "ui_lang / język",
        "wizard_ask_project": "default_project",
        "wizard_ask_memory": "memory_path",
        "wizard_ask_backend": "llm_backend (auto|ollama|gemini|local|openai|mock)",
        "wizard_ask_model": "llm_model (nazwa Ollamy)",
        "wizard_ask_url": "llm_base_url (HTTP API, puste=auto)",
        "wizard_skip_url": "pomijam niepoprawny llm_base_url",
        "wizard_test": "Przetestować LLM teraz? [T/n]",
        "wizard_test_skip": "pomijam test LLM",
        "next_boot": "Dalej: python agent_boot.py",
        "next_doctor": "       python holon_configure.py doctor",
        "next_chat": "       START_CHAT.cmd  /  python karmin_app.py -c chat",
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
        "btn_ollama": "Ollama",
        "btn_test_llm": "Test LLM",
        "lang": "Język",
        "lab_preset": "Preset",
        "lab_profile": "Profil",
        "lab_proj": "Projekt domyślny",
        "lab_mem": "Plik pamięci",
        "lab_facts": "Max facts (handoff)",
        "lab_work": "Max work (handoff)",
        "lab_llm": "Backend LLM",
        "lab_model": "Model LLM",
        "lab_url": "Base URL (HTTP)",
        "sec_base": "Profil i ścieżki",
        "sec_handoff": "Handoff (opcjonalnie)",
        "sec_llm": "LLM — Ollama / OpenAI-compatible",
        "status_file": "plik: {path}",
        "status_saved": "zapisano → {path}",
        "status_doctor": "doctor score={score}%",
        "status_ollama_up": "Ollama: online (:11434)",
        "status_ollama_down": "Ollama: offline — uruchom `ollama serve`",
        "status_llm_ok": "LLM OK → {model}: {preview}",
        "status_llm_fail": "LLM błąd: {err}",
        "status_llm_none": "Brak klienta LLM (sprawdź backend / ollama serve)",
        "msg_saved": "Zapisano ustawienia:\n{path}",
        "msg_boot": (
            "W terminalu:\n\n"
            "  cd Karmin_Ae\n"
            "  python agent_boot.py\n\n"
            "Settings wczytywane automatycznie (profile, memory_path, overrides)."
        ),
        "msg_ollama_applied": (
            "Ustawiono backend=ollama.\n"
            "Model: {model}\n"
            "Base URL wyczyszczony (auto http://localhost:11434/v1).\n"
            "Zapisz, potem Test LLM."
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
        "err_url_not_http": (
            "llm_base_url must be http(s)://… (OpenAI-compatible API).\n"
            "For Ollama leave empty or use: http://localhost:11434/v1\n"
            "A models folder path (e.g. .ollama\\models) is NOT base_url."
        ),
        "err_backend": "llm_backend must be one of: {choices}",
        "err_int": "{key} must be an integer, got: {value!r}",
        "hint_url": "empty = Ollama auto · e.g. http://localhost:11434/v1 · NOT models folder",
        "hint_model": "e.g. gemma3:4b (name from ollama list)",
        "unknown_key": "unknown key",
        "use_set_override": "Use: {keys} or set-override",
        "profile_must": "profile must be agent|chat|flat",
        "unknown_preset": "unknown preset",
        "override_not_allowed": "override not allowed",
        "allowed": "allowed",
        "cleared_override": "cleared override",
        "wizard_title": "=== Karmin_Ae wizard (SE memory) ===",
        "wizard_hint": "Enter = keep value in [brackets] · '-' = clear field",
        "wizard_sec_base": "— Basics —",
        "wizard_sec_llm": "— LLM (Ollama / URL) —",
        "wizard_llm_note": (
            "backend=ollama → model from `ollama list`; leave base_url empty.\n"
            "base_url = http(s)://… API only, NEVER a path to .ollama\\models."
        ),
        "wizard_ask_preset": "preset",
        "wizard_ask_lang": "ui_lang / language",
        "wizard_ask_project": "default_project",
        "wizard_ask_memory": "memory_path",
        "wizard_ask_backend": "llm_backend (auto|ollama|gemini|local|openai|mock)",
        "wizard_ask_model": "llm_model (Ollama name)",
        "wizard_ask_url": "llm_base_url (HTTP API, empty=auto)",
        "wizard_skip_url": "skipping invalid llm_base_url",
        "wizard_test": "Test LLM now? [Y/n]",
        "wizard_test_skip": "skipping LLM test",
        "next_boot": "Next: python agent_boot.py",
        "next_doctor": "      python holon_configure.py doctor",
        "next_chat": "      START_CHAT.cmd  /  python karmin_app.py -c chat",
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
        "btn_ollama": "Ollama",
        "btn_test_llm": "Test LLM",
        "lang": "Language",
        "lab_preset": "Preset",
        "lab_profile": "Profile",
        "lab_proj": "Default project",
        "lab_mem": "Memory file",
        "lab_facts": "Max facts (handoff)",
        "lab_work": "Max work (handoff)",
        "lab_llm": "LLM backend",
        "lab_model": "LLM model",
        "lab_url": "Base URL (HTTP)",
        "sec_base": "Profile & paths",
        "sec_handoff": "Handoff (optional)",
        "sec_llm": "LLM — Ollama / OpenAI-compatible",
        "status_file": "file: {path}",
        "status_saved": "saved → {path}",
        "status_doctor": "doctor score={score}%",
        "status_ollama_up": "Ollama: online (:11434)",
        "status_ollama_down": "Ollama: offline — run `ollama serve`",
        "status_llm_ok": "LLM OK → {model}: {preview}",
        "status_llm_fail": "LLM error: {err}",
        "status_llm_none": "No LLM client (check backend / ollama serve)",
        "msg_saved": "Settings saved:\n{path}",
        "msg_boot": (
            "In a terminal:\n\n"
            "  cd Karmin_Ae\n"
            "  python agent_boot.py\n\n"
            "Settings load automatically (profile, memory_path, overrides)."
        ),
        "msg_ollama_applied": (
            "Set backend=ollama.\n"
            "Model: {model}\n"
            "Base URL cleared (auto http://localhost:11434/v1).\n"
            "Save, then Test LLM."
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
  1) START.cmd  (albo: python karmin_app.py)  ← norma dla CZŁOWIEKA
  2) python holon_configure.py wizard         ← setup CLI
  3) python holon_configure.py doctor
  4) python agent_boot.py                     ← norma dla AGENTA
  Configure-only GUI: python holon_configure.py gui
  Instrukcja: docs/USER_GUIDE.md

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
  1) START.cmd  (or: python karmin_app.py)   ← normal HUMAN path
  2) python holon_configure.py wizard        ← CLI setup
  3) python holon_configure.py doctor
  4) python agent_boot.py                    ← AGENT path
  Configure-only GUI: python holon_configure.py gui
  Guide: docs/USER_GUIDE.md

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


LLM_BACKENDS = ("auto", "ollama", "gemini", "local", "openai", "mock", "groq", "deepseek")
OLLAMA_DEFAULT_MODEL = "gemma3:4b"
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"
OLLAMA_DEFAULT_URL = "http://localhost:11434/v1"
_CLEAR_TOKENS = frozenset({"-", "clear", "none", "null", "~"})


def _lang_of(args: argparse.Namespace) -> str:
    return getattr(args, "lang_resolved", None) or resolve_ui_lang(
        getattr(args, "lang", None)
    )


def _print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def _is_http_url(value: str) -> bool:
    u = (value or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def _parse_optional_int(raw: str, key: str, lang: str) -> Optional[int]:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError as e:
        raise ValueError(t(lang, "err_int", key=key, value=s)) from e


def _validate_backend(raw: str, lang: str) -> str:
    be = (raw or "auto").strip().lower() or "auto"
    if be not in LLM_BACKENDS:
        raise ValueError(t(lang, "err_backend", choices=", ".join(LLM_BACKENDS)))
    return be


def _validate_base_url(raw: str, lang: str) -> Optional[str]:
    """Zwraca URL albo None (puste). Rzuca ValueError dla ścieżek dyskowych itd."""
    s = (raw or "").strip()
    if not s:
        return None
    if not _is_http_url(s):
        raise ValueError(t(lang, "err_url_not_http"))
    return s.rstrip("/")


def _prompt(label: str, default: str = "") -> str:
    """Input z domyślną w nawiasach. '-' czyści do pustego stringa."""
    shown = default if default is not None else ""
    raw = input(f"{label} [{shown}]: ").strip()
    if raw == "":
        return shown
    if raw.lower() in _CLEAR_TOKENS:
        return ""
    return raw


def _probe_ollama() -> bool:
    try:
        from holon_llm import describe_llm_slot

        return bool(describe_llm_slot().get("ollama_up"))
    except Exception:
        return False


def _test_llm_client(
    backend: str,
    model: str,
    base_url: str = "",
) -> Dict[str, Any]:
    """Krótki ping LLM. Zwraca dict: ok, model, preview|error, ollama_up."""
    from holon_llm import build_llm_client, describe_llm_slot

    slot = describe_llm_slot()
    out: Dict[str, Any] = {
        "ok": False,
        "ollama_up": bool(slot.get("ollama_up")),
        "model": model or "",
        "preview": "",
        "error": "",
    }
    try:
        client = build_llm_client(
            backend=backend or "auto",
            model=model or None,
            base_url=base_url or None,
            quiet=True,
        )
    except Exception as e:
        out["error"] = str(e)
        return out
    if client is None:
        out["error"] = "no_client"
        return out
    out["model"] = getattr(client, "model", model) or model
    try:
        text = client.chat_completion(
            [{"role": "user", "content": "Reply with exactly: OK"}],
            temperature=0.0,
            max_tokens=8,
        )
    except Exception as e:
        out["error"] = str(e)
        return out
    preview = (text or "").strip().replace("\n", " ")
    if preview.startswith("[Błąd") or preview.startswith("[Error"):
        out["error"] = preview
        return out
    out["ok"] = True
    out["preview"] = preview[:120]
    return out


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
    overs = dict(s.get("overrides") or {})

    # ── base ──────────────────────────────────────────────────────────
    print(t(lang, "wizard_sec_base"))
    print(t(lang, "presets_hdr"))
    for name in PRESETS:
        label, _ = preset_text(name, lang)
        print(f"  {name:12} — {label}")

    preset = _prompt(t(lang, "wizard_ask_preset"), s.get("preset") or "se")
    try:
        s = apply_preset(preset, s)
    except ValueError as e:
        print(f"{t(lang, 'error')}: {e}", file=sys.stderr)
        return 2
    # apply_preset zachowuje llm_*; odśwież lokalną kopię
    overs = dict(s.get("overrides") or {})

    cur_lang = s.get("ui_lang") or lang
    ui = _prompt(t(lang, "wizard_ask_lang"), cur_lang)
    s["ui_lang"] = normalize_lang(ui or cur_lang)

    s["default_project"] = _prompt(
        t(lang, "wizard_ask_project"), s.get("default_project") or ""
    )
    s["memory_path"] = (
        _prompt(t(lang, "wizard_ask_memory"), s.get("memory_path") or "holon_memory.json")
        or "holon_memory.json"
    )

    # ── LLM ───────────────────────────────────────────────────────────
    print()
    print(t(lang, "wizard_sec_llm"))
    print(t(lang, "wizard_llm_note"))
    ollama_mark = "online" if _probe_ollama() else "offline"
    print(f"  Ollama: {ollama_mark}  (localhost:11434)\n")

    cur_be = str(overs.get("llm_backend") or "auto")
    cur_model = str(overs.get("llm_model") or "")
    cur_url = str(overs.get("llm_base_url") or "")

    be_raw = _prompt(t(lang, "wizard_ask_backend"), cur_be)
    try:
        be = _validate_backend(be_raw or "auto", lang)
    except ValueError as e:
        print(f"{t(lang, 'error')}: {e}", file=sys.stderr)
        return 2
    overs["llm_backend"] = be

    model = _prompt(t(lang, "wizard_ask_model"), cur_model)
    if model:
        overs["llm_model"] = model
    else:
        overs.pop("llm_model", None)

    # Ollama: domyślnie bez base_url (auto :11434/v1)
    url_default = cur_url
    if be == "ollama" and not cur_url:
        url_default = ""
    url_raw = _prompt(t(lang, "wizard_ask_url"), url_default)
    if url_raw:
        try:
            url = _validate_base_url(url_raw, lang)
        except ValueError as e:
            print(f"{t(lang, 'error')}: {e}")
            print(f"  ({t(lang, 'wizard_skip_url')})")
            url = None
        if url:
            overs["llm_base_url"] = url
        else:
            overs.pop("llm_base_url", None)
    else:
        overs.pop("llm_base_url", None)

    s["overrides"] = overs
    path = save_settings(s, args.path)
    print(f"\n{t(lang, 'saved')} → {path}")

    # opcjonalny test
    ans = input(f"{t(lang, 'wizard_test')} ").strip().lower()
    if ans in ("", "t", "y", "tak", "yes", "1"):
        res = _test_llm_client(
            backend=str(overs.get("llm_backend") or "auto"),
            model=str(overs.get("llm_model") or ""),
            base_url=str(overs.get("llm_base_url") or ""),
        )
        if res["ok"]:
            print(t(lang, "status_llm_ok", model=res["model"], preview=res["preview"]))
        elif res["error"] == "no_client":
            print(t(lang, "status_llm_none"))
            if not res["ollama_up"]:
                print(t(lang, "status_ollama_down"))
        else:
            print(t(lang, "status_llm_fail", err=res["error"] or "?"))
    else:
        print(t(lang, "wizard_test_skip"))

    print(t(lang, "next_boot"))
    print(t(lang, "next_doctor"))
    print(t(lang, "next_chat"))
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
    # Pełne overrides z pliku — collect zachowa klucze spoza formularza
    base_overrides = dict(s.get("overrides") or {})

    root = tk.Tk()
    root.minsize(580, 640)
    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frm.columnconfigure(1, weight=1)

    title_var = tk.StringVar()
    sub_var = tk.StringVar()
    desc_var = tk.StringVar()
    status = tk.StringVar()
    llm_status = tk.StringVar()

    widgets: Dict[str, Any] = {}
    row_i = {"n": 0}

    def next_row() -> int:
        r = row_i["n"]
        row_i["n"] += 1
        return r

    def section(key: str) -> None:
        r = next_row()
        if r > 2:
            ttk.Separator(frm).grid(
                row=r, column=0, columnspan=3, sticky="ew", pady=(10, 6)
            )
            r = next_row()
        lab = ttk.Label(frm, text="", font=("", 9, "bold"))
        lab.grid(row=r, column=0, columnspan=3, sticky="w")
        widgets[key] = lab

    # header
    r = next_row()
    ttk.Label(frm, textvariable=title_var, font=("", 12, "bold")).grid(
        row=r, column=0, columnspan=3, sticky="w", pady=(0, 2)
    )
    r = next_row()
    ttk.Label(frm, textvariable=sub_var, foreground="#444").grid(
        row=r, column=0, columnspan=3, sticky="w", pady=(0, 8)
    )

    # language
    r = next_row()
    widgets["lab_lang"] = ttk.Label(frm, text="")
    widgets["lab_lang"].grid(row=r, column=0, sticky="w", pady=3)
    lang_var = tk.StringVar(value=lang_state["lang"])
    lang_cb = ttk.Combobox(
        frm, textvariable=lang_var, values=["pl", "en"], state="readonly", width=10
    )
    lang_cb.grid(row=r, column=1, sticky="w", pady=3)

    section("sec_base")

    r = next_row()
    widgets["lab_preset"] = ttk.Label(frm, text="")
    widgets["lab_preset"].grid(row=r, column=0, sticky="w", pady=3)
    preset_var = tk.StringVar(value=s.get("preset") or "se")
    preset_cb = ttk.Combobox(
        frm,
        textvariable=preset_var,
        values=list(PRESETS.keys()),
        state="readonly",
        width=28,
    )
    preset_cb.grid(row=r, column=1, sticky="ew", pady=3)

    r = next_row()
    widgets["lab_profile"] = ttk.Label(frm, text="")
    widgets["lab_profile"].grid(row=r, column=0, sticky="w", pady=3)
    profile_var = tk.StringVar(value=s.get("profile") or "agent")
    ttk.Combobox(
        frm,
        textvariable=profile_var,
        values=["agent", "chat", "flat"],
        state="readonly",
        width=28,
    ).grid(row=r, column=1, sticky="ew", pady=3)

    r = next_row()
    ttk.Label(frm, textvariable=desc_var, wraplength=420, foreground="#333").grid(
        row=r, column=0, columnspan=3, sticky="w", pady=4
    )

    r = next_row()
    widgets["lab_proj"] = ttk.Label(frm, text="")
    widgets["lab_proj"].grid(row=r, column=0, sticky="w", pady=3)
    proj_var = tk.StringVar(value=s.get("default_project") or "")
    ttk.Entry(frm, textvariable=proj_var).grid(row=r, column=1, sticky="ew", pady=3)

    r = next_row()
    widgets["lab_mem"] = ttk.Label(frm, text="")
    widgets["lab_mem"].grid(row=r, column=0, sticky="w", pady=3)
    mem_var = tk.StringVar(value=s.get("memory_path") or "holon_memory.json")
    ttk.Entry(frm, textvariable=mem_var).grid(row=r, column=1, sticky="ew", pady=3)

    section("sec_handoff")

    overs = dict(base_overrides)
    r = next_row()
    widgets["lab_facts"] = ttk.Label(frm, text="")
    widgets["lab_facts"].grid(row=r, column=0, sticky="w", pady=3)
    _facts = overs.get("handoff_max_facts")
    facts_var = tk.StringVar("" if _facts in (None, "") else str(_facts))
    ttk.Entry(frm, textvariable=facts_var, width=12).grid(
        row=r, column=1, sticky="w", pady=3
    )

    r = next_row()
    widgets["lab_work"] = ttk.Label(frm, text="")
    widgets["lab_work"].grid(row=r, column=0, sticky="w", pady=3)
    _work = overs.get("handoff_max_work")
    work_var = tk.StringVar("" if _work in (None, "") else str(_work))
    ttk.Entry(frm, textvariable=work_var, width=12).grid(
        row=r, column=1, sticky="w", pady=3
    )

    section("sec_llm")

    r = next_row()
    widgets["lab_llm"] = ttk.Label(frm, text="")
    widgets["lab_llm"].grid(row=r, column=0, sticky="w", pady=3)
    llm_var = tk.StringVar(value=str(overs.get("llm_backend") or "auto"))
    ttk.Combobox(
        frm,
        textvariable=llm_var,
        values=list(LLM_BACKENDS),
        width=28,
    ).grid(row=r, column=1, sticky="ew", pady=3)

    r = next_row()
    widgets["lab_model"] = ttk.Label(frm, text="")
    widgets["lab_model"].grid(row=r, column=0, sticky="w", pady=3)
    model_var = tk.StringVar(value=str(overs.get("llm_model") or ""))
    ttk.Entry(frm, textvariable=model_var).grid(row=r, column=1, sticky="ew", pady=3)
    r = next_row()
    widgets["model_hint"] = ttk.Label(frm, text="", foreground="#666", font=("", 8))
    widgets["model_hint"].grid(row=r, column=1, sticky="w")

    r = next_row()
    widgets["lab_url"] = ttk.Label(frm, text="")
    widgets["lab_url"].grid(row=r, column=0, sticky="w", pady=3)
    url_var = tk.StringVar(value=str(overs.get("llm_base_url") or ""))
    ttk.Entry(frm, textvariable=url_var).grid(row=r, column=1, sticky="ew", pady=3)
    r = next_row()
    widgets["url_hint"] = ttk.Label(frm, text="", foreground="#666", font=("", 8))
    widgets["url_hint"].grid(row=r, column=1, sticky="w")

    r = next_row()
    llm_btns = ttk.Frame(frm)
    llm_btns.grid(row=r, column=0, columnspan=3, sticky="w", pady=(4, 2))
    btn_ollama = ttk.Button(llm_btns)
    btn_test = ttk.Button(llm_btns)
    btn_ollama.pack(side="left", padx=(0, 6))
    btn_test.pack(side="left")

    r = next_row()
    ttk.Label(frm, textvariable=llm_status, foreground="#055", wraplength=480).grid(
        row=r, column=0, columnspan=3, sticky="w", pady=2
    )

    r = next_row()
    ttk.Label(frm, textvariable=status, foreground="#333").grid(
        row=r, column=0, columnspan=3, sticky="w", pady=(10, 4)
    )

    r = next_row()
    btns = ttk.Frame(frm)
    btns.grid(row=r, column=0, columnspan=3, sticky="ew", pady=12)
    btn_save = ttk.Button(btns)
    btn_doc = ttk.Button(btns)
    btn_boot = ttk.Button(btns)
    btn_help = ttk.Button(btns)
    btn_close = ttk.Button(btns, command=root.destroy)
    for b in (btn_save, btn_doc, btn_boot, btn_help):
        b.pack(side="left", padx=4)
    btn_close.pack(side="right", padx=4)

    def refresh_llm_badge() -> None:
        lang = lang_state["lang"]
        if _probe_ollama():
            llm_status.set(t(lang, "status_ollama_up"))
        else:
            llm_status.set(t(lang, "status_ollama_down"))

    def refresh_i18n(_e=None) -> None:
        lang = normalize_lang(lang_var.get())
        lang_state["lang"] = lang
        root.title(t(lang, "app_title"))
        title_var.set(t(lang, "app_title"))
        sub_var.set(t(lang, "app_sub"))
        btn_save.configure(text=t(lang, "btn_save"))
        btn_doc.configure(text=t(lang, "btn_doctor"))
        btn_boot.configure(text=t(lang, "btn_boot"))
        btn_help.configure(text=t(lang, "btn_help"))
        btn_close.configure(text=t(lang, "btn_close"))
        btn_ollama.configure(text=t(lang, "btn_ollama"))
        btn_test.configure(text=t(lang, "btn_test_llm"))
        label_map = {
            "lab_lang": "lang",
            "lab_preset": "lab_preset",
            "lab_profile": "lab_profile",
            "lab_proj": "lab_proj",
            "lab_mem": "lab_mem",
            "lab_facts": "lab_facts",
            "lab_work": "lab_work",
            "lab_llm": "lab_llm",
            "lab_model": "lab_model",
            "lab_url": "lab_url",
            "sec_base": "sec_base",
            "sec_handoff": "sec_handoff",
            "sec_llm": "sec_llm",
            "url_hint": "hint_url",
            "model_hint": "hint_model",
        }
        for wkey, mkey in label_map.items():
            if wkey in widgets:
                widgets[wkey].configure(text=t(lang, mkey))
        _, desc = preset_text(preset_var.get() or "se", lang)
        desc_var.set(desc)
        status.set(t(lang, "status_file", path=settings_path))
        refresh_llm_badge()

    def on_preset(_e=None) -> None:
        """Profil + opis + tylko controlled keys z presetu. LLM bez zmian."""
        name = preset_var.get()
        if name not in PRESETS:
            return
        profile_var.set(PRESETS[name].get("profile", "agent"))
        preset_overs = PRESETS[name].get("overrides") or {}
        if "handoff_max_facts" in preset_overs:
            facts_var.set(str(preset_overs["handoff_max_facts"]))
        if "handoff_max_work" in preset_overs:
            work_var.set(str(preset_overs["handoff_max_work"]))
        if "llm_backend" in preset_overs:
            llm_var.set(str(preset_overs["llm_backend"]))
        if "llm_model" in preset_overs:
            model_var.set(str(preset_overs["llm_model"]))
        if "llm_base_url" in preset_overs:
            url_var.set(str(preset_overs["llm_base_url"]))
        _, desc = preset_text(name, lang_state["lang"])
        desc_var.set(desc)

    def collect() -> Dict[str, Any]:
        lang = lang_state["lang"]
        # Start od aktualnego pliku — nie gub override'ów spoza formularza
        data = load_settings(settings_path)
        data["profile"] = profile_var.get()
        data["preset"] = preset_var.get()
        data["default_project"] = proj_var.get().strip()
        data["memory_path"] = mem_var.get().strip() or "holon_memory.json"
        data["ui_lang"] = normalize_lang(lang_var.get())

        try:
            data = apply_preset(data.get("preset") or "se", data)
        except ValueError:
            pass

        o: Dict[str, Any] = dict(data.get("overrides") or {})
        preset_name = preset_var.get() or "se"
        preset_overs = (PRESETS.get(preset_name) or {}).get("overrides") or {}

        facts = _parse_optional_int(facts_var.get(), "handoff_max_facts", lang)
        if facts is not None:
            o["handoff_max_facts"] = facts
        elif not facts_var.get().strip() and "handoff_max_facts" not in preset_overs:
            o.pop("handoff_max_facts", None)

        work = _parse_optional_int(work_var.get(), "handoff_max_work", lang)
        if work is not None:
            o["handoff_max_work"] = work
        elif not work_var.get().strip() and "handoff_max_work" not in preset_overs:
            o.pop("handoff_max_work", None)

        o["llm_backend"] = _validate_backend(llm_var.get(), lang)

        model_str = model_var.get().strip()
        if model_str:
            o["llm_model"] = model_str
        else:
            o.pop("llm_model", None)

        url_str = url_var.get().strip()
        if url_str:
            url = _validate_base_url(url_str, lang)
            if url:
                o["llm_base_url"] = url
        else:
            o.pop("llm_base_url", None)

        data["overrides"] = o
        # profile z GUI wygrywa nad presetem (user mógł zmienić ręcznie)
        data["profile"] = profile_var.get()
        return normalize_settings(data)

    def do_save() -> None:
        lang = lang_state["lang"]
        try:
            data = collect()
        except ValueError as e:
            messagebox.showerror(t(lang, "error"), str(e))
            return
        path = save_settings(data, settings_path)
        nonlocal base_overrides
        base_overrides = dict(data.get("overrides") or {})
        status.set(t(lang, "status_saved", path=path))
        messagebox.showinfo("Karmin_Ae", t(lang, "msg_saved", path=path))

    def do_doctor() -> None:
        lang = lang_state["lang"]
        try:
            data = collect()
        except ValueError as e:
            messagebox.showerror(t(lang, "error"), str(e))
            return
        save_settings(data, settings_path)
        rep = doctor(root=ROOT, settings_path=settings_path)
        lines = [f"score={rep['score']}% ok={rep['ok']}", ""]
        for c in rep["checks"]:
            lines.append(f"{'OK' if c['ok'] else '!!'} {c['name']}: {c['detail']}")
        lines.append("")
        eff = rep.get("config_effective") or {}
        lines.append(
            f"LLM: {eff.get('llm_backend', '?')} / {eff.get('llm_model') or '-'} / "
            f"{eff.get('llm_base_url') or '(auto)'}"
        )
        messagebox.showinfo(t(lang, "btn_doctor"), "\n".join(lines))
        status.set(t(lang, "status_doctor", score=rep["score"]))
        refresh_llm_badge()

    def do_boot() -> None:
        messagebox.showinfo(
            t(lang_state["lang"], "btn_boot"), t(lang_state["lang"], "msg_boot")
        )

    def do_help() -> None:
        lang = lang_state["lang"]
        body = HELP_BODY.get(lang) or HELP_BODY["pl"]
        messagebox.showinfo(
            t(lang, "btn_help"),
            body.format(title=t(lang, "help_title"))[:3500],
        )

    def do_ollama_preset() -> None:
        lang = lang_state["lang"]
        llm_var.set("ollama")
        if not model_var.get().strip():
            model_var.set(OLLAMA_DEFAULT_MODEL)
        url_var.set("")  # auto :11434/v1
        messagebox.showinfo(
            t(lang, "btn_ollama"),
            t(
                lang,
                "msg_ollama_applied",
                model=model_var.get() or OLLAMA_DEFAULT_MODEL,
            ),
        )
        refresh_llm_badge()

    def do_test_llm() -> None:
        lang = lang_state["lang"]
        try:
            _validate_backend(llm_var.get(), lang)
            url = url_var.get().strip()
            if url:
                _validate_base_url(url, lang)
        except ValueError as e:
            messagebox.showerror(t(lang, "error"), str(e))
            return
        root.config(cursor="watch")
        root.update_idletasks()
        try:
            res = _test_llm_client(
                backend=llm_var.get().strip() or "auto",
                model=model_var.get().strip(),
                base_url=url_var.get().strip(),
            )
        finally:
            root.config(cursor="")
        if res["ok"]:
            msg = t(lang, "status_llm_ok", model=res["model"], preview=res["preview"])
            llm_status.set(msg)
            messagebox.showinfo(t(lang, "btn_test_llm"), msg)
        elif res["error"] == "no_client":
            msg = t(lang, "status_llm_none")
            if not res["ollama_up"]:
                msg += "\n" + t(lang, "status_ollama_down")
            llm_status.set(msg)
            messagebox.showwarning(t(lang, "btn_test_llm"), msg)
        else:
            msg = t(lang, "status_llm_fail", err=res["error"] or "?")
            llm_status.set(msg)
            messagebox.showerror(t(lang, "btn_test_llm"), msg)

    btn_save.configure(command=do_save)
    btn_doc.configure(command=do_doctor)
    btn_boot.configure(command=do_boot)
    btn_help.configure(command=do_help)
    btn_ollama.configure(command=do_ollama_preset)
    btn_test.configure(command=do_test_llm)
    lang_cb.bind("<<ComboboxSelected>>", refresh_i18n)
    preset_cb.bind("<<ComboboxSelected>>", on_preset)

    refresh_i18n()
    # NIE wołaj on_preset() na starcie — nadpisywałoby wartości z pliku
    _, desc0 = preset_text(preset_var.get() or "se", lang_state["lang"])
    desc_var.set(desc0)
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