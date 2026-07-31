# -*- coding: utf-8 -*-
"""holon/aii.py — Stan emocjonalny (AIIState) i dekad czasowy (TimeDecay)

TimeDecay / baseline: model „zdrowego” powrotu do spokoju po przerwie
(habituation), nie utrzymywanie nieskończonego napięcia bez nowego sygnału.
"""

import math
import time
import numpy as np


class AIIState:
    WEIGHTS = {
        "radosc": 1.3, "zaskoczenie": 1.3, "strach": 1.2,
        "zlosc":  1.2, "smutek": 0.8,      "neutral": 1.0,
    }
    VACUUM_SIGNALS = {
        "radosc": +1.0, "zaskoczenie": +0.5, "strach": -1.0,
        "zlosc":  -1.0, "smutek": -0.5,      "neutral": 0.0,
    }
    KEYWORDS = {
        "radosc":      ["super", "swietnie", "doskonale", "rewelacja", "great"],
        "zaskoczenie": ["wow", "niesamowite", "naprawde", "really"],
        "strach":      ["blad", "error", "crash", "problem", "awaria", "fail", "bug"],
        "zlosc":       ["nie dziala", "znowu", "broken", "wrong"],
        "smutek":      ["niestety", "szkoda", "nie pomaga"],
        "focus":       ["implementacja", "debug", "refaktor", "kod",
                        "architektura", "softmax", "eriamo", "holon"],
    }
    T = 0.7

    def __init__(self, embedder=None):
        self.embedder      = embedder
        self.emotion       = "neutral"
        self.vacuum_signal = 0.0
        self.focus_active  = False
        self.ref_emotions  = {}
        if embedder is not None:
            self._build_refs(embedder)

    def _build_refs(self, embedder):
        def _norm(text):
            v = embedder.encode(text, timestamp=None)
            return v / (np.linalg.norm(v) + 1e-8)
        self.ref_emotions = {
            "radosc":      _norm("sukces świetnie doskonale rewelacja"),
            "zaskoczenie": _norm("wow niesamowite zaskoczenie naprawdę"),
            "strach":      _norm("błąd error problem awaria krytyczne"),
            "zlosc":       _norm("nie działa zepsute błąd znowu"),
            "smutek":      _norm("niestety szkoda smutno żal"),
            "focus":       _norm("implementacja kod architektura debug refactor"),
        }

    def update(self, text: str, text_emb: np.ndarray = None):
        t = text.lower()
        if self.ref_emotions and text_emb is not None:
            dim = min(len(text_emb),
                      len(next(iter(self.ref_emotions.values()))))
            t_c  = text_emb[:dim] / (np.linalg.norm(text_emb[:dim]) + 1e-8)
            sims = {emo: float(np.dot(t_c, ref[:dim])) / self.T
                    for emo, ref in self.ref_emotions.items()}
            self.focus_active = sims.get("focus", 0) > 0.45
            best_e, best_s = "neutral", 0.4
            for emo, sim in sims.items():
                if emo == "focus":
                    continue
                if sim > best_s:
                    best_s, best_e = sim, emo
            self.emotion = best_e
            sig = self.VACUUM_SIGNALS.get(best_e, 0.0)
        else:
            self.focus_active = any(kw in t for kw in self.KEYWORDS["focus"])
            best_e, best_hits, sig = "neutral", 0, 0.0
            for emo, kws in self.KEYWORDS.items():
                if emo == "focus":
                    continue
                hits = sum(1 for kw in kws if kw in t)
                if hits > best_hits:
                    best_hits, best_e = hits, emo
                    sig = self.VACUUM_SIGNALS.get(emo, 0.0)
            self.emotion = best_e
        self.vacuum_signal = 0.7 * self.vacuum_signal + 0.3 * sig

    def relax_toward_baseline(self, delta_hours: float,
                              half_life_hours: float = 72.0) -> None:
        """Po przerwie: napięcie i fokus wracają ku neutral — healthy habituation.

        Bez nowego bodźca vacuum nie powinien „trzymać alarmu” w nieskończoność.
        Emocja wraca do neutral przy wystarczająco długiej ciszy.
        """
        if delta_hours is None or delta_hours < 0.5:
            return
        hl = max(1.0, float(half_life_hours))
        # retencja napięcia spada z czasem nieobecności
        retain = math.exp(-0.693 * abs(delta_hours) / hl)
        self.vacuum_signal = float(self.vacuum_signal) * retain
        if abs(self.vacuum_signal) < 0.05:
            self.vacuum_signal = 0.0
        # po ~2 half-life bez bodźca — emocja baseline
        if retain < 0.25:
            self.emotion = "neutral"
            self.focus_active = False
        elif retain < 0.5 and self.emotion != "neutral":
            # częściowe wyciszenie: zostaw emocję, zdejmij focus
            self.focus_active = False

    def get_emotion_weight(self) -> float:
        return self.WEIGHTS.get(self.emotion, 1.0)

    def get_threshold_multiplier(self, adapt_range: float) -> float:
        return 1.0 + adapt_range * self.vacuum_signal

    def to_dict(self) -> dict:
        return {
            "emotion":       self.emotion,
            "vacuum_signal": round(self.vacuum_signal, 3),
            "focus":         self.focus_active,
        }

    def from_dict(self, data: dict) -> None:
        if not data:
            return
        self.emotion       = data.get("emotion", "neutral")
        self.vacuum_signal = float(data.get("vacuum_signal", 0.0))
        self.focus_active  = data.get("focus", False)


