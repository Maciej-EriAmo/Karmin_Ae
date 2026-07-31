# -*- coding: utf-8 -*-
"""holon/holography.py — HRR, PrismRouter, fazowe przesunięcia

Zmiany względem wersji poprzedniej (nic nie usunięto — tylko korekty i dodatki):
  * _to_unitary: klucz cache'a niezależny od dtype i uwzględniający kształt.
  * bind/unbind: jawne błędy wymiarów zamiast assert (assert znika pod `python -O`);
    unbind ma tryb strict=True (domyślny) oraz zachowaną ścieżkę obcinania.
  * PrismConfig: nowe pola theta_base, target_delta, tir_margin, importance_range;
    domyślne theta_ref przeskalowane do zakresu importance ∈ [0, 1].
  * PrismConfig: uogólnienie A/n/theta_ref na dowolne num_levels + walidacja długości.
  * PrismRouter: progi całkowitego wewnętrznego odbicia (TIR) liczone analitycznie
    i użyte jako dolna granica clipu — trygonometria pryzmatu przestaje degenerować
    się do funkcji afinicznej.
  * PrismRouter: target_delta wyliczany z geometrii, a nie zaszyty jako [0.3, 0.9, 1.5].
  * PrismRouter: diagnostyka (last_theta, last_tir_mask, describe()).
"""

import os
import hashlib
import numpy as np
from dataclasses import dataclass, field


class HolographicInterference:
    _unitary_cache: dict = {}
    _ANCHOR_SEED: str = os.environ.get("HOLON_ANCHOR_SEED", "holon-eriamo-4242")

    @staticmethod
    def _to_unitary(v: np.ndarray) -> np.ndarray:
        v = np.asarray(v)
        # KOREKTA: klucz cache'a nie może zależeć od dtype wejścia — float32 i float64
        # o tej samej wartości dawały wcześniej dwa różne wpisy. Kształt też wchodzi
        # do klucza, bo tobytes() sam z siebie nie rozróżnia (n,) od (1, n).
        key = (v.shape, np.round(v.astype(np.float64), 4).tobytes())
        if key in HolographicInterference._unitary_cache:
            return HolographicInterference._unitary_cache[key]
        v_fft  = np.fft.fft(v)
        result = v_fft / (np.abs(v_fft) + 1e-8)
        if len(HolographicInterference._unitary_cache) >= 512:
            HolographicInterference._unitary_cache.clear()
        HolographicInterference._unitary_cache[key] = result
        return result

    @staticmethod
    def _salt_key(key: np.ndarray, item_id: str) -> np.ndarray:
        combined = (item_id + HolographicInterference._ANCHOR_SEED).encode()
        h = int(hashlib.sha256(combined).hexdigest()[:16], 16) % (2**32)
        rng  = np.random.default_rng(h)
        salt = rng.standard_normal(len(key)).astype(np.float32) * 0.1
        salted = key + salt
        return salted / (np.linalg.norm(salted) + 1e-8)

    @staticmethod
    def bind(v1: np.ndarray, v2: np.ndarray, item_id: str = "") -> list:
        v1 = np.asarray(v1, dtype=np.float32)
        v2 = np.asarray(v2, dtype=np.float32)
        # KOREKTA: ValueError zamiast assert — asercje są wycinane pod `python -O`,
        # a cicha niezgodność wymiarów w bind jest błędem nie do wykrycia później.
        if v1.shape != v2.shape:
            raise ValueError(f"bind: niezgodność wymiarów {v1.shape} != {v2.shape}")
        key  = HolographicInterference._salt_key(v2, item_id) if item_id else v2
        v2_u = HolographicInterference._to_unitary(key)
        bound = np.fft.ifft(np.fft.fft(v1) * v2_u).real.astype(np.float32)
        return bound.tolist()

    @staticmethod
    def unbind(bound_data: list, key: np.ndarray,
               item_id: str = "", strict: bool = True) -> np.ndarray:
        """Odwrotność bind().

        strict=True (domyślnie): niezgodność długości bound vs key to błąd.
        Powód: obcięcie wektorów PRZED FFT nie daje "częściowego" odbindowania —
        splot cykliczny w R^k to inna algebra niż w R^n, więc wynik nie jest
        przybliżeniem oryginału, tylko innym wektorem. Cicha degradacja jakości
        pamięci była tu trudna do zdiagnozowania.

        strict=False: zachowana stara ścieżka obcinania do min_len.
        """
        key   = HolographicInterference._salt_key(key, item_id) if item_id else key
        key   = np.asarray(key, dtype=np.float32)
        bound = np.array(bound_data, dtype=np.float32)
        if len(bound) != len(key):
            if strict:
                raise ValueError(
                    f"unbind: niezgodność wymiarów {len(bound)} != {len(key)}. "
                    f"Użyj strict=False, aby świadomie obciąć do min_len."
                )
            min_len = min(len(bound), len(key))
            bound   = bound[:min_len]
            key     = key[:min_len]
        key_u   = HolographicInterference._to_unitary(key)
        unbound = np.fft.ifft(np.fft.fft(bound) * np.conj(key_u)).real.astype(np.float32)
        return unbound / (np.linalg.norm(unbound) + 1e-8)

    @staticmethod
    def phase_shift(v: np.ndarray, shift: float) -> np.ndarray:
        if abs(shift) < 1e-6:
            return np.asarray(v, dtype=np.float32).copy()
        v_c    = np.asarray(v, dtype=np.complex128)
        fft_v  = np.fft.fft(v_c)
        dim    = len(v)
        freqs  = np.fft.fftfreq(dim)
        angles = 2.0 * np.pi * freqs * shift
        rotated = np.fft.ifft(fft_v * np.exp(1j * angles)).real.astype(np.float32)
        n = np.linalg.norm(rotated)
        return rotated / (n + 1e-8)


