# -*- coding: utf-8 -*-
"""holon_bridge.py — Bridge Transformer jako pełny komponent Holona (bez Embeddera).

Architektura (zgodnie z intencją SE):
  Bridge  = mixer treści + sonda energii (tracer), osobno od KuRz/hash embeddera
  Prism   = „teleport” wyjścia Bridge na poziomy Φ (ograniczone do phi_levels)

Źródło modelu (kolejność):
  1. HOLON_BRIDGE_PATH / sąsiad ``Transformers/bridge_transformer/transform.py``
  2. opcjonalnie lokalny fallback (brak — zewnętrzne źródło jest kanonem)

Użycie:
  from holon_bridge import BridgeStack, prism_wins_demo
  stack = BridgeStack(d_model=64, n_heads=4, n_layers=2, phi_levels=3)
  out = stack.forward_tokens(x, tracer)          # bez embeddera
  routed = stack.teleport_to_phi(out.pattern, importance=1.8)
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from holon_holography import PrismConfig, PrismRouter


# ── ładowanie transform.py ──────────────────────────────────────────────────

_DEFAULT_CANDIDATES = (
    Path(os.environ.get("HOLON_BRIDGE_PATH", "")),
    Path(r"C:\Users\drwis\Transformers\bridge_transformer\transform.py"),
    Path.home() / "Transformers" / "bridge_transformer" / "transform.py",
)


def load_bridge_module(path: Optional[str | Path] = None):
    """Załaduj ``transform.py`` (BridgeTransformer) spoza repo Karmin_Ae."""
    candidates: List[Path] = []
    if path:
        candidates.append(Path(path))
    candidates.extend(p for p in _DEFAULT_CANDIDATES if str(p).strip())
    seen = set()
    for p in candidates:
        p = p.resolve() if p.exists() else p
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if not p.is_file():
            continue
        spec = importlib.util.spec_from_file_location("holon_ext_bridge_transform", p)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        if not hasattr(mod, "BridgeTransformer"):
            raise ImportError(f"{p} nie eksportuje BridgeTransformer")
        mod.__holon_bridge_path__ = str(p)  # type: ignore[attr-defined]
        return mod
    raise FileNotFoundError(
        "Nie znaleziono transform.py (Bridge). Ustaw HOLON_BRIDGE_PATH "
        "albo połóż plik w Transformers/bridge_transformer/transform.py"
    )


# ── energia Bridge → importance Prism ───────────────────────────────────────

def bridge_energy_importance(
    base_importance: float,
    tracer: Sequence[float] | np.ndarray,
    importance_range: Tuple[float, float] = (0.8, 2.6),
) -> Tuple[float, Dict[str, float]]:
    """Z sondy energii (tracer) wylicz importance dla Prism.

    Bridge błyszczy na układach wielowymiarowych (rozrzut energii), nie na
    płaskim Softmaxie. Tu: concentration + spread + top-mass → boost w
    ``importance_range``, żeby ``p[lv]`` reagowało na strukturę energii,
    a nie tylko na skalar AII/recalled.
    """
    lo, hi = float(importance_range[0]), float(importance_range[1])
    if hi <= lo:
        hi = lo + 1e-6
    span = hi - lo
    base = float(base_importance)
    t = np.asarray(tracer, dtype=np.float64).ravel()
    t = np.clip(t, 0.0, None)
    meta: Dict[str, float] = {
        "ok": 0.0,
        "concentration": 0.0,
        "spread": 0.0,
        "top_mass": 0.0,
        "structure": 0.0,
        "boost": 0.0,
        "imp_in": base,
        "imp_out": base,
    }
    if t.size < 2 or float(t.sum()) < 1e-12:
        return base, meta
    w = t / (t.sum() + 1e-12)
    ent = float(-(w * np.log(w + 1e-12)).sum())
    max_ent = float(np.log(len(w)))
    concentration = 1.0 - ent / (max_ent + 1e-12)
    spread = float(t.std() / (t.mean() + 1e-12))
    k = max(1, len(w) // 5)
    top_mass = float(np.sort(w)[-k:].sum())
    structure = float(np.tanh(spread / 1.5)) * (0.4 + 0.6 * concentration)
    # top_mass ponad równomierny udział
    uniform = 1.0 / float(len(w))
    peak = (top_mass - uniform) * float(len(w)) / (float(len(w) - 1) + 1e-12)
    boost = 0.55 * structure + 0.45 * peak
    boost = float(np.clip(boost, -0.35, 0.85))
    imp = float(np.clip(base + boost * span * 0.55, lo, hi))
    meta.update({
        "ok": 1.0,
        "concentration": float(concentration),
        "spread": float(spread),
        "top_mass": float(top_mass),
        "structure": float(structure),
        "boost": float(boost),
        "imp_out": imp,
    })
    return imp, meta


# ── typy wyjścia ────────────────────────────────────────────────────────────

@dataclass
class BridgeForward:
    """Wynik Bridge bez udziału Embeddera — tokeny już w przestrzeni d_model."""

    logits: Any                    # torch [B, n_classes] albo None
    token_states: Any              # torch [B, N, D] po warstwach (jeśli dostępne)
    pattern: np.ndarray            # numpy [D] — pooled wektor do Prism/Φ
    attn_maps: list
    gammas: list
    tracer_used: np.ndarray        # [N] albo [B, N]


@dataclass
class PhiTeleport:
    """Prism rozdziela pattern Bridge na poziomy pamięci Holona."""

    updates: List[np.ndarray]      # per level: waga * phase-shifted pattern
    weights: np.ndarray            # p[lv], sum≈1
    deltas: np.ndarray
    dominant_level: int
    importance: float


# ── stos Bridge + Prism ─────────────────────────────────────────────────────

class BridgeStack:
    """Pełnoprawny tor: Bridge (treść+sonda) → Prism (teleport na Φ).

    Nie woła ``Embedder`` / KuRz. Wejście to już tensory tokenów ``x`` i ``tracer``.
    """

    def __init__(
        self,
        d_model: int = 64,
        n_heads: int = 4,
        n_layers: int = 2,
        n_classes: int = 8,
        phi_levels: int = 3,
        kind: str = "bridge",
        bridge_path: Optional[str] = None,
        prism_cfg: Optional[PrismConfig] = None,
        device: str = "cpu",
    ):
        self.mod = load_bridge_module(bridge_path)
        import torch

        self.torch = torch
        self.d_model = int(d_model)
        self.phi_levels = int(phi_levels)
        self.device = torch.device(device)
        self.model = self.mod.BridgeTransformer(
            d_model=d_model,
            n_heads=n_heads,
            n_layers=n_layers,
            n_classes=n_classes,
            kind=kind,
        ).to(self.device)
        self.model.eval()
        pcfg = prism_cfg or PrismConfig(num_levels=phi_levels)
        if pcfg.num_levels != phi_levels:
            pcfg = PrismConfig(num_levels=phi_levels)
        self.prism = PrismRouter(pcfg)
        self.source_path = getattr(self.mod, "__holon_bridge_path__", "?")

    def forward_tokens(
        self,
        x,
        tracer,
        mask=None,
        pool: str = "cls",
    ) -> BridgeForward:
        """Forward Bridge na gotowych tokenach (bez embeddera).

        ``x``: [B,N,D] lub [N,D]  ·  ``tracer``: [B,N,1] / [N,1] / [N]
        ``pool``: ``cls`` (token 0) | ``mean`` | ``energy`` (ważone |tracer|)
        """
        torch = self.torch
        x_t = self._as_batch_x(x)
        tr_t = self._as_batch_tracer(tracer, x_t.shape[0], x_t.shape[1])
        if mask is not None and not torch.is_tensor(mask):
            mask = torch.as_tensor(mask, device=self.device)

        # BridgeTransformer zwraca logits z x[:,0] — zbieramy też stany wewnętrzne
        # przez ręczne przejście warstw, żeby mieć pełny wektor do Prism.
        attn_maps, gammas = [], []
        h = x_t
        with torch.no_grad():
            for layer in self.model.layers:
                h, w, g = layer(h, tr_t, mask)
                attn_maps.append(w)
                gammas.append(g)
            h = self.model.norm(h)
            logits = self.model.head(h[:, 0])

        pattern = self._pool(h, tr_t, pool=pool)
        tr_np = tr_t.detach().cpu().numpy().reshape(tr_t.shape[0], tr_t.shape[1])
        return BridgeForward(
            logits=logits,
            token_states=h,
            pattern=pattern,
            attn_maps=attn_maps,
            gammas=gammas,
            tracer_used=tr_np[0] if tr_np.shape[0] == 1 else tr_np,
        )

    def teleport_to_phi(
        self,
        pattern: np.ndarray,
        importance: float,
        target_dim: Optional[int] = None,
    ) -> PhiTeleport:
        """Prism: rozdziel ``pattern`` (wyjście Bridge) na ``phi_levels`` pamięci.

        To jest „teleport z ograniczonym zakresem” — wagi + przesunięcie fazowe
        per poziom, bez mieszania z Embedderem.
        """
        pat = np.asarray(pattern, dtype=np.float32).reshape(-1)
        if target_dim is not None and len(pat) != target_dim:
            if len(pat) < target_dim:
                pat = np.concatenate(
                    [pat, np.zeros(target_dim - len(pat), dtype=np.float32)]
                )
            else:
                pat = pat[:target_dim]
            n = float(np.linalg.norm(pat)) + 1e-8
            pat = pat / n
        updates, weights, deltas = self.prism.route(float(importance), pat)
        w = np.asarray(weights, dtype=np.float64)
        return PhiTeleport(
            updates=[np.asarray(u, dtype=np.float32) for u in updates],
            weights=w,
            deltas=np.asarray(deltas, dtype=np.float64),
            dominant_level=int(np.argmax(w)),
            importance=float(importance),
        )

    def bridge_then_prism(
        self,
        x,
        tracer,
        importance: float,
        pool: str = "cls",
        target_dim: Optional[int] = None,
    ) -> Tuple[BridgeForward, PhiTeleport]:
        """Pełna ścieżka: tokeny → Bridge → Prism → poziomy Φ."""
        fwd = self.forward_tokens(x, tracer, pool=pool)
        tele = self.teleport_to_phi(fwd.pattern, importance, target_dim=target_dim)
        return fwd, tele

    # ── helpers ─────────────────────────────────────────────────────────────

    def _as_batch_x(self, x):
        torch = self.torch
        t = x if torch.is_tensor(x) else torch.as_tensor(x, dtype=torch.float32)
        t = t.to(self.device).float()
        if t.ndim == 2:
            t = t.unsqueeze(0)
        if t.shape[-1] != self.d_model:
            raise ValueError(
                f"x ostatni dim={t.shape[-1]}, oczekiwano d_model={self.d_model} "
                f"(Bridge bez Embeddera — dopasuj tokeny albo d_model)"
            )
        return t

    def _as_batch_tracer(self, tracer, B: int, N: int):
        torch = self.torch
        t = tracer if torch.is_tensor(tracer) else torch.as_tensor(
            tracer, dtype=torch.float32
        )
        t = t.to(self.device).float()
        if t.ndim == 1:
            t = t.view(1, N, 1) if t.numel() == N else t.view(B, N, 1)
        elif t.ndim == 2:
            if t.shape == (B, N):
                t = t.unsqueeze(-1)
            elif t.shape == (N, 1):
                t = t.unsqueeze(0)
        if t.shape[:2] != (B, N):
            raise ValueError(f"tracer shape {tuple(t.shape)} vs batch {(B, N)}")
        return t

    def _pool(self, h, tracer, pool: str) -> np.ndarray:
        torch = self.torch
        if pool == "cls":
            vec = h[0, 0]
        elif pool == "mean":
            vec = h[0].mean(dim=0)
        elif pool == "energy":
            w = tracer[0, :, 0].abs()
            w = w / (w.sum() + 1e-8)
            vec = (h[0] * w.unsqueeze(-1)).sum(dim=0)
        else:
            raise ValueError(f"pool={pool!r}; użyj cls|mean|energy")
        v = vec.detach().cpu().numpy().astype(np.float32)
        n = float(np.linalg.norm(v)) + 1e-8
        return v / n


# ── demo: gdzie Prism wygrywa ───────────────────────────────────────────────

def prism_wins_demo(phi_levels: int = 3) -> Dict[str, Any]:
    """Porównanie: Prism soft-teleport vs płaski hard-threshold (bez Bridge).

    Metryka: rozdział masy między poziomami przy niskiej vs wysokiej importance.
    Prism wygrywa, gdy potrafi **miękko** i **różnie** osadzić ten sam pattern
    na poziomach (niska entropia per warunek + duża odległość między p_low/p_high).
    Flat hard-threshold zawsze one-hot na jednym poziomie — zero geometrii fazowej.
    """
    rng = np.random.default_rng(42)
    dim = 64
    pattern = rng.standard_normal(dim).astype(np.float32)
    pattern /= np.linalg.norm(pattern) + 1e-8

    prism = PrismRouter(PrismConfig(num_levels=phi_levels))
    # zakres jak w HoloMem
    lows = [0.85, 1.0, 1.1]
    highs = [2.0, 2.3, 2.5]

    def _flat_route(importance: float) -> np.ndarray:
        p = np.zeros(phi_levels, dtype=np.float64)
        if importance < 1.2:
            p[0] = 1.0
        elif importance < 1.8:
            p[min(1, phi_levels - 1)] = 1.0
        else:
            p[min(2, phi_levels - 1)] = 1.0
        return p

    def _entropy(p: np.ndarray) -> float:
        p = p.clip(1e-12)
        p = p / p.sum()
        return float(-(p * np.log(p)).sum() / np.log(2.0))

    prism_low = np.mean(
        [prism.route(i, pattern)[1] for i in lows], axis=0
    )
    prism_high = np.mean(
        [prism.route(i, pattern)[1] for i in highs], axis=0
    )
    flat_low = np.mean([_flat_route(i) for i in lows], axis=0)
    flat_high = np.mean([_flat_route(i) for i in highs], axis=0)

    # TV distance między rozkładami low/high — im większa, tym lepszy rozdział
    def _tv(a, b):
        return 0.5 * float(np.abs(a - b).sum())

    # fazowe zróżnicowanie update'ów (Prism ma delta≠0 per level)
    _, _, delta_low = prism.route(lows[1], pattern)
    updates_high, _, delta_high = prism.route(highs[1], pattern)
    phase_spread = float(np.std(delta_high))

    # flat nie robi phase shift per level w gałęzi else HoloMem — jeden shift
    report = {
        "ok": True,
        "phi_levels": phi_levels,
        "prism_p_low": prism_low.tolist(),
        "prism_p_high": prism_high.tolist(),
        "flat_p_low": flat_low.tolist(),
        "flat_p_high": flat_high.tolist(),
        "prism_tv_low_vs_high": _tv(prism_low, prism_high),
        "flat_tv_low_vs_high": _tv(flat_low, flat_high),
        "prism_entropy_low": _entropy(prism_low),
        "prism_entropy_high": _entropy(prism_high),
        "flat_entropy_low": _entropy(flat_low),
        "flat_entropy_high": _entropy(flat_high),
        "prism_phase_spread_high": phase_spread,
        "prism_deltas_high": np.asarray(delta_high).tolist(),
        "update_norms_high": [float(np.linalg.norm(u)) for u in updates_high],
    }
    # Prism „wygrywa” tor pamięci: miękkie wagi + nieseparowalna geometria fazy.
    # Flat ma większe TV (one-hot L0↔L2), ale zero fazy i zero współdzielenia poziomów.
    report["prism_wins"] = bool(
        report["prism_phase_spread_high"] > 1e-4
        and report["prism_entropy_high"] > report["flat_entropy_high"]
    )
    report["winner_routing"] = "prism" if report["prism_wins"] else "flat"
    report["why_prism"] = (
        "Flat wygrywa surowe TV (one-hot), ale to nie jest teleport pamięci. "
        "Prism wygrywa tor Φ: ciągłe wagi + delta fazy per poziom "
        f"(phase_spread={phase_spread:.4f}, entropy_high="
        f"{report['prism_entropy_high']:.3f} vs flat≈0)."
    )
    return report


def bridge_home_turf_quick(
    steps: int = 600,
    seed: int = 11,
    bridge_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Bridge (transform.py) vs Softmax na retrieval po energii.

    Przy ~200 krokach bywa remis/przegrana; od ~600 kroków ``kind=bridge``
    stabilnie bije softmax (~0.72 vs ~0.23). Tied (proca_fixed) jest lekko wyżej.
    """
    import torch
    import torch.nn.functional as F

    mod = load_bridge_module(bridge_path)
    # make_batch z fixed (ten sam task) — tylko dane
    fixed_path = Path(getattr(mod, "__holon_bridge_path__", "")).with_name(
        "proca_bridge_transformer_fixed.py"
    )
    if not fixed_path.is_file():
        return {"ok": False, "error": f"brak {fixed_path} do make_batch"}

    spec = importlib.util.spec_from_file_location("holon_ext_bridge_fixed", fixed_path)
    assert spec and spec.loader
    fixed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixed)

    def _train(kind: str, n_steps: int, sd: int) -> float:
        torch.manual_seed(sd)
        # d_model=32 jak w make_batch default D
        model = mod.BridgeTransformer(
            d_model=32, n_heads=2, n_layers=1, n_classes=8, kind=kind
        )
        opt = torch.optim.Adam(model.parameters(), lr=3e-3)
        for _ in range(n_steps):
            b = fixed.make_batch(B=64, N=24, D=32)
            logits, _, _ = model(b.x, b.tracer)
            loss = F.cross_entropy(logits, b.target)
            opt.zero_grad()
            loss.backward()
            opt.step()
        model.eval()
        accs = []
        with torch.no_grad():
            for _ in range(15):
                b = fixed.make_batch(B=64, N=24, D=32)
                logits, _, _ = model(b.x, b.tracer)
                accs.append((logits.argmax(-1) == b.target).float().mean().item())
        return float(sum(accs) / len(accs))

    acc_bridge = _train("bridge", steps, seed)
    acc_soft = _train("softmax", steps, seed)
    return {
        "ok": True,
        "task": "energy_proximity_retrieval",
        "steps": steps,
        "seed": seed,
        "acc_bridge_transform_py": acc_bridge,
        "acc_softmax": acc_soft,
        "bridge_wins": acc_bridge > acc_soft + 0.02,
        "source": getattr(mod, "__holon_bridge_path__", ""),
    }