class TimeDecay:
    @staticmethod
    def decay_factor(delta_hours: float, half_life_hours: float) -> float:
        return math.exp(-0.693 * delta_hours / (half_life_hours + 1e-8))

    @staticmethod
    def evolve_phi(phi: np.ndarray, delta_hours: float,
                   hl_list: list, min_norm: float,
                   level: int = 0) -> np.ndarray:
        if abs(delta_hours) < 0.1:
            return phi
        evolved = phi.copy()
        if hl_list and isinstance(hl_list[0], list):
            row = hl_list[level] if level < len(hl_list) else hl_list[-1]
        else:
            row = hl_list
        for k in range(len(phi)):
            hl = row[k] if k < len(row) else 24.0
            df = TimeDecay.decay_factor(abs(delta_hours), hl)
            evolved[k] = phi[k] * df
            n = np.linalg.norm(evolved[k])
            if n < min_norm:
                evolved[k] = evolved[k] / (n + 1e-8) * min_norm
        return evolved

    @staticmethod
    def format_pastness(delta_hours: float) -> str:
        """Ludzki dystans czasowy (pastness), nie surowy float."""
        if delta_hours is None or delta_hours < 0:
            return "nieznany czas"
        m = delta_hours * 60.0
        if m < 90:
            return f"{max(1, int(m))} min temu"
        if delta_hours < 36:
            return f"{delta_hours:.0f} h temu"
        d = delta_hours / 24.0
        if d < 14:
            return f"{d:.0f} d temu"
        if d < 60:
            return f"{d/7.0:.0f} tyg. temu"
        if d < 730:
            return f"{d/30.0:.0f} mies. temu"
        return f"{d/365.0:.1f} lat temu"

    @staticmethod
    def wake_message(delta_hours: float, turns: int,
                     store_size: int, coherence: float) -> str:
        if delta_hours < 0.1:
            return ""
        past = TimeDecay.format_pastness(delta_hours)
        # coh: retencja stanu po przerwie — „to było wtedy, stan się przesunął”
        coh = float(coherence) if coherence is not None else 1.0
        if coh >= 0.7:
            coh_note = "stan po przerwie bliski zapisanemu"
        elif coh >= 0.35:
            coh_note = "stan częściowo przesunięty przez czas (normalny dryf)"
        else:
            coh_note = "długi dystans czasowy — rdzeń zubożony, fakty kalendarzowe ważne"
        return (
            f"[Oś czasu: ostatni zapis był {past} "
            f"(Δ≈{delta_hours:.0f} h). Tur łącznie: {turns}, "
            f"wzorców po load: {store_size}. {coh_note} "
            f"(spójność stanu Φ≈{coh:.2f}). "
            f"To jest PRZESZŁOŚĆ sesji — teraźniejszość to ta rozmowa.]"
        )