@dataclass
class PrismConfig:
    num_levels:           int        = 3
    A:                    np.ndarray = None
    n:                    np.ndarray = None
    gamma:                float      = 8.0
    alpha:                float      = 0.4
    theta_ref:            np.ndarray = None
    bias:                 float      = 0.03
    first_level_damping:  float      = 0.12

    # --- NOWE POLA (dodane, nic nie zastępują) ---------------------------------
    theta_base:           float      = 1.0
    """Kąt bazowy padania [rad]. Wcześniej zaszyty w route() jako 0.8.
    Podniesiony do 1.0, bo 0.8 leżało zbyt blisko progu TIR poziomu 0 (0.514)."""

    target_delta:         np.ndarray = None
    """Docelowe odchylenie pryzmatu na poziom. None => wyliczane z geometrii
    w PrismRouter.__init__ (dawniej zaszyte jako [0.3, 0.9, 1.5])."""

    tir_margin:           float      = 0.02
    """Margines [rad] nad progiem całkowitego wewnętrznego odbicia."""

    importance_range:     tuple      = (0.8, 2.6)
    """Zakres, w jakim faktycznie przychodzi `importance`. TO JEST GŁÓWNE POKRĘTŁO.

    Wartość domyślna wynika z HoloMem._update_phi:
        importance = emotion_w * (1 + 0.3 * recalled_count)
        emotion_w  = AIIState.WEIGHTS[emocja] * (focus_boost jeśli focus)
                   -> {0.8 ... 1.3} * {1.0, 1.25} = 0.8 .. 1.625
        recalled_count <= top_n_recall = 2      -> mnożnik 1.0 .. 1.6
        czyli importance ∈ [0.80, 2.60]
    Kontrola krzyżowa: gałąź BEZ pryzmatu tnie na 1.2 i 1.8 — oba progi leżą
    wewnątrz tego przedziału, więc zakres się zgadza."""

    auto_scale:           bool       = True
    """Gdy True, `theta_ref`, `alpha` i `theta_base` są wyliczane z
    `importance_range` oraz z okna bez TIR, tak by ŻADEN poziom nie wpadał
    w clip na krańcach zakresu. Ustaw False, aby stroić ręcznie."""

    theta_max_margin:     float      = 0.1
    """Odsunięcie górnego clipu od pi/2."""

    delta_scale:          float      = None
    """Skala normalizacji argumentu cosinusa. None => auto-kalibracja z geometrii.
    Bez tego cos(delta - target) pracuje w otoczeniu swojego maksimum, gdzie jest
    płaski w drugim rzędzie: przy domyślnych parametrach cały zakres importance
    dawał rozrzut score rzędu 0.06 nata, czyli softmax praktycznie jednorodny."""

    def __post_init__(self):
        L = int(self.num_levels)
        if L < 1:
            raise ValueError(f"PrismConfig: num_levels musi być >= 1, jest {L}")

        if self.A is None:
            # Uogólnienie: dla L == 3 daje dokładnie stare [60, 55, 50] stopni.
            self.A = np.deg2rad(np.linspace(60.0, 60.0 - 5.0 * (L - 1), L))
        if self.n is None:
            self.n = np.linspace(1.52, 1.52 + 0.03 * (L - 1), L)

        if self.auto_scale:
            # Wypełniane w PrismRouter.__init__ — dopiero tam znane jest okno TIR.
            pass
        elif self.theta_ref is None:
            # KOREKTA KLUCZOWA: stare [1.0, 2.2, 3.5] było odniesione do importance
            # w skali ~[0, 4]. Przy importance ∈ [0, 1] dawało to:
            #   theta[1] < 0.1 dla importance < 0.45  (clip)
            #   theta[2] < 0.1 dla importance < 1.75  (clip ZAWSZE)
            # czyli poziomy 2 i 3 miały stałą wagę niezależną od wejścia.
            # Nowe wartości rozkładają punkty odniesienia równomiernie w [0, 1].
            lo, hi = 0.25, 0.75
            self.theta_ref = (np.full(L, 0.5) if L == 1
                              else np.linspace(lo, hi, L))

        self.A = np.asarray(self.A, dtype=np.float64)
        self.n = np.asarray(self.n, dtype=np.float64)
        if self.theta_ref is not None:
            self.theta_ref = np.asarray(self.theta_ref, dtype=np.float64)

        checks = [("A", self.A), ("n", self.n)]
        if self.theta_ref is not None:
            checks.append(("theta_ref", self.theta_ref))
        for name, arr in checks:
            if arr.shape != (L,):
                raise ValueError(
                    f"PrismConfig: {name} ma kształt {arr.shape}, oczekiwano ({L},)"
                )
        if np.any(self.n <= 1.0):
            raise ValueError(f"PrismConfig: n musi być > 1.0, jest {self.n}")

        if self.target_delta is not None:
            self.target_delta = np.asarray(self.target_delta, dtype=np.float64)
            if self.target_delta.shape != (L,):
                raise ValueError(
                    f"PrismConfig: target_delta ma kształt {self.target_delta.shape}, "
                    f"oczekiwano ({L},)"
                )


