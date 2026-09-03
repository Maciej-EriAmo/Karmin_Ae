# -*- coding: utf-8 -*-
"""holon/holomem.py — HoloMem: silnik pamięci kognitywnej"""

import re
import math
import time
import uuid
import datetime
import numpy as np
from typing import Optional, Tuple

from holon_config import Config
from holon_item import Item
from holon_holography import HolographicInterference, PrismConfig, PrismRouter
from holon_embedder import Embedder
from holon_aii import AIIState, TimeDecay
from holon_memory import PersistentMemory


class HoloMem:
    FACT_PATTERNS: Tuple[str, ...] = (
        "mój ulubiony", "jestem", "mam na imię", "nazywam się",
        "lubię", "pracuję nad",
        # Agent CLI / partner SE — jawne kotwice faktów
        "zapamiętaj:", "fakt:", "ustalenie:", "preferencja:",
        "użytkownik:", "partner:", "grok:", "agent:",
        "zawsze ", "nigdy nie ", "konwencja:",
    )
    FOCUS_PATTERNS: Tuple[str, ...] = (
        "holon", "holomem", "eriamo", "kurz", "harmonic attention",
        "adml", "archmind", "fehm", "qrm", "bielik", "speakleash",
        "implementuję", "implementacja", "debuguję", "refaktoruję",
        "klasa ", "metoda ", "funkcja ", "def ", "class ",
        "algorytm", "architektura", "moduł", "integracja",
        "trenuję", "fine-tuning", "embedding", "transformer",
        "naprawiam", "poprawka", "błąd w", "fix:",
        # Praca kodowa z agentem
        "pull request", " pr ", "commit", "diff", "refactor",
        "test ", "pytest", "bug", "issue", "todo", "wip",
        "holonos", "holography", "persistentmemory",
    )

    def __init__(self, embedder: Embedder, cfg: Config = None,
                 memory_path: str = "holon_memory.json"):
        self.embedder = embedder
        self.cfg      = cfg or Config(dim=embedder.dim)
        self.memory   = PersistentMemory(memory_path, dim=self.cfg.total_dim)

        self.phi: np.ndarray          = None
        self.store: list              = []
        self.turns: int               = 0
        self.phi_stability            = np.zeros(
            (self.cfg.phi_levels, self.cfg.k), dtype=np.float32)
        self.aii                      = AIIState(embedder)
        self._session_start_turn      = 0
        self._delta_hours             = 0.0
        self._last_wake               = ""
        self._last_coherence          = 1.0
        self.insight_llm_callback     = None

        self.last_error: Optional[np.ndarray]    = None
        self.prev_phi_center: Optional[np.ndarray] = None
        self._last_surprise: float               = 0.0
        self.W_time = np.random.randn(
            self.cfg.total_dim, self.cfg.total_dim) * 0.01
        self.W_gen  = np.random.randn(
            self.cfg.total_dim, self.cfg.total_dim) * 0.01
        self.temporal_error: Optional[np.ndarray] = None

        self.conversation_history: list = []
        self._topic_counter: dict       = {}

        if self.cfg.use_prism:
            pcfg = self.cfg.prism_cfg or PrismConfig()
            self.prism_router = PrismRouter(pcfg)
        else:
            self.prism_router = None

        # Bridge Transformer (opcjonalny) — lazy init + kalibracja przy pierwszym Φ.
        self.bridge_stack = None
        self._bridge_status = "off"
        self._bridge_calibrated = False
        if bool(getattr(self.cfg, "use_bridge", False)):
            self._bridge_status = "pending"
        self._last_bridge_energy: dict = {}

    def _ensure_bridge(self) -> bool:
        """Leniwie podłącz ``transform.py`` + krótka kalibracja. False = tor klasyczny."""
        if not bool(getattr(self.cfg, "use_bridge", False)):
            self._bridge_status = "off"
            return False
        if self.bridge_stack is not None and self._bridge_calibrated:
            return True
        if self._bridge_status == "unavailable":
            return False
        try:
            from holon_bridge import BridgeStack, load_bridge_module

            load_bridge_module()  # fail-fast jeśli brak transform.py
            d_model = int(getattr(self.cfg, "bridge_d_model", 64) or 64)
            n_heads = int(getattr(self.cfg, "bridge_n_heads", 4) or 4)
            n_layers = int(getattr(self.cfg, "bridge_n_layers", 2) or 2)
            if d_model % n_heads != 0:
                n_heads = 4 if d_model % 4 == 0 else 2
            self.bridge_stack = BridgeStack(
                d_model=d_model,
                n_heads=n_heads,
                n_layers=n_layers,
                n_classes=8,
                phi_levels=int(self.cfg.phi_levels),
                kind="bridge",
            )
            steps = int(getattr(self.cfg, "bridge_calibrate_steps", 400) or 0)
            if steps > 0 and not self._bridge_calibrated:
                self._calibrate_bridge_inplace(steps=steps, seed=11)
            self._bridge_calibrated = True
            self._bridge_status = "on"
            return True
        except Exception as e:
            self.bridge_stack = None
            self._bridge_status = f"unavailable:{type(e).__name__}"
            return False

    _BRIDGE_WEIGHT_CACHE: dict = {}

    def _calibrate_bridge_inplace(self, steps: int = 400, seed: int = 11) -> None:
        """Dopasuj wagi BridgeStack do retrieval po energii (bez Embeddera)."""
        import torch
        import torch.nn.functional as F
        from holon_bridge import load_bridge_module

        mod = load_bridge_module()
        fixed_path = __import__("pathlib").Path(
            getattr(mod, "__holon_bridge_path__", "")
        ).with_name("proca_bridge_transformer_fixed.py")
        if not fixed_path.is_file():
            return
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "holon_ext_bridge_fixed_cal", fixed_path
        )
        if spec is None or spec.loader is None:
            return
        fixed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixed)

        d_model = int(self.bridge_stack.d_model)
        n_heads = int(getattr(self.cfg, "bridge_n_heads", 4) or 4)
        n_layers = int(getattr(self.cfg, "bridge_n_layers", 2) or 2)
        cache_key = (d_model, n_heads, n_layers, int(steps), int(seed))
        model = self.bridge_stack.model
        cached = HoloMem._BRIDGE_WEIGHT_CACHE.get(cache_key)
        if cached is not None:
            model.load_state_dict(cached)
            model.eval()
            return

        # make_batch D=32; przy innym d_model — syntetyczne batche.
        torch.manual_seed(seed)
        model.train()
        opt = torch.optim.Adam(model.parameters(), lr=3e-3)
        n_classes = int(model.head.out_features)

        for _ in range(max(1, steps)):
            if d_model == 32:
                b = fixed.make_batch(B=64, N=24, D=32, n_content=min(8, n_classes))
                x, tracer, target = b.x, b.tracer, b.target
            else:
                B, N = 32, 16
                energy = torch.rand(B, N) * 3.0
                content = torch.randint(0, n_classes, (B, N))
                x = torch.zeros(B, N, d_model)
                n_content = min(n_classes, d_model)
                x[..., :n_content].scatter_(-1, content.unsqueeze(-1), 1.0)
                if d_model > n_content:
                    x[..., n_content:] = 0.15 * torch.randn(B, N, d_model - n_content)
                j = (energy[:, 1:] - energy[:, :1]).abs().argmin(1)
                target = content[torch.arange(B), j + 1]
                tracer = energy.unsqueeze(-1)
            logits, _, _ = model(x, tracer)
            loss = F.cross_entropy(logits, target)
            opt.zero_grad()
            loss.backward()
            opt.step()
        model.eval()
        HoloMem._BRIDGE_WEIGHT_CACHE[cache_key] = {
            k: v.detach().cpu().clone() for k, v in model.state_dict().items()
        }
    def _bridge_mix_active(
        self, active: list, emotion_w: float
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Złóż tokeny z Itemów (bez Embeddera.encode) → Bridge → (pattern, tracer).

        Zwraca ``(pattern[tdim], tracer[N])`` albo ``(None, None)`` przy fallbacku.
        """
        if not self._ensure_bridge() or self.bridge_stack is None:
            return None, None
        if len(active) < 2:
            return None, None
        import torch

        d_model = int(self.bridge_stack.d_model)
        tdim = int(self.cfg.total_dim)
        rows = []
        tracers = []
        for item in active[:32]:
            emb = np.asarray(item.emb_np(), dtype=np.float32).reshape(-1)
            if len(emb) < d_model:
                tok = np.concatenate(
                    [emb, np.zeros(d_model - len(emb), dtype=np.float32)]
                )
            else:
                tok = emb[:d_model].copy()
            n = float(np.linalg.norm(tok)) + 1e-8
            tok = tok / n
            rows.append(tok)
            phase = math.exp(-float(item.age) / float(self.cfg.vacuum_age_tau))
            tr = float(item.relevance) * phase * float(emotion_w)
            if item.is_work:
                tr *= 1.2
            if item.recalled:
                tr *= 1.5
            tracers.append(tr)
        x = torch.as_tensor(np.stack(rows, axis=0), dtype=torch.float32)  # [N,D]
        tracer = torch.as_tensor(tracers, dtype=torch.float32)
        try:
            fwd = self.bridge_stack.forward_tokens(x, tracer, pool="energy")
        except Exception:
            return None, None
        pat = np.asarray(fwd.pattern, dtype=np.float32).reshape(-1)
        if len(pat) < tdim:
            pat = np.concatenate([pat, np.zeros(tdim - len(pat), dtype=np.float32)])
        else:
            pat = pat[:tdim]
        n = float(np.linalg.norm(pat)) + 1e-8
        tr_np = np.asarray(tracers, dtype=np.float32)
        return (pat / n).astype(np.float32), tr_np

    # ── Session ────────────────────────────────────────────────────────────

    def start_session(self) -> dict:
        res               = self.memory.load(self.cfg)
        self.phi          = res["phi"]
        self.store        = res["store"]
        self.turns        = res["turns"]
        self._delta_hours = res["delta_hours"]
        self.aii.from_dict(res.get("aii", {}))
        # Healthy mind: po przerwie baseline afektu wraca (habituation),
        # vacuum nie zostaje zamrożony bez nowego bodźca.
        if getattr(self.cfg, "healthy_temporal_mode", True):
            self.aii.relax_toward_baseline(
                float(res.get("delta_hours") or 0.0),
                float(getattr(self.cfg, "aii_baseline_half_life_h", 72.0)))
        self._last_wake = res.get("wake") or ""
        self._last_coherence = float(res.get("coherence") or 1.0)

        saved_stab = res.get("phi_stability")
        if saved_stab is not None:
            try:
                arr = np.array(saved_stab, dtype=np.float32)
                if arr.shape == (self.cfg.phi_levels, self.cfg.k):
                    self.phi_stability = arr
                elif arr.ndim == 1 and len(arr) == self.cfg.k:
                    self.phi_stability = np.stack([
                        arr * (0.5 ** lv)
                        for lv in range(self.cfg.phi_levels)])
            except Exception:
                pass

        if res.get("W_time") is not None:
            wt = res["W_time"]
            if wt.shape == self.W_time.shape:
                self.W_time = wt
        if res.get("W_gen") is not None:
            wg = res["W_gen"]
            if wg.shape == self.W_gen.shape:
                self.W_gen = wg

        self._session_start_turn = self.turns
        return res

    # ── Cosine helpers ─────────────────────────────────────────────────────

    def _align(self, a: np.ndarray, b: np.ndarray):
        m = min(len(a), len(b))
        return a[:m], b[:m]

    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na < 1e-8 or nb < 1e-8:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def _csim(self, a: np.ndarray, b: np.ndarray) -> float:
        a_, b_ = self._align(a, b)
        return self._cosine_sim(a_, b_)

    # ── Phi center ─────────────────────────────────────────────────────────

    def _phi_center(self, query_emb: np.ndarray = None,
                    level: int = 2) -> np.ndarray:
        layer = self.phi[level]
        if query_emb is not None:
            q_dim = len(query_emb)
            sims  = np.array([
                self._cosine_sim(query_emb, layer[k][:q_dim])
                for k in range(self.cfg.k)
            ], dtype=np.float32)
            exp_s   = np.exp(sims - sims.max())
            weights = exp_s / (exp_s.sum() + 1e-8)
        else:
            norms   = np.linalg.norm(layer, axis=1)
            exp_n   = np.exp(norms - norms.max())
            weights = exp_n / (exp_n.sum() + 1e-8)
        center = sum(weights[k] * layer[k] for k in range(self.cfg.k))
        n = np.linalg.norm(center)
        return center / (n + 1e-8)

    # ── Recall ─────────────────────────────────────────────────────────────

    def _lexical_overlap(self, query_text: str, content: str) -> float:
        """Udział tokenów zapytania obecnych w treści ∈ [0, 1]."""
        min_len = int(getattr(self.cfg, "hybrid_min_token_len", 3))
        q_tok = {t for t in query_text.lower().replace(":", " ").split()
                 if len(t) >= min_len}
        if not q_tok:
            return 0.0
        c_low = content.lower()
        return sum(1 for t in q_tok if t in c_low) / len(q_tok)

    def _recall_item_pool(self, query_text: str = ""):
        """B2: pełny store lub kandydaci z ``lex_index`` gdy store duży."""
        store = self.store
        if not store:
            return store
        force = bool(getattr(self.cfg, "lexical_index_force", False))
        thr = int(getattr(self.cfg, "lexical_index_min_store", 500))
        if not force and len(store) < thr:
            return store
        idx = getattr(self, "lex_index", None)
        if idx is None or not query_text:
            return store
        max_c = int(getattr(self.cfg, "lexical_index_max_candidates", 256))
        try:
            idx.ensure(store)
            return idx.candidates(
                query_text, store, always_durable=True, max_candidates=max_c
            )
        except Exception:
            return store

    def _recall(self, query_emb_timed: np.ndarray, query_text: str = ""):
        if not self.store:
            return
        scores = {}
        cdim   = self.cfg.dim
        q_time = query_emb_timed[cdim:]
        lex_w  = float(getattr(self.cfg, "hybrid_lexical_weight", 0.18))
        pool   = self._recall_item_pool(query_text)

        for k in range(self.cfg.k):
            attractor = (0.6 * self.phi[2][k] +
                         0.3 * self.phi[1][k] +
                         0.1 * self.phi[0][k])
            for item in pool:
                emb   = item.emb_np()
                s_att = self._csim(emb[:cdim], attractor[:cdim])
                s_qry = self._csim(emb[:cdim], query_emb_timed[:cdim])
                time_sim    = (self._cosine_sim(emb[cdim:], q_time)
                               if len(q_time) > 0 else 1.0)
                time_weight = np.exp(2.0 * (time_sim - 1.0))
                # Suma zamiast iloczynu: przy słabym KuRz iloczyn → 0 i gubi fakty.
                score = (0.55 * max(0.0, s_qry) + 0.45 * max(0.0, s_att)) * time_weight
                if query_text:
                    score += lex_w * self._lexical_overlap(query_text, item.content)
                if item.is_fact:
                    score *= (1.0 + 0.2 / (1.0 + item.age * 0.1))
                if item.is_work:
                    score *= (1.0 + 0.4 / (1.0 + item.age * 0.05))
                if item.is_reminder:
                    score *= 1.15
                if id(item) not in scores or score > scores[id(item)][0]:
                    scores[id(item)] = (score, item, k)

        ranked = sorted(scores.values(), key=lambda x: -x[0])
        for _, item, k in ranked[:self.cfg.top_n_recall]:
            item.recalled = True
            self.phi_stability[2][k] += 1.0

    # ── Vacuum ─────────────────────────────────────────────────────────────

    def _vacuum(self, query_emb_timed: np.ndarray):
        center   = self._phi_center(query_emb_timed, level=2)
        cdim     = self.cfg.dim
        center_c = center[:cdim] / (np.linalg.norm(center[:cdim]) + 1e-8)
        q_time   = query_emb_timed[cdim:]

        def _durable(item) -> bool:
            return bool(item.is_insight or item.is_fact or item.is_work
                        or item.is_reminder)

        if self.turns > 0 and self.turns % self.cfg.soft_vacuum_interval == 0:
            for item in self.store:
                if not _durable(item):
                    item.relevance *= self.cfg.soft_decay_factor

        for item in self.store:
            if _durable(item):
                # Fakty/work: nie rozwadniaj relevance samym dopasowaniem do Φ.
                item.relevance = max(0.5, item.relevance)
                continue
            sem = self._cosine_sim(item.emb_content(cdim), center_c)
            item.relevance = 0.6 * sem + 0.4 * item.relevance
            item.relevance = max(0.05, item.relevance)

        hpi = self.cfg.hard_prune_interval
        hpm = self.cfg.hard_prune_store_max
        if (self.turns > 0 and self.turns % hpi == 0) or len(self.store) > hpm:
            threshold    = self.cfg.threshold * self.aii.get_threshold_multiplier(
                self.cfg.aii_adapt_range)
            session_age  = self.turns - self._session_start_turn
            if session_age < self.cfg.vacuum_warmup_turns:
                threshold *= (0.5 + 0.5 * session_age / self.cfg.vacuum_warmup_turns)

            def _score(item):
                if _durable(item):
                    return 1e6 + item.relevance
                sim      = self._cosine_sim(item.emb_content(cdim), center_c)
                time_sim = (self._cosine_sim(item.emb_time(cdim), q_time)
                            if len(q_time) > 0 else 1.0)
                entropy  = 0.1 * (1.0 - abs(sim)) + max(0.0, 1.0 - time_sim)
                fe       = -sim + entropy
                return -(fe - 0.2 * item.relevance)

            self.store = [
                i for i in self.store
                if ((i.age <= 1 and i.relevance > 0.2) or i.recalled
                    or _durable(i)
                    or i.relevance > 0.3 or _score(i) >= threshold)
            ]
            MAX_STORE = min(self.cfg.n * 6, hpm)
            if len(self.store) > MAX_STORE:
                durable = [i for i in self.store if _durable(i)]
                rest = [i for i in self.store if not _durable(i)]
                rest.sort(key=_score, reverse=True)
                budget = max(0, MAX_STORE - len(durable))
                self.store = durable + rest[:budget]

    # ── Update phi ─────────────────────────────────────────────────────────

    def _update_phi(self, window: list):
        if not window:
            return
        window_ids = {id(i) for i in window}
        active = [i for i in self.store
                  if id(i) in window_ids or i.age <= 1 or i.recalled]
        if not active:
            return

        base_emo_w = self.aii.get_emotion_weight()
        emotion_w  = (base_emo_w * self.cfg.focus_boost
                      if self.aii.focus_active else base_emo_w)

        tdim    = self.cfg.total_dim
        pattern = np.zeros(tdim, dtype=np.float32)
        for item in active:
            phase  = math.exp(-item.age / self.cfg.vacuum_age_tau)
            weight = 2.0 if item.recalled else (1.5 if item.age <= 1 else 1.0)
            if item.is_insight:
                weight *= 2.0
            sign = 1.0 if (item.recalled or item.age <= 1 or item.is_insight) else -0.3
            emb  = item.emb_np()
            if len(emb) < tdim:
                emb = np.concatenate(
                    [emb, np.zeros(tdim - len(emb), dtype=np.float32)])
            pattern += sign * phase * weight * emotion_w * emb

        n = np.linalg.norm(pattern)
        if n < 1e-8:
            return
        pattern /= n

        # Bridge (gdy ON): mixer tokenów+sondy bez Embeddera → wejście do Prism.
        # Opcjonalnie: struktura energii (tracer) moduluje importance → p[lv].
        bridge_tracer = None
        self._last_bridge_energy = {}
        if bool(getattr(self.cfg, "use_bridge", False)):
            mixed, bridge_tracer = self._bridge_mix_active(active, emotion_w)
            if mixed is not None:
                pattern = mixed

        recalled_count = sum(1 for i in window if i.recalled)
        importance     = emotion_w * (1.0 + 0.3 * recalled_count)
        if (
            bridge_tracer is not None
            and bool(getattr(self.cfg, "bridge_energy_to_importance", False))
            and self.prism_router is not None
        ):
            try:
                from holon_bridge import bridge_energy_importance

                ir = getattr(self.prism_router.cfg, "importance_range", (0.8, 2.6))
                importance, emeta = bridge_energy_importance(
                    importance, bridge_tracer, importance_range=ir
                )
                self._last_bridge_energy = dict(emeta)
            except Exception:
                self._last_bridge_energy = {"ok": 0.0, "error": 1.0}

        def _norm_v(v):
            nv = np.linalg.norm(v)
            return v / (nv + 1e-8)

        if self.cfg.use_prism and self.prism_router is not None:
            prism_updates, prism_p, _ = self.prism_router.route(importance, pattern)
            self.W_gen *= 0.999

            for lv in range(self.cfg.phi_levels):
                if prism_p[lv] < 1e-4:
                    continue
                shifted_lv = prism_updates[lv] / (prism_p[lv] + 1e-8)
                layer_lv   = self.phi[lv]
                sims_lv    = np.array([
                    float(np.dot(shifted_lv, layer_lv[k]) /
                          (np.linalg.norm(layer_lv[k]) + 1e-8))
                    for k in range(self.cfg.k)], dtype=np.float32)
                exp_lv = np.exp(sims_lv - sims_lv.max())
                w_lv   = exp_lv / (exp_lv.sum() + 1e-8)
                w_lv   = w_lv + 0.05
                w_lv[0] *= 0.1
                w_lv   /= (w_lv.sum() + 1e-8)

                for k in range(self.cfg.k):
                    layer_old = layer_lv[k].copy()
                    mu_k      = np.tanh(self.W_gen @ layer_lv[k])
                    mu_k     /= (np.linalg.norm(mu_k) + 1e-8)
                    eps_local = shifted_lv - mu_k
                    eps_total = (
                        0.6 * _norm_v(eps_local)
                        + 0.25 * _norm_v(self.last_error[:len(eps_local)])
                        + 0.15 * _norm_v(
                            self.temporal_error[:len(eps_local)]
                            if self.temporal_error is not None
                            else np.zeros_like(eps_local))
                    ) if self.last_error is not None else eps_local
                    eps_total   = np.clip(eps_total, -0.3, 0.3)
                    sigma_k     = np.linalg.norm(eps_local)
                    precision_k = min(5.0, 1.0 / (sigma_k + 1e-4))
                    lr_k        = self.cfg.lr * w_lv[k] * precision_k * prism_p[lv]
                    layer_lv[k] += lr_k * eps_total
                    layer_lv[k] *= 0.9995
                    layer_lv[k] /= (np.linalg.norm(layer_lv[k]) + 1e-8)
                    self.W_gen  += lr_k * np.outer(eps_local, layer_old)

                self.phi_stability[lv] += w_lv * prism_p[lv]
                self.phi_stability[lv]  = np.clip(
                    self.phi_stability[lv], 0, self.cfg.phi_stability_max)
                self.phi_stability[lv] *= self.cfg.phi_stability_decay

            w_norm = np.linalg.norm(self.W_gen)
            if w_norm > 5.0:
                self.W_gen *= 5.0 / w_norm

            dom_lv       = int(np.argmax(prism_p))
            shifted_dom  = prism_updates[dom_lv] / (prism_p[dom_lv] + 1e-8)
            self._last_surprise = float(np.mean([
                np.linalg.norm(
                    shifted_dom - np.tanh(self.W_gen @ self.phi[dom_lv][k]))
                for k in range(self.cfg.k)]))
            level = dom_lv

        else:
            if importance < 1.2:   level = 0
            elif importance < 1.8: level = 1
            else:                  level = 2

            shift           = self.cfg.phase_shifts[level]
            shifted_pattern = HolographicInterference.phase_shift(pattern, shift)
            layer           = self.phi[level]
            sims            = np.array([
                float(np.dot(shifted_pattern, layer[k]) /
                      (np.linalg.norm(layer[k]) + 1e-8))
                for k in range(self.cfg.k)], dtype=np.float32)
            exp_s   = np.exp(sims - sims.max())
            weights = exp_s / (exp_s.sum() + 1e-8)
            weights = weights + 0.05
            weights[0] *= 0.1
            weights /= (weights.sum() + 1e-8)

            self.W_gen *= 0.999
            for k in range(self.cfg.k):
                layer_old = layer[k].copy()
                mu_k      = np.tanh(self.W_gen @ layer[k])
                mu_k     /= (np.linalg.norm(mu_k) + 1e-8)
                eps_local = shifted_pattern - mu_k
                eps_total = (
                    0.6 * _norm_v(eps_local)
                    + 0.25 * _norm_v(self.last_error[:len(eps_local)])
                    + 0.15 * _norm_v(
                        self.temporal_error[:len(eps_local)]
                        if self.temporal_error is not None
                        else np.zeros_like(eps_local))
                ) if self.last_error is not None else eps_local
                eps_total   = np.clip(eps_total, -0.3, 0.3)
                sigma_k     = np.linalg.norm(eps_local)
                precision_k = min(5.0, 1.0 / (sigma_k + 1e-4))
                lr_k        = self.cfg.lr * weights[k] * precision_k
                layer[k]   += lr_k * eps_total
                layer[k]   *= 0.9995
                layer[k]   /= (np.linalg.norm(layer[k]) + 1e-8)
                self.W_gen += lr_k * np.outer(eps_local, layer_old)

            w_norm = np.linalg.norm(self.W_gen)
            if w_norm > 5.0:
                self.W_gen *= 5.0 / w_norm
            self.phi_stability[level] += weights
            self.phi_stability[level]  = np.clip(
                self.phi_stability[level], 0, self.cfg.phi_stability_max)
            self.phi_stability[level] *= self.cfg.phi_stability_decay
            self._last_surprise = float(np.mean([
                np.linalg.norm(
                    shifted_pattern - np.tanh(self.W_gen @ self.phi[level][k]))
                for k in range(self.cfg.k)]))

        if self._last_surprise > self.cfg.surprise_trigger:
            self.cfg.lr *= (1.0 + self.cfg.surprise_adapt_rate)
        else:
            self.cfg.lr *= (1.0 - self.cfg.surprise_adapt_rate * 0.5)
        self.cfg.lr = float(np.clip(self.cfg.lr, self.cfg.lr_min, self.cfg.lr_max))

        self.phi *= 0.999
        self.phi  = np.clip(self.phi, -1.0, 1.0)

        beta = self.cfg.phi_ortho_beta
        if beta > 0.0:
            for lv in range(self.cfg.phi_levels):
                phi_new = self.phi[lv].copy()
                for i in range(self.cfg.k):
                    row = self.phi[lv][i].copy()
                    for j in range(self.cfg.k):
                        if i != j:
                            row -= (beta * float(np.dot(row, self.phi[lv][j]))
                                    * self.phi[lv][j])
                    phi_new[i] = row / (np.linalg.norm(row) + 1e-8)
                self.phi[lv] = phi_new

        lr_cross = self.cfg.lr * 0.3
        for lv in range(self.cfg.phi_levels - 1):
            low  = self._phi_center(level=lv)
            high = self._phi_center(level=lv + 1)
            p    = min(len(low), len(high))
            e    = high[:p] - low[:p]
            n    = np.linalg.norm(e)
            if n > 1e-8:
                e = np.clip(e / n, -0.3, 0.3)
                for k in range(self.cfg.k):
                    self.phi[lv][k][:p]   += lr_cross * e
                    self.phi[lv][k]       /= (np.linalg.norm(self.phi[lv][k]) + 1e-8)
                    self.phi[lv+1][k][:p] -= lr_cross * 0.5 * e
                    self.phi[lv+1][k]     /= (np.linalg.norm(self.phi[lv+1][k]) + 1e-8)

        for lv in range(self.cfg.phi_levels):
            if np.std(self.phi_stability[lv]) > 2.0:
                wi    = int(np.argmin(self.phi_stability[lv]))
                noise = np.random.randn(tdim).astype(np.float32) * 0.005
                self.phi[lv][wi] += noise
                self.phi[lv][wi] /= (np.linalg.norm(self.phi[lv][wi]) + 1e-8)

    # ── Merge / deduplicate ────────────────────────────────────────────────

    def _semantic_merge(self, item: Item, new_emb: np.ndarray) -> None:
        cdim     = self.cfg.dim
        c1, c2   = item.emb_content(cdim), new_emb[:cdim]
        t2       = new_emb[cdim:]
        c_merged = (item.cluster_size * c1 + c2) / (item.cluster_size + 1.0)
        merged   = np.concatenate([c_merged, t2])
        merged  /= (np.linalg.norm(merged) + 1e-8)
        old_size = item.cluster_size
        item.cluster_size += 1
        item.created_at    = (old_size * item.created_at + time.time()) / item.cluster_size
        item.embedding     = merged.tolist()
        item.relevance     = min(5.0, item.relevance + 0.2)
        item.age           = 0
        item._norm         = -1.0

    # ── Helpers ────────────────────────────────────────────────────────────

    def _detect_fact_work(self, text: str) -> tuple:
        is_fact = (any(p in text.lower() for p in self.FACT_PATTERNS)
                   and "?" not in text)
        is_work = (self.aii.focus_active
                   or any(p in text.lower() for p in self.FOCUS_PATTERNS))
        return is_fact, is_work

    def _find_best_match(self, emb: np.ndarray) -> tuple:
        best_sim, best_item = -1.0, None
        for i in self.store:
            sim = self._csim(emb, i.emb_np())
            if sim > best_sim:
                best_sim, best_item = sim, i
        return best_sim, best_item

    # ── Build messages ─────────────────────────────────────────────────────

    def _build_messages(self, window: list, user_message: str,
                        system_prompt: str) -> list:
        msgs = ([{"role": "system", "content": system_prompt}]
                if system_prompt else [])
        mem_parts = []
        try:
            from holon_prompts import (
                format_internal_state,
                format_temporal_context,
                format_memory_bullet,
            )
            mem_parts.append(format_internal_state(self.aii))
            # Widoczne w ROZMOWIE (nie tylko digest CLI): pastness + oś
            mem_parts.append(format_temporal_context(
                delta_hours=float(self._delta_hours or 0.0),
                wake=getattr(self, "_last_wake", "") or "",
                coherence=float(getattr(self, "_last_coherence", 1.0) or 1.0),
                turns=int(self.turns or 0),
                store_size=len(self.store or []),
                window_items=window or [],
                timeline_n=int(getattr(self.cfg, "digest_timeline_items", 8)),
            ))
            _bullet = format_memory_bullet
        except ImportError:
            emo_pl = {
                "radosc": "radość/ekscytacja", "zaskoczenie": "zaskoczenie/ciekawość",
                "strach": "niepokój/błąd",     "zlosc": "frustracja/złość",
                "smutek": "smutek/melancholia", "neutral": "spokój/neutralność",
            }.get(self.aii.emotion, self.aii.emotion)
            mem_parts.append(
                f"[SYSTEM - STAN WEWNĘTRZNY]\n"
                f"Dominująca emocja układu: {emo_pl}\n"
                f"Napięcie kognitywne (vacuum): {self.aii.vacuum_signal:+.2f}\n"
                f"Focus na zadaniu: {'AKTYWNY' if self.aii.focus_active else 'BRAK'}\n"
                f"Nie recytuj tego bloku. Najpierw treść, barwa w tle."
            )
            _bullet = lambda i, max_len=300: f"• {(i.content or '')[:max_len]}"

        if window:
            ctx        = [i for i in window if i.content != user_message]
            work_items = [i for i in ctx if i.is_work]
            fact_items = [i for i in ctx if i.is_fact and not i.is_work]
            regular    = [i for i in ctx if not i.is_fact and not i.is_work]

            if work_items:
                mem_parts.append(
                    "AKTYWNE PROJEKTY (najwyższy priorytet — z datą):\n"
                    + "\n".join(_bullet(i, 400) for i in work_items))
            if fact_items:
                mem_parts.append(
                    "TRWAŁE FAKTY (prawdziwe; to było wtedy — nie „wieczne teraz”):\n"
                    + "\n".join(_bullet(i, 300) for i in fact_items))
            if regular:
                max_chars = max(200, 9856 // max(1, len(regular)))
                mem_parts.append(
                    "PAMIĘĆ SESJI (epizody z dystansem czasowym):\n" + "\n---\n".join(
                        f"[{_bullet(i, max_chars).lstrip('• ').strip()}]"
                        f"{' ★' if i.recalled else ''}"
                        f"{' 💡' if i.is_insight else ''}"
                        for i in regular))

        if mem_parts:
            msgs.append({"role": "system",
                         "content": "\n\n".join(mem_parts)})

        for entry in self.conversation_history:
            msgs.append(entry)
        msgs.append({"role": "user", "content": user_message})
        return msgs

    # ── Turn / after_turn ──────────────────────────────────────────────────

    def turn(self, user_message: str, system_prompt: str = "") -> list:
        # Auto-init jeśli start_session nie zostało wywołane
        if self.phi is None:
            self.start_session()
        
        q_timed        = self.embedder.encode(user_message, timestamp=time.time())
        current_center = self._phi_center(level=2)

        if self.prev_phi_center is not None:
            pred_center    = self.W_time @ self.prev_phi_center
            pred_center   /= (np.linalg.norm(pred_center) + 1e-8)
            temporal_error = current_center - pred_center
            temporal_error /= (np.linalg.norm(temporal_error) + 1e-8)
            self.temporal_error = temporal_error.copy()
            raw_spatial    = np.clip(
                q_timed[:len(current_center)] - current_center, -0.5, 0.5)
            combined       = (0.7 * raw_spatial
                              + 0.3 * temporal_error[:len(raw_spatial)])
            self.last_error = (0.7 * self.last_error + 0.3 * combined
                               if self.last_error is not None else combined)
            grad  = np.outer(
                current_center - self.prev_phi_center, self.prev_phi_center)
            g_norm = np.linalg.norm(grad)
            if g_norm > 1e-6:
                grad /= g_norm
            self.W_time += self.cfg.lr * 0.1 * grad
            decay = 0.999 - 0.2 * min(1.0, self._last_surprise)
            self.W_time = (decay * self.W_time
                           + (1 - decay) * np.eye(self.cfg.total_dim))
            w_norm = np.linalg.norm(self.W_time)
            if w_norm > 5.0:
                self.W_time *= 5.0 / w_norm
        else:
            self.last_error     = np.clip(
                q_timed[:len(current_center)] - current_center, -0.5, 0.5)
            self.temporal_error = None

        self._recall(q_timed, query_text=user_message)

        skip = False
        if self.store:
            best_sim, best_item = self._find_best_match(q_timed)
            is_new_fact, is_new_work = self._detect_fact_work(user_message)
            if best_sim > 0.95:
                self._semantic_merge(best_item, q_timed)
                best_item.is_fact = best_item.is_fact or is_new_fact
                best_item.is_work = best_item.is_work or is_new_work
                skip = True

        if not skip:
            is_fact, is_work = self._detect_fact_work(user_message)
            self.store.append(Item(
                id=str(uuid.uuid4()),
                content=user_message[:500],
                embedding=q_timed.tolist(),
                age=0, is_fact=is_fact, is_work=is_work))

        self._vacuum(q_timed)
        window = self._build_window(q_timed)
        self._update_phi(window)
        for item in self.store:
            item.recalled = False
        self.turns += 1
        self.prev_phi_center = self._phi_center(level=2).copy()
        return self._build_messages(window, user_message, system_prompt)

    def after_turn(self, user_message: str, response: str) -> None:
        response = response or "[brak odpowiedzi]"
        MAX_C    = 500
        combined = (f"User: {user_message[:MAX_C]}\n"
                    f"Assistant: {response[:MAX_C]}")
        t_now    = time.time()
        comb_emb = self.embedder.encode(combined, timestamp=t_now)
        self.aii.update(user_message + " " + response, comb_emb)

        skip = False
        if self.store:
            best_sim, best_item = self._find_best_match(comb_emb)
            is_new_fact, is_new_work = self._detect_fact_work(user_message)
            if best_sim > 0.95:
                self._semantic_merge(best_item, comb_emb)
                best_item.is_fact = best_item.is_fact or is_new_fact
                best_item.is_work = best_item.is_work or is_new_work
                skip = True

        if not skip:
            is_fact, is_work = self._detect_fact_work(user_message)
            self.store.append(Item(
                id=str(uuid.uuid4()),
                content=combined[:800],
                embedding=comb_emb.tolist(),
                relevance=self.aii.get_emotion_weight(),
                is_fact=is_fact, is_work=is_work))

        self._vacuum(comb_emb)
        self._update_phi(self._build_window(comb_emb))
        for it in self.store:
            it.age += 1

        # v5.11: conversation history
        self.conversation_history.append(
            {"role": "user", "content": user_message[:300]})
        self.conversation_history.append(
            {"role": "assistant", "content": response[:300]})
        max_h = self.cfg.conversation_history_size * 2
        if len(self.conversation_history) > max_h:
            self.conversation_history = self.conversation_history[-max_h:]

        # v5.11: topic counter
        STOP = {
            "i","w","z","na","do","że","to","a","o","się","jak","co","czy",
            "nie","tak","już","jest","tego","jego","jej","ich","ten","tej",
            "być","mnie","moje","swój","przez","przy","pod","nad","też","ale",
            "lub","the","is","in","of","and","it","this","that","are","was",
            "for","with","have","has","will","been","they","lubię","lubisz",
            "mówię","mówisz","myślę","myślisz","chcę","chcesz","mogę",
            "możesz","wiem","wiesz",
        }
        raw_words = re.sub(r'[^\w\s]', '', user_message.lower()).split()
        keywords  = [w for w in set(raw_words) if len(w) >= 5 and w not in STOP]
        for kw in keywords:
            self._topic_counter[kw] = self._topic_counter.get(kw, 0) + 1
            if self._topic_counter[kw] == self.cfg.topic_repeat_threshold:
                fact_content = f"Użytkownik wielokrotnie poruszał temat: {kw}"
                fact_emb     = self.embedder.encode(fact_content, timestamp=time.time())
                already = any(
                    self._cosine_sim(
                        np.array(i.embedding[:self.cfg.dim], dtype=np.float32),
                        fact_emb[:self.cfg.dim]) > 0.85
                    for i in self.store if i.is_fact)
                if not already:
                    self.store.append(Item(
                        id=str(uuid.uuid4()), content=fact_content,
                        embedding=fact_emb.tolist(), relevance=1.5,
                        is_fact=True))
                    print(f"[ConvTracker] Nowy fakt: '{fact_content}'")

        self.ruminate()
        self.memory.save(self.phi, self.store, self.turns, self.cfg,
                         self.aii.to_dict(), self.phi_stability.tolist(),
                         self.W_time, self.W_gen)
        if hasattr(self.embedder, 'save'):
            self.embedder.save()

    # ── Reminders ──────────────────────────────────────────────────────────

    def add_reminder(self, text: str, timestamp: float) -> None:
        emb = self.embedder.encode(text, timestamp=timestamp)
        self.store.append(Item(
            id=str(uuid.uuid4()), content=text,
            embedding=emb.tolist(), created_at=timestamp,
            is_reminder=True, relevance=2.0))
        print(f"[Przypomnienie] Dodano: '{text}' na "
              f"{datetime.datetime.fromtimestamp(timestamp)}")
        self.memory.save(self.phi, self.store, self.turns, self.cfg,
                         self.aii.to_dict(), self.phi_stability.tolist(),
                         self.W_time, self.W_gen)

    # POPRAWIONA METODA get_upcoming_reminders (bez AttributeError)
    def get_upcoming_reminders(self, within_seconds: int = 3600) -> list:
        now = time.time()
        out = [i for i in self.store
               if getattr(i, 'is_reminder', False) and now <= i.created_at <= now + within_seconds]
        out.sort(key=lambda x: x.created_at)
        return out

    # ── Ruminate ───────────────────────────────────────────────────────────

    def ruminate(self, force: bool = False) -> Optional[str]:
        if not force and self.turns % self.cfg.rumination_interval != 0:
            return None
        core  = self.phi[2].mean(axis=0)
        short = self.phi[0].mean(axis=0)
        mid   = self.phi[1].mean(axis=0)
        projs = [HolographicInterference.phase_shift(core, s)
                 for s in self.cfg.rumination_shifts]
        incs  = [abs(float(np.dot(p, short)) - float(np.dot(p, mid)))
                 for p in projs]
        max_inc = max(incs)

        if self.cfg.phase_shifts_learnable:
            target = self.cfg.rumination_threshold / 2.0
            lr_ps  = 0.05
            for lv in range(self.cfg.phi_levels):
                lv_lr = lr_ps * (0.5 ** (self.cfg.phi_levels - 1 - lv))
                self.cfg.phase_shifts[lv] += lv_lr * (target - max_inc)
                self.cfg.phase_shifts[lv] %= 1.0

        if max_inc <= self.cfg.rumination_threshold and not force:
            return None

        reflection = ""
        if self.insight_llm_callback is not None:
            try:
                prompt     = self.cfg.insight_prompt_template.format(max_inc=max_inc)
                reflection = self.insight_llm_callback(prompt)[:400]
            except Exception:
                pass

        if not reflection or "brak insightu" in reflection.lower():
            return None

        t_now = time.time()
        emb   = self.embedder.encode(reflection, timestamp=t_now)
        cdim  = self.cfg.dim
        sim_c = self._cosine_sim(emb[:cdim], self._phi_center(level=2)[:cdim])
        sim_s = self._cosine_sim(emb[:cdim], self._phi_center(level=0)[:cdim])
        score = 0.7 * sim_c + 0.3 * sim_s
        if score < 0.35:
            print(f"[Ruminacja t={self.turns}] Odrzucono insight "
                  f"(score: {score:.2f})")
            return None

        shifted = HolographicInterference.phase_shift(emb, 0.9)
        tdim    = self.cfg.total_dim
        if len(shifted) < tdim:
            shifted = np.concatenate(
                [shifted, np.zeros(tdim - len(shifted), dtype=np.float32)])
        shifted = shifted[:tdim]
        shifted /= (np.linalg.norm(shifted) + 1e-8)

        alpha = min(0.2, 0.02 + 0.1 * max(0.0, sim_c))
        for k in range(self.cfg.k):
            self.phi[2][k] = (1.0 - alpha) * self.phi[2][k] + alpha * shifted
            self.phi[2][k] /= (np.linalg.norm(self.phi[2][k]) + 1e-8)

        self.store.append(Item(
            id=f"insight-{uuid.uuid4().hex[:8]}", content=reflection,
            embedding=emb.tolist(), age=0, relevance=2.5, created_at=t_now,
            is_insight=True, insight_level=2, cluster_size=1))
        print(f"\n[Ruminacja] Niespójność: {max_inc:.3f} → insight zaktualizowany")
        return reflection

    # ── Build window ───────────────────────────────────────────────────────

    def _build_window(self, query_emb: np.ndarray) -> list:
        center      = self._phi_center(query_emb, level=2)
        cdim        = self.cfg.dim
        center_c    = center[:cdim] / (np.linalg.norm(center[:cdim]) + 1e-8)
        protected   = [i for i in self.store
                       if i.age <= 1 or i.recalled or i.is_fact or i.is_work]
        prot_ids    = {id(i) for i in protected}
        candidates  = sorted(
            [i for i in self.store if id(i) not in prot_ids],
            key=lambda x: -self._cosine_sim(x.emb_content(cdim), center_c))
        return (protected + candidates)[:self.cfg.n]

    # ── Recall at time ─────────────────────────────────────────────────────

    def recall_at(self, query: str, target_time: float, top_k: int = 5) -> list:
        hours_ago = (time.time() - target_time) / 3600.0
        phi_then  = np.zeros_like(self.phi)
        for lv in range(self.cfg.phi_levels):
            phi_then[lv] = TimeDecay.evolve_phi(
                self.phi[lv], hours_ago,
                self.cfg.phi_half_life_hours, self.cfg.phi_min_norm, level=lv)
        q_full   = self.embedder.encode(query, timestamp=target_time)
        cdim     = self.cfg.dim
        q_c      = q_full[:cdim]
        layer    = phi_then[2]
        norms    = np.linalg.norm(layer, axis=1)
        exp_n    = np.exp(norms - norms.max())
        wts      = exp_n / (exp_n.sum() + 1e-8)
        center_c = sum(wts[k] * layer[k] for k in range(self.cfg.k))
        center_c = center_c[:cdim] / (np.linalg.norm(center_c[:cdim]) + 1e-8)
        scored   = []
        for item in self.store:
            e_c = item.emb_content(cdim)
            e_t = item.emb_np()[cdim:]
            q_t = q_full[cdim:]
            s1  = self._cosine_sim(e_c, q_c)
            s2  = self._cosine_sim(e_t, q_t) if len(e_t) == len(q_t) else 0.0
            s3  = self._cosine_sim(e_c, center_c)
            scored.append((item, 0.5 * s1 + 0.2 * s2 + 0.3 * s3))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    # ── Stats / reset ──────────────────────────────────────────────────────

    def set_insight_callback(self, cb) -> None:
        self.insight_llm_callback = cb

    def stats(self) -> dict:
        if self.phi is None:
            return {"turns": 0, "store": 0, "phi_norms": [],
                    "phi_stability": [], "aii": self.aii.to_dict(),
                    "delta_hours": 0.0, "warning": "start_session() not called"}
        phi_norms = [np.linalg.norm(self.phi[lv], axis=1).tolist()
                     for lv in range(self.cfg.phi_levels)]
        return {
            "turns":         self.turns,
            "store":         len(self.store),
            "phi_norms":     phi_norms,
            "phi_stability": self.phi_stability.tolist(),
            "aii":           self.aii.to_dict(),
            "delta_hours":   round(self._delta_hours, 2),
            "phase_shifts":  list(self.cfg.phase_shifts),
            "last_error_norm": round(float(np.linalg.norm(self.last_error)), 4)
                               if self.last_error is not None else 0.0,
            "temporal_drift": round(float(np.linalg.norm(
                self._phi_center(level=2) - self.prev_phi_center))
                if self.prev_phi_center is not None else 0.0, 4),
            "surprise":      round(self._last_surprise, 4),
            "lr_current":    round(self.cfg.lr, 5),
            "prism_mode":    self.cfg.use_prism,
            "bridge_mode":   bool(getattr(self.cfg, "use_bridge", False)),
            "bridge_status": getattr(self, "_bridge_status", "off"),
            "bridge_energy_to_importance": bool(
                getattr(self.cfg, "bridge_energy_to_importance", False)
            ),
            "bridge_energy": dict(getattr(self, "_last_bridge_energy", {}) or {}),
        }

    def reset(self):
        self.memory.delete()
        self.phi              = PersistentMemory._init_phi(self.cfg)
        self.phi_stability    = np.zeros(
            (self.cfg.phi_levels, self.cfg.k), dtype=np.float32)
        self.store            = []
        self.turns            = 0
        self._delta_hours     = 0.0
        self.aii              = AIIState(self.embedder)
        self._session_start_turn = 0
        self.last_error       = None
        self.prev_phi_center  = None
        self._last_surprise   = 0.0
        self.W_time = np.random.randn(
            self.cfg.total_dim, self.cfg.total_dim) * 0.01
        self.W_gen  = np.random.randn(
            self.cfg.total_dim, self.cfg.total_dim) * 0.01
        self.temporal_error       = None
        self.conversation_history = []
        self._topic_counter       = {}
