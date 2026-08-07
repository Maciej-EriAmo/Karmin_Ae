# holon_config.py — parametry Holona + jawne profile (agent vs chat).
"""
Domyślny ``Config()`` = profil **chat** (produkt EriAmo / sesja rozmowy).

Pamięć SE / Grok CLI: zawsze ``Config.agent()`` (dłuższa trwałość, większy store).

Ablacja / lab: ``Config.flat()`` — bez PrismRouter (prostszy tor Φ).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Optional


@dataclass
class Config:
    # ── profil ────────────────────────────────────────────────────────────
    # "chat" | "agent" | "flat" | custom
    profile: str = "chat"

    k: int = 4
    n: int = 7
    threshold: float = 0.20
    lr: float = 0.01
    alpha: float = 0.05
    top_n_recall: int = 5
    dim: int = 256
    time_dim: int = 8
    # Hybryda recall: KuRz-cosine bywa ~0 — lexical token boost ratuje SE/CLI.
    hybrid_lexical_weight: float = 0.18
    hybrid_min_token_len: int = 3
    # B2: inverted lexical index — pruning kandydatów gdy store duży
    lexical_index_min_store: int = 500
    lexical_index_max_candidates: int = 256
    lexical_index_force: bool = False  # True w testach / lab

    @property
    def total_dim(self) -> int:
        return self.dim + self.time_dim

    phi_half_life_hours: list = field(default_factory=lambda: [
        [24.0, 18.0, 12.0, 8.0],
        [168.0, 120.0, 96.0, 72.0],
        [720.0, 540.0, 360.0, 240.0],
    ])

    # ── domyślne = CHAT (produkt) — krótsze epizody, ciaśniejszy store ────
    store_decay_hours: float = 336.0  # ~14 dni epizody
    # ranking_age cap dla durable; created_at nigdy nie jest kasowany
    durable_age_cap: int = 120
    keep_facts_forever: bool = True
    keep_work_forever: bool = True
    work_decay_hours: float = 2160.0  # ~90 dni gdy keep_work_forever=False
    healthy_temporal_mode: bool = True
    aii_baseline_half_life_h: float = 72.0
    digest_timeline_items: int = 6
    phi_min_norm: float = 0.1
    phi_ortho_beta: float = 0.05
    vacuum_age_tau: float = 50.0
    recall_age_penalty: float = 0.02
    aii_adapt_range: float = 0.15
    vacuum_warmup_turns: int = 8
    phi_stability_decay: float = 0.95
    phi_stability_max: float = 5.0
    coherence_threshold: float = 0.4
    phi_levels: int = 3
    phase_shifts: list = field(default_factory=lambda: [0.0, 0.33, 0.66])
    rumination_interval: int = 12
    rumination_threshold: float = 0.35
    rumination_shifts: list = field(default_factory=lambda: [0.0, 0.25, 0.5, 0.75])
    surprise_adapt_rate: float = 0.005
    surprise_trigger: float = 0.4
    lr_min: float = 0.001
    lr_max: float = 0.025
    precision_mode: str = "error"
    soft_vacuum_interval: int = 4
    soft_decay_factor: float = 0.96
    hard_prune_interval: int = 20
    hard_prune_store_max: int = 120
    # ── krystalizacja (B9) — offline utrwalanie stałych ścieżek ──────────
    # sim >= threshold → merge near-dup; cluster_size >= min → promote note→fact
    crystallize_sim_threshold: float = 0.90
    crystallize_promote_cluster_min: int = 2
    crystallize_reinforce_top: int = 24
    crystallize_relevance_floor: float = 1.4
    crystallize_max_active_work: int = 1
    # ── B10 handoff / set-work (projekcja SE, mniej szumu) ────────────────
    set_work_max_active: int = 1
    handoff_max_work: int = 2
    handoff_max_facts: int = 6
    handoff_max_chronicle: int = 4
    handoff_hybrid_since: bool = True  # --since: dołóż last work poza oknem
    remember_merge_sim: float = 0.88  # semantic merge w remember
    focus_boost: float = 1.25
    phase_shifts_learnable: bool = True
    conversation_history_size: int = 12
    topic_repeat_threshold: int = 3
    use_prism: bool = True
    prism_cfg: object = None
    rumination_generate_insight: bool = True
    insight_prompt_template: str = (
        "Jesteś EriAmo. Przeanalizuj swój błąd predykcji w architekturze Holon.\n"
        "Wykryto niespójność czasowo-przestrzenną: {max_inc:.3f}\n"
        "Wygeneruj jeden zwięzły wniosek (insight), czego się z tego nauczyłeś "
        "i jak to wpływa na Twój model otoczenia:\n"
    )

    # ── LLM / lokalny model (wszczep) ─────────────────────────────────────
    # backend: auto | ollama | local | openai | groq | deepseek | mock
    # local = fabryka z register_local_model_factory() LUB OpenAI-compatible URL
    llm_backend: str = "auto"
    llm_base_url: str = ""  # np. http://127.0.0.1:8080/v1 (llama.cpp server)
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_s: float = 120.0

    # ── fabryki profili ───────────────────────────────────────────────────

    @classmethod
    def chat(cls, **overrides) -> "Config":
        """Profil produktowy (EriAmo / main.py) — domyślne wartości dataclass."""
        c = cls(profile="chat")
        return replace(c, **overrides) if overrides else c

    @classmethod
    def agent(cls, **overrides) -> "Config":
        """Profil pamięci SE / Grok CLI — dłuższa trwałość, większy store."""
        c = cls(
            profile="agent",
            store_decay_hours=2160.0,  # ~90 dni epizody
            durable_age_cap=720,
            work_decay_hours=8760.0,  # ~1 rok gdy keep_work=False
            hard_prune_store_max=400,
            digest_timeline_items=8,
            hybrid_lexical_weight=0.22,
            top_n_recall=8,
            lexical_index_min_store=500,
            lexical_index_max_candidates=256,
            # SE: trochę niższy próg merge (KuRz bywa sztywny), więcej ścieżek Φ
            crystallize_sim_threshold=0.88,
            crystallize_reinforce_top=32,
            crystallize_max_active_work=1,
            set_work_max_active=1,
            handoff_max_work=2,
            handoff_max_facts=6,
            handoff_max_chronicle=4,
            handoff_hybrid_since=True,
            remember_merge_sim=0.88,
        )
        return replace(c, **overrides) if overrides else c

    @classmethod
    def flat(cls, base: Optional[str] = "agent", **overrides) -> "Config":
        """Ablacja: bez PrismRouter — prostszy tor (lab / porównania)."""
        c = cls.agent() if base == "agent" else cls.chat()
        c = replace(c, profile="flat", use_prism=False)
        return replace(c, **overrides) if overrides else c

    @classmethod
    def from_env(cls, default_profile: str = "chat") -> "Config":
        """HOLON_PROFILE=agent|chat|flat + opcjonalne LLM_* z env.

        Preferuj ``from_settings()`` gdy istnieje ``holon_settings.json``
        (CLI/GUI: ``python holon_configure.py``).
        """
        prof = (os.environ.get("HOLON_PROFILE") or default_profile).strip().lower()
        if prof == "agent":
            c = cls.agent()
        elif prof == "flat":
            c = cls.flat()
        else:
            c = cls.chat()
        # LLM override z env (nie wymagają restartu logiki poza startem sesji)
        be = os.environ.get("HOLON_LLM_BACKEND") or os.environ.get("HOLON_LLM")
        if be:
            c.llm_backend = be.strip().lower()
        if os.environ.get("HOLON_LLM_BASE_URL"):
            c.llm_base_url = os.environ["HOLON_LLM_BASE_URL"].strip()
        if os.environ.get("HOLON_LLM_MODEL") or os.environ.get("OLLAMA_MODEL"):
            c.llm_model = (
                os.environ.get("HOLON_LLM_MODEL")
                or os.environ.get("OLLAMA_MODEL")
                or ""
            ).strip()
        if os.environ.get("HOLON_LLM_API_KEY"):
            c.llm_api_key = os.environ["HOLON_LLM_API_KEY"].strip()
        return c

    @classmethod
    def from_settings(
        cls,
        default_profile: str = "agent",
        *,
        profile: Optional[str] = None,
        settings_path: Optional[str] = None,
    ) -> "Config":
        """Config z ``holon_settings.json`` (+ env LLM). Lazy import settings."""
        from holon_settings import load_config

        return load_config(
            profile=profile,
            default_profile=default_profile,
            settings_path=settings_path,
            apply_env=True,
        )
