# -*- coding: utf-8 -*-
"""
holon_settings.py — trwała konfiguracja Karmin_Ae / Holon (SE + chat).

Plik: ``holon_settings.json`` (gitignore; lokalne preferencje, może zawierać LLM key).
Łańcuch: fabryka profilu → settings.overrides → env (env wygrywa sekrety/CI).

Nie mylić z ``holon_memory.json`` (stan umysłu).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from holon_config import Config

SETTINGS_VERSION = 1
DEFAULT_SETTINGS_NAME = "holon_settings.json"
EXAMPLE_SETTINGS_NAME = "holon_settings.example.json"

# Stan (pamięć, settings, linki) — poza drzewem kodu. Inaczej zombie w repo.
STATE_BASENAMES = (
    "holon_memory.json",
    "holon_memory.meta.json",
    "holon_memory_links.json",
    "holon_memory_kurz.json",
    "holon_memory.bak.json",
    "holon_settings.json",
)
STATE_DIRNAMES = ("notes",)


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def data_home() -> Path:
    """Katalog danych SE — nie katalog projektu.

    HOLON_DATA_HOME > %LOCALAPPDATA%/Karmin_Ae > ~/.local/share/karmin_ae
    """
    env = (os.environ.get("HOLON_DATA_HOME") or "").strip()
    if env:
        return Path(env).expanduser()
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return Path(local) / "Karmin_Ae"
    return Path.home() / ".local" / "share" / "karmin_ae"

# Pola Config dozwolone w overrides (bez obiektów / list złożonych Φ).
SAFE_OVERRIDE_KEYS = frozenset(
    {
        "top_n_recall",
        "hybrid_lexical_weight",
        "hybrid_min_token_len",
        "lexical_index_min_store",
        "lexical_index_max_candidates",
        "lexical_index_force",
        "store_decay_hours",
        "durable_age_cap",
        "keep_facts_forever",
        "keep_work_forever",
        "work_decay_hours",
        "hard_prune_store_max",
        "digest_timeline_items",
        "crystallize_sim_threshold",
        "crystallize_promote_cluster_min",
        "crystallize_reinforce_top",
        "crystallize_max_active_work",
        "set_work_max_active",
        "handoff_max_work",
        "handoff_max_facts",
        "handoff_max_chronicle",
        "handoff_hybrid_since",
        "remember_merge_sim",
        "use_prism",
        "llm_backend",
        "llm_base_url",
        "llm_model",
        "llm_api_key",
        "llm_timeout_s",
        "helper_llm_backend",
        "helper_llm_model",
        "helper_llm_api_key",
        "helper_llm_timeout_s",
        "helper_enabled",
        "conversation_history_size",
    }
)

# Presety produktowe — pozycjonowanie vs „pamięć agenta z chmury”.
# label/description = PL; label_en/description_en = EN (UI switch).
PRESETS: Dict[str, Dict[str, Any]] = {
    "se": {
        "label": "SE / Grok (ciągłość, kompakt)",
        "label_en": "SE / Grok (continuity, compact)",
        "profile": "agent",
        "description": "Domyślny tor: 1 work, krótki handoff, hybrid since, crystallize.",
        "description_en": "Default path: 1 work, short handoff, hybrid since, crystallize.",
        "overrides": {
            "handoff_max_work": 1,
            "handoff_max_facts": 4,
            "handoff_max_chronicle": 2,
            "set_work_max_active": 1,
        },
    },
    "se-compact": {
        "label": "SE ultra-kompakt",
        "label_en": "SE ultra-compact",
        "profile": "agent",
        "description": "Minimalny bootstrap — 3 facts, 1 work, bez chronicle w compact boot.",
        "description_en": "Minimal bootstrap — 3 facts, 1 work, no chronicle on compact boot.",
        "overrides": {
            "handoff_max_work": 1,
            "handoff_max_facts": 3,
            "handoff_max_chronicle": 1,
            "set_work_max_active": 1,
            "top_n_recall": 6,
            "digest_timeline_items": 4,
        },
    },
    "se-long": {
        "label": "SE long-horizon",
        "label_en": "SE long-horizon",
        "profile": "agent",
        "description": "Większy store i miększe prune — długie projekty multi-sesja.",
        "description_en": "Larger store and softer prune — long multi-session projects.",
        "overrides": {
            "hard_prune_store_max": 800,
            "store_decay_hours": 4320.0,
            "durable_age_cap": 1440,
            "lexical_index_min_store": 300,
        },
    },
    "chat": {
        "label": "Chat EriAmo",
        "label_en": "Chat EriAmo",
        "profile": "chat",
        "description": "Produkt rozmowy — ciaśniejszy store, krótsze epizody.",
        "description_en": "Conversation product — tighter store, shorter episodes.",
        "overrides": {},
    },
    "lab-flat": {
        "label": "Lab flat (bez Prism)",
        "label_en": "Lab flat (no Prism)",
        "profile": "flat",
        "description": "Ablacja Φ/Prism — porównania i testy.",
        "description_en": "Φ/Prism ablation — comparisons and tests.",
        "overrides": {"use_prism": False},
    },
}


def normalize_lang(raw: Optional[str]) -> str:
    """Zwraca ``pl`` lub ``en``."""
    v = (raw or "").strip().lower()
    if v in ("en", "eng", "english", "us", "gb"):
        return "en"
    return "pl"


def resolve_ui_lang(
    cli_lang: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
    settings_path: Optional[str | Path] = None,
) -> str:
    """Kolejność: CLI → env ``HOLON_UI_LANG`` → settings ``ui_lang`` → pl."""
    if cli_lang:
        return normalize_lang(cli_lang)
    env = (os.environ.get("HOLON_UI_LANG") or os.environ.get("HOLON_LANG") or "").strip()
    if env:
        return normalize_lang(env)
    s = settings if settings is not None else load_settings(settings_path)
    return normalize_lang(str(s.get("ui_lang") or "pl"))


def preset_text(name: str, lang: str = "pl") -> Tuple[str, str]:
    """(label, description) w wybranym języku."""
    meta = PRESETS.get(name) or {}
    en = normalize_lang(lang) == "en"
    label = str(
        (meta.get("label_en") if en else meta.get("label"))
        or meta.get("label")
        or name
    )
    desc = str(
        (meta.get("description_en") if en else meta.get("description"))
        or meta.get("description")
        or ""
    )
    return label, desc


def default_settings_path(root: Optional[Path] = None) -> Path:
    """Settings: najpierw data_home, potem (legacy) katalog kodu."""
    home = data_home() / DEFAULT_SETTINGS_NAME
    if home.is_file():
        return home
    base = Path(root) if root else repo_root()
    legacy = base / DEFAULT_SETTINGS_NAME
    if legacy.is_file():
        return legacy
    return home


def relocate_repo_state(*, root: Optional[Path] = None) -> Dict[str, Any]:
    """Przenieś pliki stanu z repo do data_home. Idempotentne.

    Dest wygrywa. Po udanym kopiowaniu kasujemy kopię w projekcie
    (to był bałagan / zombie).
    """
    import shutil

    repo = Path(root) if root else repo_root()
    home = data_home()
    report: Dict[str, Any] = {
        "home": str(home),
        "repo": str(repo),
        "moved": [],
        "kept_dest": [],
        "skipped": [],
    }
    try:
        if home.resolve() == repo.resolve():
            report["skipped"].append("home==repo")
            return report
    except OSError:
        pass
    home.mkdir(parents=True, exist_ok=True)
    for name in STATE_BASENAMES:
        src, dst = repo / name, home / name
        if not src.is_file():
            continue
        if not dst.is_file():
            shutil.copy2(src, dst)
            report["moved"].append(name)
        else:
            report["kept_dest"].append(name)
        try:
            src.unlink()
        except OSError:
            report["skipped"].append(f"unlink {name}")
    for name in STATE_DIRNAMES:
        src, dst = repo / name, home / name
        if not src.is_dir():
            continue
        if not dst.exists():
            import shutil as _sh

            _sh.copytree(src, dst)
            report["moved"].append(name + "/")
            _sh.rmtree(src, ignore_errors=True)
        else:
            report["kept_dest"].append(name + "/")
    marker = repo / ".holon_data_home"
    try:
        marker.write_text(str(home) + "\n", encoding="utf-8")
    except OSError:
        pass
    readme = home / "README.txt"
    if not readme.is_file():
        readme.write_text(
            "Karmin_Ae data home — stan umysłu i ustawienia.\n"
            "Kod jest w katalogu projektu; tutaj tylko dane.\n",
            encoding="utf-8",
        )
    return report


def default_blank() -> Dict[str, Any]:
    return {
        "version": SETTINGS_VERSION,
        "profile": "agent",
        "preset": "se",
        "default_project": "",
        "memory_path": "holon_memory.json",
        "ui_lang": "pl",
        "overrides": {},
        "updated_at": 0.0,
        "notes": "",
    }


def _coerce_value(key: str, raw: Any) -> Any:
    """Proste rzutowanie typów z CLI/GUI (stringi → bool/int/float)."""
    if raw is None:
        return None
    # bool z stringa
    if isinstance(raw, str):
        low = raw.strip().lower()
        if low in ("true", "yes", "1", "on"):
            if key in SAFE_OVERRIDE_KEYS:
                # heurystyka: bool fields
                if key in (
                    "lexical_index_force",
                    "keep_facts_forever",
                    "keep_work_forever",
                    "handoff_hybrid_since",
                    "use_prism",
                ):
                    return True
        if low in ("false", "no", "0", "off"):
            if key in (
                "lexical_index_force",
                "keep_facts_forever",
                "keep_work_forever",
                "handoff_hybrid_since",
                "use_prism",
            ):
                return False
        # int / float
        try:
            if "." in raw or "e" in low:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw
    return raw


def _looks_like_http_url(value: str) -> bool:
    u = (value or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def sanitize_overrides(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        key = str(k).strip()
        if key not in SAFE_OVERRIDE_KEYS:
            continue
        if v is None or v == "":
            continue
        coerced = _coerce_value(key, v)
        # llm_base_url = endpoint HTTP, NIE ścieżka do folderu modeli Ollamy
        if key == "llm_base_url":
            s = str(coerced).strip()
            if not _looks_like_http_url(s):
                continue  # drop invalid path-like values
            coerced = s.rstrip("/")
        out[key] = coerced
    return out


def normalize_settings(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = default_blank()
    if not data:
        return base
    base["version"] = int(data.get("version") or SETTINGS_VERSION)
    prof = str(data.get("profile") or "agent").strip().lower()
    if prof not in ("agent", "chat", "flat"):
        prof = "agent"
    base["profile"] = prof
    preset = str(data.get("preset") or "").strip().lower()
    if preset and preset not in PRESETS:
        preset = ""
    base["preset"] = preset or ("se" if prof == "agent" else prof)
    base["default_project"] = str(data.get("default_project") or "").strip()
    mp = str(data.get("memory_path") or "holon_memory.json").strip()
    base["memory_path"] = mp or "holon_memory.json"
    base["ui_lang"] = normalize_lang(str(data.get("ui_lang") or "pl"))
    base["overrides"] = sanitize_overrides(data.get("overrides") or {})
    base["updated_at"] = float(data.get("updated_at") or 0.0)
    base["notes"] = str(data.get("notes") or "")
    return base


def load_settings(path: Optional[str | Path] = None) -> Dict[str, Any]:
    p = Path(path) if path else default_settings_path()
    if not p.is_file():
        return default_blank()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_blank()
    return normalize_settings(raw if isinstance(raw, dict) else None)


def save_settings(
    data: Dict[str, Any],
    path: Optional[str | Path] = None,
    *,
    create_parent: bool = True,
) -> Path:
    p = Path(path) if path else default_settings_path()
    if create_parent:
        p.parent.mkdir(parents=True, exist_ok=True)
    norm = normalize_settings(data)
    norm["updated_at"] = time.time()
    tmp = p.with_suffix(p.suffix + ".tmp")
    text = json.dumps(norm, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)
    return p


def preset_controlled_keys() -> frozenset:
    """Klucze ustawiane przez którykolwiek produktowy preset (handoff/store/…).

    Przy ``apply_preset`` te klucze są podmieniane; reszta user overrides
    (np. ``llm_backend`` / ``llm_model`` / ``llm_base_url``) zostaje.
    """
    keys: set = set()
    for p in PRESETS.values():
        keys.update((p.get("overrides") or {}).keys())
    return frozenset(keys)


def apply_preset(name: str, current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    key = (name or "").strip().lower()
    if key not in PRESETS:
        raise ValueError(f"Nieznany preset: {name!r}. Dostępne: {', '.join(PRESETS)}")
    cur = normalize_settings(current)
    preset = PRESETS[key]
    cur["preset"] = key
    cur["profile"] = preset["profile"]
    # Zachowaj user overrides spoza presetu (LLM itd.); podmień tylko controlled keys
    controlled = preset_controlled_keys()
    kept = {
        k: v
        for k, v in (cur.get("overrides") or {}).items()
        if k not in controlled
    }
    kept.update(sanitize_overrides(preset.get("overrides") or {}))
    cur["overrides"] = sanitize_overrides(kept)
    return cur


def _profile_config(profile: str) -> Config:
    p = (profile or "agent").strip().lower()
    if p == "chat":
        return Config.chat()
    if p == "flat":
        return Config.flat(base="agent")
    return Config.agent()


def apply_env_llm(cfg: Config) -> Config:
    """Env nadpisuje LLM (CI / sekrety)."""
    be = os.environ.get("HOLON_LLM_BACKEND") or os.environ.get("HOLON_LLM")
    if be:
        cfg.llm_backend = be.strip().lower()
    if os.environ.get("HOLON_LLM_BASE_URL"):
        cfg.llm_base_url = os.environ["HOLON_LLM_BASE_URL"].strip()
    if (
        os.environ.get("HOLON_LLM_MODEL")
        or os.environ.get("OLLAMA_MODEL")
        or os.environ.get("GEMINI_MODEL")
    ):
        cfg.llm_model = (
            os.environ.get("HOLON_LLM_MODEL")
            or os.environ.get("OLLAMA_MODEL")
            or os.environ.get("GEMINI_MODEL")
            or ""
        ).strip()
    # klucz: HOLON_* wygrywa; potem Gemini / Google AI Studio
    if os.environ.get("HOLON_LLM_API_KEY"):
        cfg.llm_api_key = os.environ["HOLON_LLM_API_KEY"].strip()
    elif not (cfg.llm_api_key or "").strip():
        for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY"):
            if os.environ.get(k):
                cfg.llm_api_key = os.environ[k].strip()
                break
    if os.environ.get("HOLON_LLM_TIMEOUT"):
        try:
            cfg.llm_timeout_s = float(os.environ["HOLON_LLM_TIMEOUT"])
        except ValueError:
            pass
    # Pomocnik SE (Gemini domyślnie)
    if os.environ.get("HOLON_HELPER_LLM_BACKEND"):
        cfg.helper_llm_backend = os.environ["HOLON_HELPER_LLM_BACKEND"].strip().lower()
    if os.environ.get("HOLON_HELPER_LLM_MODEL") or os.environ.get("GEMINI_MODEL"):
        cfg.helper_llm_model = (
            os.environ.get("HOLON_HELPER_LLM_MODEL")
            or os.environ.get("GEMINI_MODEL")
            or cfg.helper_llm_model
            or ""
        ).strip()
    if os.environ.get("HOLON_HELPER_LLM_API_KEY"):
        cfg.helper_llm_api_key = os.environ["HOLON_HELPER_LLM_API_KEY"].strip()
    elif not (cfg.helper_llm_api_key or "").strip():
        for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY"):
            if os.environ.get(k):
                cfg.helper_llm_api_key = os.environ[k].strip()
                break
    if os.environ.get("HOLON_HELPER_ENABLED"):
        raw = os.environ["HOLON_HELPER_ENABLED"].strip().lower()
        cfg.helper_enabled = raw not in ("0", "false", "no", "off")
    return cfg


def load_config(
    *,
    profile: Optional[str] = None,
    default_profile: str = "agent",
    settings_path: Optional[str | Path] = None,
    settings: Optional[Dict[str, Any]] = None,
    apply_env: bool = True,
) -> Config:
    """Zbuduj Config: settings (+ opcjonalny profile CLI) → overrides → env."""
    s = normalize_settings(settings if settings is not None else load_settings(settings_path))
    # CLI profile argument wins over file if explicitly passed and non-empty
    prof = (
        (profile or "").strip().lower()
        or str(s.get("profile") or "").strip().lower()
        or (default_profile or "agent").strip().lower()
    )
    # HOLON_PROFILE env can force base profile when apply_env
    if apply_env:
        env_prof = (os.environ.get("HOLON_PROFILE") or "").strip().lower()
        if env_prof in ("agent", "chat", "flat"):
            prof = env_prof
    cfg = _profile_config(prof)
    overs = sanitize_overrides(s.get("overrides") or {})
    for k, v in overs.items():
        if hasattr(cfg, k):
            try:
                setattr(cfg, k, v)
            except Exception:
                pass
    # ensure profile label matches
    cfg.profile = prof if prof != "flat" else "flat"
    if apply_env:
        cfg = apply_env_llm(cfg)
    return cfg


def resolve_memory_path(
    cli_path: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
    settings_path: Optional[str | Path] = None,
    root: Optional[Path] = None,
) -> str:
    if cli_path and str(cli_path).strip():
        return str(cli_path).strip()
    s = settings if settings is not None else load_settings(settings_path)
    mp = str(s.get("memory_path") or "holon_memory.json").strip()
    p = Path(mp)
    if p.is_absolute():
        return str(p)
    home_p = data_home() / p.name
    base = Path(root) if root is not None else repo_root()
    legacy = base / p
    if home_p.is_file():
        return str(home_p)
    if legacy.is_file():
        return str(legacy)
    return str(home_p)


def resolve_default_project(
    cli_project: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
    settings_path: Optional[str | Path] = None,
) -> Tuple[str, str]:
    """Zwraca (project, source). CLI > env > settings > \"\"."""
    if cli_project and str(cli_project).strip():
        return str(cli_project).strip(), "cli"
    env = (os.environ.get("HOLON_DEFAULT_PROJECT") or "").strip()
    if env:
        return env, "env"
    s = settings if settings is not None else load_settings(settings_path)
    sp = str(s.get("default_project") or "").strip()
    if sp:
        return sp, "settings"
    return "", ""


