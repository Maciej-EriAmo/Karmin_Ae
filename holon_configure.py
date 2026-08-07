#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
holon_configure.py — konfigurator Karmin_Ae (CLI + opcjonalne GUI).

  python holon_configure.py show
  python holon_configure.py presets
  python holon_configure.py use se-compact
  python holon_configure.py set default_project Karmazyn
  python holon_configure.py set-override handoff_max_facts 4
  python holon_configure.py wizard
  python holon_configure.py doctor
  python holon_configure.py export-env
  python holon_configure.py gui

Cel produktowy: jedna powierzchnia setupu (profile / handoff / LLM / doctor),
żeby lokalna pamięć SE była „gotowa w 30 s” — nie chmura z dashboardem.
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
    normalize_settings,
    public_summary,
    save_settings,
)


def _print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def cmd_show(args: argparse.Namespace) -> int:
    s = load_settings(args.path)
    if args.json:
        _print_json(public_summary(s))
        return 0
    cfg = load_config(settings=s)
    print("Karmin_Ae / Holon — settings")
    print(f"  file            : {args.path or default_settings_path()}")
    print(f"  exists          : {(Path(args.path) if args.path else default_settings_path()).is_file()}")
    print(f"  profile         : {s.get('profile')}")
    print(f"  preset          : {s.get('preset')}")
    print(f"  default_project : {s.get('default_project') or '(meta/env)'}")
    print(f"  memory_path     : {s.get('memory_path')}")
    print(f"  overrides       : {s.get('overrides') or {}}")
    print("  effective Config:")
    print(f"    top_n_recall={cfg.top_n_recall}  prune_max={cfg.hard_prune_store_max}")
    print(f"    handoff facts/work={cfg.handoff_max_facts}/{cfg.handoff_max_work}  hybrid={cfg.handoff_hybrid_since}")
    print(f"    crystallize_sim={cfg.crystallize_sim_threshold}  prism={cfg.use_prism}")
    print(f"    llm={cfg.llm_backend} model={cfg.llm_model or '-'} url={cfg.llm_base_url or '-'}")
    return 0