class PrismRouter:
    def __init__(self, cfg: PrismConfig):
        self.cfg = cfg

        # --- Próg całkowitego wewnętrznego odbicia (TIR), analitycznie -----------
        # Warunek braku TIR na drugiej ściance:  n * sin(A - phi1) <= 1
        #   phi1 = arcsin(sin(theta)/n)
        #   =>  arcsin(sin(theta)/n) >= A - arcsin(1/n)
        #   =>  theta >= arcsin( n * sin(A - arcsin(1/n)) )
        # Dla domyślnej konfiguracji: [0.514, 0.408, 0.299] rad = [29.4, 23.4, 17.1] deg.
        crit = self.cfg.A - np.arcsin(1.0 / self.cfg.n)
        self.theta_min_tir = np.where(
            crit <= 0.0,
            0.0,
            np.arcsin(np.clip(self.cfg.n * np.sin(np.clip(crit, 0.0, np.pi / 2)), -1.0, 1.0)),
        )
        self.theta_lo = self.theta_min_tir + self.cfg.tir_margin
        self.theta_hi = np.pi / 2 - self.cfg.theta_max_margin
        if np.any(self.theta_lo >= self.theta_hi):
            bad = np.where(self.theta_lo >= self.theta_hi)[0].tolist()
            raise ValueError(
                f"PrismRouter: brak okna bez TIR dla poziomów {bad} "
                f"(theta_lo={self.theta_lo}, theta_hi={self.theta_hi}). "
                f"Zmniejsz A lub n."
            )

        # --- target_delta z geometrii, nie z magicznych liczb --------------------
        # Każdy poziom jest strojony tak, by osiągać maksimum score dokładnie wtedy,
        # gdy importance == theta_ref[lv] (wtedy theta[lv] == theta_base).
        if self.cfg.target_delta is None:
            theta_at_ref = np.clip(
                np.full(self.cfg.num_levels, self.cfg.theta_base),
                self.theta_lo, self.theta_hi,
            )
            self.target_delta = self.deviation_angle(theta_at_ref)
        else:
            self.target_delta = np.asarray(self.cfg.target_delta, dtype=np.float64)

        # --- auto-skalowanie do rzeczywistego zakresu importance -----------------
        # POWÓD: pierwsza wersja tej poprawki zakładała importance ∈ [0, 1]
        # i miała theta_ref = [0.25, 0.5, 0.75]. Prawdziwy zakres w HoloMem to
        # [0.80, 2.60] — przy importance > ~1.5 WSZYSTKIE poziomy wpadały w górny
        # clip (theta = 1.471), delta stawała się identyczna i wagi znów były
        # płaskie [0.057, 0.472, 0.472]. Zamiast wpisywać kolejne stałe, wagi
        # są teraz wyprowadzane z zadeklarowanego zakresu, więc ta klasa błędu
        # nie może się powtórzyć przy zmianie WEIGHTS albo focus_boost.
        if self.cfg.auto_scale:
            lo, hi = float(self.cfg.importance_range[0]), float(self.cfg.importance_range[1])
            if hi <= lo:
                raise ValueError(f"PrismRouter: pusty importance_range {(lo, hi)}")
            span = hi - lo
            L    = self.cfg.num_levels
            inset = 0.15 * span
            ref = (np.full(L, 0.5 * (lo + hi)) if L == 1
                   else np.linspace(lo + inset, hi - inset, L))
            spread = float(ref[-1] - ref[0])
            window = float(self.theta_hi - self.theta_lo.max())
            alpha  = 0.95 * window / (span + spread + 1e-12)
            center = 0.5 * (float(self.theta_lo.max()) + float(self.theta_hi))
            theta_base = center - alpha * 0.5 * ((hi - ref[0]) + (lo - ref[-1]))
            self.cfg.theta_ref  = ref
            self.cfg.alpha      = float(alpha)
            self.cfg.theta_base = float(theta_base)
        elif self.cfg.theta_ref is None:
            raise ValueError("PrismRouter: auto_scale=False wymaga jawnego theta_ref")

        # --- auto-kalibracja skali argumentu cosinusa ----------------------------
        # cos(x) jest w pobliżu x=0 płaski w drugim rzędzie (1 - x^2/2). Ponieważ
        # osiągalny rozrzut |delta - target| to przy domyślnej geometrii ~0.12 rad,
        # gamma * cos(...) dawało rozrzut score ~0.06 nata — softmax zwracał wtedy
        # niemal jednorodne wagi NIEZALEŻNIE od importance. Normalizujemy argument
        # tak, by pełny osiągalny rozrzut odpowiadał ćwiartce okresu cosinusa.
        if self.cfg.delta_scale is None:
            lo, hi = self.cfg.importance_range
            grid = np.linspace(lo, hi, 65)
            worst = 0.0
            for imp in grid:
                th = np.clip(
                    np.full(self.cfg.num_levels, self.cfg.theta_base)
                    + self.cfg.alpha * (imp - self.cfg.theta_ref),
                    self.theta_lo, self.theta_hi,
                )
                worst = max(worst, float(np.abs(self.deviation_angle(th) - self.target_delta).max()))
            self.delta_scale = max(worst, 1e-6)
        else:
            self.delta_scale = float(self.cfg.delta_scale)

        # --- diagnostyka ostatniego wywołania ------------------------------------
        self.last_theta     = None
        self.last_delta     = None
        self.last_tir_mask  = None
        self.last_clip_mask = None

    def deviation_angle(self, theta: np.ndarray) -> np.ndarray:
        theta = np.asarray(theta, dtype=np.float64)
        phi1  = np.arcsin(np.clip(np.sin(theta) / self.cfg.n, -1.0, 1.0))
        phi2  = self.cfg.A - phi1
        raw   = self.cfg.n * np.sin(phi2)
        # Zachowany clip (bez niego arcsin daje NaN), ale teraz odnotowujemy,
        # kiedy zadziałał — bo wtedy delta = theta + pi/2 - A, czyli funkcja
        # afiniczna: cała trygonometria pryzmatu przestaje cokolwiek liczyć.
        self.last_tir_mask = np.abs(raw) > 1.0
        delta = theta + np.arcsin(np.clip(raw, -1.0, 1.0)) - self.cfg.A
        return delta

    def _prism_shift(self, v: np.ndarray, delta: float) -> np.ndarray:
        v = np.asarray(v)
        fft_v   = np.fft.fft(v.astype(np.complex128))
        freqs   = np.fft.fftfreq(len(v))
        rotator = np.exp(1j * 2.0 * np.pi * freqs * delta)
        shifted = np.fft.ifft(fft_v * rotator).real.astype(np.float32)
        n = np.linalg.norm(shifted)
        return shifted / (n + 1e-8)

    def route(self, importance: float, pattern: np.ndarray):
        theta_raw = (np.full(self.cfg.num_levels, self.cfg.theta_base)
                     + self.cfg.alpha * (importance - self.cfg.theta_ref))
        # KOREKTA: dolna granica clipu to teraz próg TIR danego poziomu,
        # a nie wspólne 0.1. Poniżej 0.1 pryzmat i tak nie działał fizycznie.
        theta = np.clip(theta_raw, self.theta_lo, self.theta_hi)
        self.last_clip_mask = ~np.isclose(theta, theta_raw)
        self.last_theta = theta

        delta = self.deviation_angle(theta)
        self.last_delta = delta

        # Uwaga: cos(delta - target) jest parzysty względem (delta - target),
        # więc odchylenie o +x i -x od targetu daje ten sam score. To jest
        # zachowanie jądra odległościowego i NIE zostało zmienione — zmiana
        # semantyki wymaga Twojej decyzji. Jeśli znak odchylenia ma nieść
        # informację, tu jest miejsce na s = gamma * (cos(...) + kappa * sin(...)).
        # Argument skalowany i przycięty do [-pi/2, pi/2]: poza oknem kalibracji
        # cos zacząłby rosnąć z powrotem (jest okresowy), co odwracałoby ranking.
        x = np.clip((delta - self.target_delta) / self.delta_scale, -1.0, 1.0)
        s = self.cfg.gamma * np.cos(x * (np.pi / 2))
        p = np.exp(s - s.max())
        p = p / (p.sum() + 1e-8)
        p = p + self.cfg.bias
        p[0] *= self.cfg.first_level_damping
        p = p / (p.sum() + 1e-8)

        updates = [p[lv] * self._prism_shift(pattern, delta[lv])
                   for lv in range(self.cfg.num_levels)]
        return updates, p, delta

    def describe(self) -> str:
        """Zwraca opis okna pracy routera — do sanity-checku po zmianie configu."""
        lines = ["PrismRouter — okno pracy:"]
        lo, hi = self.cfg.importance_range
        lines.append(f"  importance_range = [{lo:.2f}, {hi:.2f}]  auto_scale={self.cfg.auto_scale}")
        lines.append(f"  theta_base = {self.cfg.theta_base:.4f}  alpha = {self.cfg.alpha:.4f}  "
                     f"theta_hi = {self.theta_hi:.4f}  delta_scale = {self.delta_scale:.4f}")
        for lv in range(self.cfg.num_levels):
            lines.append(
                f"  L{lv}: A={np.rad2deg(self.cfg.A[lv]):5.1f}deg  n={self.cfg.n[lv]:.3f}  "
                f"theta_TIR={self.theta_min_tir[lv]:.4f}  theta_lo={self.theta_lo[lv]:.4f}  "
                f"theta_ref={self.cfg.theta_ref[lv]:.3f}  target_delta={self.target_delta[lv]:.4f}"
            )
        for imp in np.linspace(lo, hi, 5):
            th = (np.full(self.cfg.num_levels, self.cfg.theta_base)
                  + self.cfg.alpha * (imp - self.cfg.theta_ref))
            clipped = np.clip(th, self.theta_lo, self.theta_hi)
            flag = "CLIP" if not np.allclose(th, clipped) else "ok  "
            lines.append(f"  importance={imp:.2f} -> theta={np.round(th, 4)} [{flag}]")
        return "\n".join(lines)