def export_env_lines(settings: Optional[Dict[str, Any]] = None) -> List[str]:
    s = normalize_settings(settings if settings is not None else load_settings())
    cfg = load_config(settings=s, apply_env=False)
    lines = [
        f"HOLON_PROFILE={s.get('profile') or 'agent'}",
    ]
    if s.get("default_project"):
        lines.append(f"HOLON_DEFAULT_PROJECT={s['default_project']}")
    if cfg.llm_backend:
        lines.append(f"HOLON_LLM_BACKEND={cfg.llm_backend}")
    if cfg.llm_base_url:
        lines.append(f"HOLON_LLM_BASE_URL={cfg.llm_base_url}")
    if cfg.llm_model:
        lines.append(f"HOLON_LLM_MODEL={cfg.llm_model}")
    if cfg.llm_api_key:
        lines.append(f"HOLON_LLM_API_KEY={cfg.llm_api_key}")
    return lines


def doctor(
    *,
    root: Optional[Path] = None,
    settings_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Diagnostyka setupu — checklista „lokalna pamięć SE gotowa”."""
    root = Path(root) if root else Path(__file__).resolve().parent
    sp = Path(settings_path) if settings_path else root / DEFAULT_SETTINGS_NAME
    s = load_settings(sp)
    cfg = load_config(settings=s, apply_env=True)
    mem = resolve_memory_path(settings=s, root=root)
    mem_p = Path(mem)

    checks: List[Dict[str, Any]] = []

    def add(ok: bool, name: str, detail: str = "") -> None:
        checks.append({"ok": bool(ok), "name": name, "detail": detail})

    add(True, "brand", "Karmin_Ae (Agent Edition) — lokalna pamięć SE, nie SaaS")
    add(sp.is_file(), "settings_file", str(sp) if sp.is_file() else f"brak {sp.name} — użyj: python holon_configure.py wizard")
    add(mem_p.is_file(), "memory_file", str(mem_p) if mem_p.is_file() else f"brak {mem_p} — pojawi się po seed/remember")
    add((root / "agent_boot.py").is_file(), "agent_boot", "python agent_boot.py")
    add((root / "AGENTS.md").is_file(), "agents_md", "kontrakt startowy agenta")
    add((root / "holon_agent_memory.py").is_file(), "agent_memory", "handoff / crystallize / eval")
    add(cfg.profile in ("agent", "chat", "flat"), "profile", f"profile={cfg.profile}")
    add(bool(cfg.keep_facts_forever), "durable_facts", "fact nie wygasa z decay godzin")
    add(bool(cfg.handoff_hybrid_since), "hybrid_handoff", "B10 hybrid --since")
    add(cfg.hard_prune_store_max >= 100, "store_capacity", f"hard_prune_store_max={cfg.hard_prune_store_max}")

    # competitive positioning matrix (informational)
    positioning = [
        {"capability": "Local-first (no cloud lock-in)", "karmin_ae": True, "typical_saas_memory": False},
        {"capability": "Durable fact/work flags", "karmin_ae": True, "typical_saas_memory": "partial"},
        {"capability": "Handoff JSON for agent boot", "karmin_ae": True, "typical_saas_memory": False},
        {"capability": "Hybrid delta (--since) + anchors", "karmin_ae": True, "typical_saas_memory": False},
        {"capability": "Crystallize offline merge paths", "karmin_ae": True, "typical_saas_memory": False},
        {"capability": "Mneme meta-language + graph", "karmin_ae": True, "typical_saas_memory": False},
        {"capability": "Golden eval CI", "karmin_ae": True, "typical_saas_memory": "rare"},
        {"capability": "One-command agent_boot", "karmin_ae": True, "typical_saas_memory": False},
    ]

    n_ok = sum(1 for c in checks if c["ok"])
    score = round(100.0 * n_ok / max(1, len(checks)), 1)

    return {
        "ok": n_ok == len(checks) or (n_ok >= len(checks) - 1 and not mem_p.is_file()),
        "score": score,
        "checks": checks,
        "settings": {
            "path": str(sp),
            "exists": sp.is_file(),
            "profile": s.get("profile"),
            "preset": s.get("preset"),
            "default_project": s.get("default_project"),
            "memory_path": s.get("memory_path"),
            "overrides": s.get("overrides") or {},
        },
        "config_effective": {
            "profile": cfg.profile,
            "top_n_recall": cfg.top_n_recall,
            "hard_prune_store_max": cfg.hard_prune_store_max,
            "handoff_max_facts": cfg.handoff_max_facts,
            "handoff_max_work": cfg.handoff_max_work,
            "handoff_hybrid_since": cfg.handoff_hybrid_since,
            "crystallize_sim_threshold": cfg.crystallize_sim_threshold,
            "use_prism": cfg.use_prism,
            "llm_backend": cfg.llm_backend,
            "llm_model": cfg.llm_model or "",
            "llm_base_url": cfg.llm_base_url or "",
        },
        "positioning": positioning,
        "next": [
            "python holon_configure.py wizard",
            "python holon_configure.py gui",
            "python agent_boot.py",
            "python holon_agent_memory.py eval",
        ],
    }


def public_summary(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    s = normalize_settings(settings if settings is not None else load_settings())
    cfg = load_config(settings=s, apply_env=True)
    return {
        "profile": s.get("profile"),
        "preset": s.get("preset"),
        "default_project": s.get("default_project"),
        "memory_path": s.get("memory_path"),
        "overrides": s.get("overrides") or {},
        "effective": {
            "profile": cfg.profile,
            "top_n_recall": cfg.top_n_recall,
            "hard_prune_store_max": cfg.hard_prune_store_max,
            "handoff_max_facts": cfg.handoff_max_facts,
            "handoff_max_work": cfg.handoff_max_work,
            "use_prism": cfg.use_prism,
            "llm_backend": cfg.llm_backend,
            "llm_model": cfg.llm_model,
        },
    }


def config_field_help() -> List[Tuple[str, str]]:
    return [
        ("top_n_recall", "ile hitów recall wraca do SE"),
        ("hybrid_lexical_weight", "waga tokenów lexical w hybrid recall"),
        ("hard_prune_store_max", "twardy limit wielkości store"),
        ("store_decay_hours", "czas życia epizodów (nie fact)"),
        ("handoff_max_facts", "ile faktów w handoff JSON"),
        ("handoff_max_work", "ile work w handoff"),
        ("handoff_hybrid_since", "dołóż last work spoza okna --since"),
        ("crystallize_sim_threshold", "próg merge near-dup w crystallize"),
        ("set_work_max_active", "max aktywnych work (domyślnie 1)"),
        ("remember_merge_sim", "próg semantic merge w remember"),
        ("use_prism", "PrismRouter on/off"),
        ("llm_backend", "auto|ollama|gemini|local|openai|groq|deepseek|mock"),
        ("llm_base_url", "OpenAI-compatible URL"),
        ("llm_model", "nazwa modelu (chat)"),
        ("helper_llm_backend", "pomocnik SE: gemini|ollama|auto|…"),
        ("helper_llm_model", "model pomocnika (np. gemini-2.0-flash)"),
        ("helper_enabled", "True|False — slot holon_helper / assist"),
        ("llm_api_key", "klucz API (lokalny plik — nie commituj)"),
    ]