def cmd_presets(_args: argparse.Namespace) -> int:
    for name, meta in PRESETS.items():
        print(f"{name:12}  [{meta['profile']}]  {meta['label']}")
        print(f"              {meta['description']}")
        if meta.get("overrides"):
            print(f"              overrides={meta['overrides']}")
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    s = load_settings(args.path)
    try:
        s = apply_preset(args.preset, s)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    path = save_settings(s, args.path)
    print(f"preset={args.preset} profile={s['profile']} → {path}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    s = load_settings(args.path)
    key = args.key.strip()
    val = args.value
    simple = {
        "profile": "profile",
        "preset": "preset",
        "default_project": "default_project",
        "memory_path": "memory_path",
        "notes": "notes",
    }
    if key not in simple:
        print(
            f"error: unknown key {key!r}. "
            f"Użyj: {', '.join(simple)} lub set-override",
            file=sys.stderr,
        )
        return 2
    if key == "profile":
        val = str(val).strip().lower()
        if val not in ("agent", "chat", "flat"):
            print("error: profile must be agent|chat|flat", file=sys.stderr)
            return 2
    if key == "preset":
        val = str(val).strip().lower()
        if val and val not in PRESETS:
            print(f"error: unknown preset {val}", file=sys.stderr)
            return 2
    s[simple[key]] = val
    s = normalize_settings(s)
    path = save_settings(s, args.path)
    print(f"set {key}={s[simple[key]]!r} → {path}")
    return 0


def cmd_set_override(args: argparse.Namespace) -> int:
    s = load_settings(args.path)
    key = args.key.strip()
    if key not in SAFE_OVERRIDE_KEYS:
        print(f"error: override not allowed: {key}", file=sys.stderr)
        print("allowed:", ", ".join(sorted(SAFE_OVERRIDE_KEYS)), file=sys.stderr)
        return 2
    overs = dict(s.get("overrides") or {})
    if args.clear or args.value in (None, "", "null", "NONE"):
        overs.pop(key, None)
        print(f"cleared override {key}")
    else:
        overs[key] = args.value
        print(f"override {key}={args.value!r}")
    s["overrides"] = overs
    path = save_settings(s, args.path)
    print(f"saved → {path}")
    return 0


def cmd_wizard(args: argparse.Namespace) -> int:
    print("=== Karmin_Ae wizard (pamięć SE) ===")
    print("Enter = domyślna wartość w [nawiasach]\n")
    s = load_settings(args.path)

    print("Presety:")
    for name, meta in PRESETS.items():
        print(f"  {name:12} — {meta['label']}")
    preset = input(f"preset [{s.get('preset') or 'se'}]: ").strip() or (s.get("preset") or "se")
    try:
        s = apply_preset(preset, s)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    proj = input(f"default_project [{s.get('default_project') or ''}]: ").strip()
    if proj:
        s["default_project"] = proj

    mem = input(f"memory_path [{s.get('memory_path')}]: ").strip()
    if mem:
        s["memory_path"] = mem

    llm = input(f"llm_backend [{s.get('overrides', {}).get('llm_backend', 'auto')}]: ").strip()
    if llm:
        s.setdefault("overrides", {})["llm_backend"] = llm
    model = input("llm_model []: ").strip()
    if model:
        s.setdefault("overrides", {})["llm_model"] = model
    url = input("llm_base_url []: ").strip()
    if url:
        s.setdefault("overrides", {})["llm_base_url"] = url

    path = save_settings(s, args.path)
    print(f"\nZapisano → {path}")
    print("Dalej: python agent_boot.py")
    print("       python holon_configure.py doctor")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    rep = doctor(root=ROOT, settings_path=args.path)
    if args.json:
        _print_json(rep)
        return 0 if rep.get("ok") else 1
    print(f"Karmin_Ae doctor  score={rep['score']}%  ok={rep['ok']}")
    print("\nChecks:")
    for c in rep["checks"]:
        mark = "OK " if c["ok"] else "!! "
        print(f"  {mark} {c['name']}: {c['detail']}")
    print("\nPositioning vs typical cloud agent-memory:")
    for row in rep["positioning"]:
        ka = row["karmin_ae"]
        typ = row["typical_saas_memory"]
        print(f"  • {row['capability']}")
        print(f"      Karmin_Ae={ka}  typical_saas={typ}")
    print("\nEffective:")
    for k, v in rep["config_effective"].items():
        print(f"  {k}: {v}")
    print("\nNext:")
    for n in rep["next"]:
        print(f"  {n}")
    return 0 if rep.get("ok") else 1


def cmd_export_env(args: argparse.Namespace) -> int:
    s = load_settings(args.path)
    lines = export_env_lines(s)
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_keys(_args: argparse.Namespace) -> int:
    print("Top-level keys: profile, preset, default_project, memory_path, notes")
    print("Overrides:")
    help_map = dict(config_field_help())
    for k in sorted(SAFE_OVERRIDE_KEYS):
        h = help_map.get(k, "")
        print(f"  {k:28} {h}")
    return 0


# ── GUI (tkinter, stdlib) ─────────────────────────────────────────────────


def cmd_gui(args: argparse.Namespace) -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        print("error: tkinter niedostępny w tej instalacji Pythona", file=sys.stderr)
        return 2

    settings_path = args.path or str(default_settings_path())
    s = load_settings(settings_path)

    root = tk.Tk()
    root.title("Karmin_Ae — konfigurator pamięci SE")
    root.minsize(520, 480)

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Karmin_Ae configurator", font=("", 12, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
    )
    ttk.Label(
        frm,
        text="Lokalna pamięć SE (nie SaaS) · profile · handoff · LLM",
        foreground="#444",
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

    vars_map: Dict[str, tk.Variable] = {}

    def row_label(r: int, text: str) -> None:
        ttk.Label(frm, text=text).grid(row=r, column=0, sticky="w", pady=3)

    r = 2
    row_label(r, "Preset")
    preset_var = tk.StringVar(value=s.get("preset") or "se")
    vars_map["preset"] = preset_var
    cb = ttk.Combobox(
        frm,
        textvariable=preset_var,
        values=list(PRESETS.keys()),
        state="readonly",
        width=28,
    )
    cb.grid(row=r, column=1, sticky="ew", pady=3)

    def on_preset(_e=None) -> None:
        name = preset_var.get()
        if name in PRESETS:
            profile_var.set(PRESETS[name]["profile"])
            desc_var.set(PRESETS[name]["description"])

    cb.bind("<<ComboboxSelected>>", on_preset)

    r = 3
    row_label(r, "Profile")
    profile_var = tk.StringVar(value=s.get("profile") or "agent")
    vars_map["profile"] = profile_var
    ttk.Combobox(
        frm,
        textvariable=profile_var,
        values=["agent", "chat", "flat"],
        state="readonly",
        width=28,
    ).grid(row=r, column=1, sticky="ew", pady=3)

    r = 4
    desc_var = tk.StringVar(
        value=PRESETS.get(s.get("preset") or "se", {}).get("description", "")
    )
    ttk.Label(frm, textvariable=desc_var, wraplength=360).grid(
        row=r, column=0, columnspan=3, sticky="w", pady=4
    )

    r = 5
    row_label(r, "default_project")
    proj_var = tk.StringVar(value=s.get("default_project") or "")
    ttk.Entry(frm, textvariable=proj_var).grid(row=r, column=1, sticky="ew", pady=3)

    r = 6
    row_label(r, "memory_path")
    mem_var = tk.StringVar(value=s.get("memory_path") or "holon_memory.json")
    ttk.Entry(frm, textvariable=mem_var).grid(row=r, column=1, sticky="ew", pady=3)

    r = 7
    ttk.Separator(frm).grid(row=r, column=0, columnspan=3, sticky="ew", pady=8)

    overs = dict(s.get("overrides") or {})
    r = 8
    row_label(r, "handoff_max_facts")
    facts_var = tk.StringVar(value=str(overs.get("handoff_max_facts", "")))
    ttk.Entry(frm, textvariable=facts_var, width=12).grid(row=r, column=1, sticky="w", pady=3)

    r = 9
    row_label(r, "handoff_max_work")
    work_var = tk.StringVar(value=str(overs.get("handoff_max_work", "")))
    ttk.Entry(frm, textvariable=work_var, width=12).grid(row=r, column=1, sticky="w", pady=3)

    r = 10
    row_label(r, "llm_backend")
    llm_var = tk.StringVar(value=str(overs.get("llm_backend", "auto")))
    ttk.Combobox(
        frm,
        textvariable=llm_var,
        values=["auto", "ollama", "local", "openai", "mock"],
        width=28,
    ).grid(row=r, column=1, sticky="ew", pady=3)

    r = 11
    row_label(r, "llm_model")
    model_var = tk.StringVar(value=str(overs.get("llm_model", "")))
    ttk.Entry(frm, textvariable=model_var).grid(row=r, column=1, sticky="ew", pady=3)

    r = 12
    row_label(r, "llm_base_url")
    url_var = tk.StringVar(value=str(overs.get("llm_base_url", "")))
    ttk.Entry(frm, textvariable=url_var).grid(row=r, column=1, sticky="ew", pady=3)

    status = tk.StringVar(value=f"plik: {settings_path}")
    r = 13
    ttk.Label(frm, textvariable=status, foreground="#333").grid(
        row=r, column=0, columnspan=3, sticky="w", pady=(10, 4)
    )

    def collect() -> Dict[str, Any]:
        data = normalize_settings(
            {
                "profile": profile_var.get(),
                "preset": preset_var.get(),
                "default_project": proj_var.get().strip(),
                "memory_path": mem_var.get().strip() or "holon_memory.json",
                "overrides": {},
            }
        )
        # start from preset cleanly then layer GUI overrides
        try:
            data = apply_preset(preset_var.get() or "se", data)
        except ValueError:
            pass
        data["profile"] = profile_var.get()
        data["default_project"] = proj_var.get().strip()
        data["memory_path"] = mem_var.get().strip() or "holon_memory.json"
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
        data = collect()
        path = save_settings(data, settings_path)
        status.set(f"zapisano → {path}")
        messagebox.showinfo("Karmin_Ae", f"Zapisano ustawienia:\n{path}")

    def do_doctor() -> None:
        # save first so doctor sees current file intent? optional — use in-memory
        data = collect()
        save_settings(data, settings_path)
        rep = doctor(root=ROOT, settings_path=settings_path)
        lines = [f"score={rep['score']}% ok={rep['ok']}", ""]
        for c in rep["checks"]:
            lines.append(f"{'OK' if c['ok'] else '!!'} {c['name']}: {c['detail']}")
        lines.append("")
        lines.append("Positioning:")
        for row in rep["positioning"][:5]:
            lines.append(f"  {row['capability']}: Ae={row['karmin_ae']} saas={row['typical_saas_memory']}")
        messagebox.showinfo("Doctor", "\n".join(lines))
        status.set(f"doctor score={rep['score']}%")

    def do_boot_hint() -> None:
        messagebox.showinfo(
            "Boot",
            "W terminalu:\n\n"
            "  cd Karmin_Ae\n"
            "  python agent_boot.py\n\n"
            "Settings są wczytywane automatycznie (profile, memory_path, overrides).",
        )

    btns = ttk.Frame(frm)
    btns.grid(row=14, column=0, columnspan=3, sticky="ew", pady=12)
    ttk.Button(btns, text="Zapisz", command=do_save).pack(side="left", padx=4)
    ttk.Button(btns, text="Doctor", command=do_doctor).pack(side="left", padx=4)
    ttk.Button(btns, text="Jak boot?", command=do_boot_hint).pack(side="left", padx=4)
    ttk.Button(btns, text="Zamknij", command=root.destroy).pack(side="right", padx=4)

    root.mainloop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="holon_configure",
        description="Konfigurator Karmin_Ae / Holon (CLI + GUI)",
    )
    p.add_argument(
        "--path",
        default="",
        help="ścieżka settings (domyślnie holon_settings.json w root repo)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("show", help="pokaż ustawienia + effective Config")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("presets", help="lista presetów produktowych")
    sp.set_defaults(func=cmd_presets)

    sp = sub.add_parser("use", help="zastosuj preset i zapisz")
    sp.add_argument("preset", help="se | se-compact | se-long | chat | lab-flat")
    sp.set_defaults(func=cmd_use)

    sp = sub.add_parser("set", help="ustaw pole top-level")
    sp.add_argument("key")
    sp.add_argument("value")
    sp.set_defaults(func=cmd_set)

    sp = sub.add_parser("set-override", help="ustaw/clear override Config")
    sp.add_argument("key")
    sp.add_argument("value", nargs="?", default="")
    sp.add_argument("--clear", action="store_true")
    sp.set_defaults(func=cmd_set_override)

    sp = sub.add_parser("wizard", help="interaktywny setup w terminalu")
    sp.set_defaults(func=cmd_wizard)

    sp = sub.add_parser("doctor", help="diagnostyka + positioning vs SaaS memory")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("export-env", help="wypisz HOLON_* do shella")
    sp.add_argument("--out", default="", help="zapisz do pliku")
    sp.set_defaults(func=cmd_export_env)

    sp = sub.add_parser("keys", help="lista dozwolonych kluczy")
    sp.set_defaults(func=cmd_keys)

    sp = sub.add_parser("gui", help="okienkowy konfigurator (tkinter)")
    sp.set_defaults(func=cmd_gui)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    # normalize path
    args.path = args.path or None
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
