# -*- coding: utf-8 -*-
"""holon/memory.py — Persystencja pamięci JSON z holograficznym szyfrowaniem

Zmiany względem wersji poprzedniej (nic nie usunięto — tylko korekty i dodatki):

  1. OCHRONA PRZED UTRATĄ PAMIĘCI
     - `save()` NIE nadpisuje pliku głównego, jeśli poprzedni `load()` zawiódł;
       zapisuje wtedy do `*.rescue.json` i zwraca False. Wcześniej jeden błąd
       odczytu kasował całą historię przy najbliższym zamknięciu programu.
     - Rotacja kopii: przed podmianą plik główny idzie do `*.bak.json`.
     - `load()` próbuje kolejno: plik główny -> `.tmp` -> `.bak`. `.tmp` nie jest
       już kasowany na wejściu — po crashu między `write_text` a `replace` to
       właśnie on zawiera najnowsze dane.
     - Awaryjna gałąź `save()` nie pisze już bezpośrednio do pliku głównego
       (nieatomowo); idzie do `*.rescue.json`.

  2. ROZDZIELENIE integrity / coherence  <- ustalone w tej wersji
     Stara `coherence` porównywała dane z nimi samymi (oba ramiona pochodziły
     z tego samego pliku), więc wychodziła 1.000000 zawsze — zmierzone na
     5 różnych `phi`, po długim uczeniu i po zmianie `total_dim`. Odchylała się
     wyłącznie przy fizycznym uszkodzeniu pliku.
       * `integrity`  — TA SAMA liczba, poprawnie nazwana. Dwie niezależne drogi
                        do tego samego stanu: rekonstrukcja z `phi` oraz
                        odszyfrowanie `h_coherence` kotwicą. Zgodność dowodzi,
                        że plik jest spójny i należy do TEJ tożsamości (kotwicy).
                        BRAMKUJE wczytanie `store` — i musi, bo embeddingi są
                        odbindowywane przez `recovered_state`; przy złej kotwicy
                        dekodują się w szum.
       * `coherence`  — NOWA treść: `dot(phi_center(phi_today), state_at_save)`,
                        czyli dryf tożsamości wywołany rozpadem czasowym przez
                        czas nieobecności. Zależy od czegoś SPOZA pliku (upływu
                        realnego czasu), więc niesie informację. Raportowana
                        w `wake_message`, NIE bramkuje niczego — długa przerwa
                        ma budzić refleksję, a nie kasować pamięć.

  3. Walidacja kształtu `phi` PRZED pętlą: liczba poziomów i wymiar w obie
     strony (dotąd obsłużone było tylko powiększenie wymiaru).
  4. `core_level` z konfiguracji zamiast zaszytego `level=2`, zapisywany
     w pliku, żeby stare pliki czytały się swoim własnym poziomem.
  5. Wykrywanie stanu zdegenerowanego (wektor zerowy) — w algebrze HRR zero
     jest anihilatorem: `bind(0, k) = 0` i żaden klucz tego nie odzyska.
  6. Kotwica o wymiarze zapisanym w pliku (`anchor_dim`), z zachowaniem
     zgodności wstecz (brak pola => stare 264).
  7. `_safe_bind` nie tnie już po cichu do `min(...)`: obcięcie przed FFT to
     inna algebra cykliczna, a nie „częściowe" wiązanie — cały `store`
     zapisywałby się nieodwracalnie przekłamany.
  8. Wyjątki rozdzielone zamiast jednego `except Exception` na całości.
"""

import os
import json
import time
import shutil
import hashlib
import numpy as np
from pathlib import Path

from holon_config import Config
from holon_item import Item
from holon_holography import HolographicInterference
from holon_aii import TimeDecay
from holon_embedder import time_embed


class MemoryShapeError(ValueError):
    """Niezgodność kształtu/konfiguracji — odróżniona od uszkodzenia pliku."""


class PersistentMemory:

    LEGACY_ANCHOR_DIM = 264
    DEGENERATE_NORM   = 1e-6

    def __init__(self, path: str = "holon_memory.json", dim: int = 264):
        self.path = Path(path)
        # KOREKTA (7. z listy): ta sama zmienna sterowała dwiema różnymi rzeczami
        # z różnymi wartościami domyślnymi (tu "4242", w holography.py
        # "holon-eriamo-4242"). Dodana osobna nazwa, ze zgodnością wstecz.
        seed_str = (os.environ.get("HOLON_MEMORY_ANCHOR_SEED")
                    or os.environ.get("HOLON_ANCHOR_SEED")
                    or "4242")
        self._seed_str = seed_str
        self._seed_int = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16) % (2**31)
        self.dim = dim
        self.eriamo_anchor = self._anchor(dim)

        # Blokada zapisu po nieudanym odczycie — sedno punktu 1.
        self._load_failed = False
        self._last_error  = None
        self._last_source = None

    # ── Ścieżki pomocnicze ────────────────────────────────────────────────

    @property
    def tmp_path(self) -> Path:
        return self.path.with_suffix(".tmp")

    @property
    def bak_path(self) -> Path:
        return self.path.with_suffix(".bak.json")

    @property
    def rescue_path(self) -> Path:
        return self.path.with_suffix(".rescue.json")

    # ── Kotwica ───────────────────────────────────────────────────────────

    def _anchor(self, d: int) -> np.ndarray:
        """Kotwica tożsamości o zadanym wymiarze.

        Konstrukcja zachowana 1:1 ze starej wersji (randn(d) -> normalizacja),
        żeby istniejące pliki z `anchor_dim == 264` weryfikowały się bez zmian.
        """
        d = int(max(d, 1))
        a = np.random.RandomState(self._seed_int).randn(d).astype(np.float32)
        return a / (np.linalg.norm(a) + 1e-8)

    # ── Init ──────────────────────────────────────────────────────────────

    @staticmethod
    def _init_phi(cfg: Config) -> np.ndarray:
        total = cfg.total_dim
        phi   = np.random.randn(cfg.phi_levels, cfg.k, total).astype(np.float32) * 0.01
        norms = np.linalg.norm(phi, axis=2, keepdims=True)
        return phi / (norms + 1e-8)

    @staticmethod
    def _core_level(cfg: Config) -> int:
        """Poziom rdzenia. Dotąd zaszyte `2`; teraz najgłębszy istniejący."""
        return max(0, int(getattr(cfg, "phi_levels", 3)) - 1)

    @staticmethod
    def _phi_center_static(phi: np.ndarray, level: int = 2) -> np.ndarray:
        if phi.ndim == 3:
            if not (0 <= level < phi.shape[0]):
                raise MemoryShapeError(
                    f"_phi_center_static: poziom {level} poza zakresem "
                    f"(phi ma {phi.shape[0]} poziomów)"
                )
            layer = phi[level]
        else:
            layer = phi
        norms   = np.linalg.norm(layer, axis=1)
        exp_n   = np.exp(norms - norms.max())
        weights = exp_n / (exp_n.sum() + 1e-8)
        center  = sum(weights[k] * layer[k] for k in range(len(layer)))
        n = np.linalg.norm(center)
        # KOREKTA (5.): wektor zerowy jest anihilatorem splotu — `bind(0, k) = 0`
        # i nie ma klucza, który to odbindowuje. Bez tej kontroli cały zapis
        # degenerował się po cichu do zer.
        if n < PersistentMemory.DEGENERATE_NORM:
            raise MemoryShapeError(
                f"_phi_center_static: stan zdegenerowany na poziomie {level} "
                f"(norma {n:.2e}) — wiązanie holograficzne dałoby wektor zerowy"
            )
        return center / (n + 1e-8)

    def _safe_bind(self, emb: np.ndarray, state: np.ndarray) -> list:
        # KOREKTA (7. z nagłówka): dawniej `m = min(len(emb), len(state))` i cicha
        # obcinka. Obcięcie przed FFT to splot w innej algebrze cyklicznej, więc
        # wynik nie jest przybliżeniem — zapisany `store` byłby nieodwracalny.
        if len(emb) != len(state):
            raise MemoryShapeError(
                f"_safe_bind: embedding ma {len(emb)}, stan {len(state)}. "
                f"Niezgodność konfiguracji `total_dim` — zapis przerwany, "
                f"żeby nie utrwalić przekłamanego store."
            )
        return HolographicInterference.bind(emb, state)

    # ── Save ──────────────────────────────────────────────────────────────

    def save(self, phi: np.ndarray, store: list, turns: int, cfg: Config,
             aii: dict = None, stability=None,
             W_time: np.ndarray = None, W_gen: np.ndarray = None,
             force: bool = False) -> bool:
        """Zapisuje stan. Zwraca True przy zapisie do pliku głównego.

        Gdy poprzedni `load()` zawiódł, zapis idzie do `*.rescue.json`
        i zwraca False — plik główny pozostaje nietknięty. To jest ta zmiana,
        która likwiduje ścieżkę trwałej utraty pamięci. `force=True` pozwala
        świadomie nadpisać.
        """
        core_lv = self._core_level(cfg)
        try:
            state_now = PersistentMemory._phi_center_static(phi, level=core_lv)
        except MemoryShapeError as e:
            print(f"[Memory] Zapis przerwany: {e}")
            return False

        anchor = self._anchor(len(state_now))
        try:
            h_coherence = HolographicInterference.bind(state_now, anchor)
            store_ser = [
                {
                    "id":            i.id,
                    "content":       i.content,
                    "embedding":     self._safe_bind(i.emb_np(), state_now),
                    "age":           i.age,
                    "relevance":     i.relevance,
                    "created_at":    i.created_at,
                    "is_insight":    i.is_insight,
                    "insight_level": i.insight_level,
                    "cluster_size":  i.cluster_size,
                    "is_reminder":   i.is_reminder,
                    "is_fact":       i.is_fact,
                    "is_work":       i.is_work,
                    "is_fired":      getattr(i, "is_fired", False),
                }
                # Poprawka zachowana: warunek age >= 0, aby nie tracić danych
                # z ostatniej tury przy wyjściu.
                for i in store if i.age >= 0
            ]
        except (MemoryShapeError, ValueError) as e:
            print(f"[Memory] Zapis przerwany (wiązanie): {e}")
            return False

        data = {
            "timestamp":     time.time(),
            "turns":         turns,
            "phi":           phi.tolist(),
            "phi_stability": stability if stability is not None else [],
            "phase_shifts":  cfg.phase_shifts,
            "h_coherence":   h_coherence,
            "anchor_dim":    int(len(state_now)),
            "core_level":    int(core_lv),
            "phi_levels":    int(phi.shape[0]) if phi.ndim == 3 else 1,
            "total_dim":     int(cfg.total_dim),
            "aii":           aii or {},
            "W_time":        W_time.tolist() if W_time is not None else None,
            "W_gen":         W_gen.tolist()  if W_gen  is not None else None,
            "store":         store_ser,
        }
        payload = json.dumps(data, ensure_ascii=False, indent=2)

        target_main = force or not self._load_failed
        if not target_main:
            try:
                self.rescue_path.write_text(payload, encoding="utf-8")
                print(f"[Memory] Poprzedni odczyt zawiódł ({self._last_error}). "
                      f"Zapisano do {self.rescue_path.name}; plik główny nietknięty. "
                      f"Użyj save(..., force=True), aby nadpisać.")
            except OSError as e:
                print(f"[Memory] Nie udało się zapisać kopii ratunkowej: {e}")
            return False

        try:
            self.tmp_path.write_text(payload, encoding="utf-8")
            if self.path.exists():
                try:
                    shutil.copy2(self.path, self.bak_path)
                except OSError as e:
                    print(f"[Memory] Ostrzeżenie: kopia zapasowa nieudana: {e}")
            self.tmp_path.replace(self.path)
            return True
        except OSError as e:
            # KOREKTA (1.): dawniej ta gałąź pisała NIEATOMOWO wprost do pliku
            # głównego — przy drugim błędzie zostawał plik uszkodzony i skasowany
            # .tmp. Teraz oryginał pozostaje nietknięty.
            print(f"[Memory] Błąd zapisu atomowego: {e}")
            try:
                self.rescue_path.write_text(payload, encoding="utf-8")
                print(f"[Memory] Stan zapisany do {self.rescue_path.name}.")
            except OSError as e2:
                print(f"[Memory] Kopia ratunkowa również nieudana: {e2}")
            return False

    # ── Load ──────────────────────────────────────────────────────────────

    def _empty(self, cfg: Config) -> dict:
        return {
            "phi": self._init_phi(cfg), "store": [], "turns": 0,
            "delta_hours": 0.0, "aii": {}, "phi_stability": None,
            "loaded": False, "coherence": 1.0, "integrity": 1.0,
            "wake": "", "W_time": None, "W_gen": None,
            "source": None, "load_failed": self._load_failed,
            "error": self._last_error,
        }

    def _candidates(self) -> list:
        # KOREKTA (1.): `.tmp` NIE jest już kasowany na wejściu — po crashu
        # między zapisem a podmianą to on trzyma najświeższe dane.
        out = []
        for p in (self.path, self.tmp_path, self.bak_path):
            if p.exists() and p.stat().st_size > 0:
                out.append(p)
        return out

    def load(self, cfg: Config) -> dict:
        self._load_failed = False
        self._last_error  = None
        self._last_source = None

        cands = self._candidates()
        if not cands:
            return self._empty(cfg)

        errors = []
        for src in cands:
            try:
                raw = json.loads(src.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
                errors.append(f"{src.name}: nieczytelny ({e})")
                continue
            try:
                result = self._parse(raw, cfg)
                result["source"] = src.name
                self._last_source = src.name
                if src != self.path:
                    print(f"[Memory] Odczyt z {src.name} (plik główny niedostępny "
                          f"lub uszkodzony).")
                return result
            except MemoryShapeError as e:
                errors.append(f"{src.name}: niezgodność kształtu ({e})")
            except (KeyError, TypeError, ValueError) as e:
                errors.append(f"{src.name}: uszkodzone dane ({e})")

        # Żaden kandydat nie wypalił: pamięć pusta, ale ZAPIS ZABLOKOWANY.
        self._load_failed = True
        self._last_error  = "; ".join(errors)
        print(f"[Memory] Błąd wczytania: {self._last_error}")
        print(f"[Memory] Zapis do {self.path.name} zablokowany do końca sesji "
              f"— dane nie zostaną nadpisane.")
        return self._empty(cfg)

    # ── Parsowanie jednego kandydata ──────────────────────────────────────

    @staticmethod
    def _fit_phi(phi_raw: np.ndarray, cfg: Config) -> np.ndarray:
        """Dopasowanie kształtu `phi` do konfiguracji — w OBIE strony."""
        total_dim = cfg.total_dim
        levels    = int(getattr(cfg, "phi_levels", 3))

        if phi_raw.ndim == 2:
            phi_raw = np.stack([phi_raw.copy() * (1.0 - 0.05 * l)
                                for l in range(levels)])
        if phi_raw.ndim != 3:
            raise MemoryShapeError(f"phi ma {phi_raw.ndim} wymiarów, oczekiwano 2 lub 3")

        # KOREKTA (3.): liczba poziomów. Dotąd nieobsłużone — przy wzroście
        # `phi_levels` leciał IndexError w pętli, przy spadku część poziomów
        # zostawała wyzerowana przez `np.zeros_like` i cicho anihilowała bind.
        have = phi_raw.shape[0]
        if have < levels:
            extra = [phi_raw[-1].copy() * (1.0 - 0.05 * (l - have + 1))
                     for l in range(have, levels)]
            phi_raw = np.concatenate([phi_raw, np.stack(extra)], axis=0)
        elif have > levels:
            phi_raw = phi_raw[:levels]

        # Wymiar — dotąd obsłużone tylko powiększenie.
        if phi_raw.shape[2] < total_dim:
            pad = np.zeros((*phi_raw.shape[:2], total_dim - phi_raw.shape[2]),
                           dtype=np.float32)
            phi_raw = np.concatenate([phi_raw, pad], axis=2)
        elif phi_raw.shape[2] > total_dim:
            phi_raw = phi_raw[:, :, :total_dim]

        norms   = np.linalg.norm(phi_raw, axis=2, keepdims=True)
        phi_raw = phi_raw / (norms + 1e-8)
        return phi_raw.astype(np.float32)

    @staticmethod
    def _decay_coherence(phi_before: np.ndarray, phi_after: np.ndarray,
                         core_lv: int) -> float:
        """Dryf tożsamości przez czas nieobecności, w [0, 1].

        Iloczyn dwóch niezależnych składników:
          * obrót — cosinus między centrum rdzenia przed i po rozpadzie;
            zeruje się przy przekręceniu tożsamości, ale przy jednorodnym
            skalowaniu wszystkich wierszy zostaje 1.0 (stąd drugi składnik),
          * retencja — stosunek średnich norm; podąża za `phi_half_life_hours`
            niezależnie od tego, jak `evolve_phi` traktuje kierunki.
        """
        try:
            c_b = PersistentMemory._phi_center_static(phi_before, level=core_lv)
            c_a = PersistentMemory._phi_center_static(phi_after,  level=core_lv)
            rot = float(np.dot(c_a, c_b))
        except MemoryShapeError:
            return 0.0
        n_b = float(np.linalg.norm(phi_before, axis=-1).mean())
        n_a = float(np.linalg.norm(phi_after,  axis=-1).mean())
        ret = n_a / (n_b + 1e-8)
        return float(np.clip(rot, 0.0, 1.0) * np.clip(ret, 0.0, 1.0))

    def _parse(self, data: dict, cfg: Config) -> dict:
        saved_at    = float(data["timestamp"])
        delta_hours = (time.time() - saved_at) / 3600.0
        turns       = int(data["turns"])
        total_dim   = cfg.total_dim

        if "phase_shifts" in data:
            cfg.phase_shifts = data["phase_shifts"]

        phi_raw_orig = np.array(data["phi"], dtype=np.float32)
        dim_changed  = (phi_raw_orig.ndim == 3 and phi_raw_orig.shape[2] != total_dim)
        phi_raw      = self._fit_phi(phi_raw_orig, cfg)

        # Poziom rdzenia: z pliku (zgodność wstecz), przycięty do zakresu.
        core_lv = int(data.get("core_level", 2))
        core_lv = min(max(core_lv, 0), phi_raw.shape[0] - 1)

        state_at_save = PersistentMemory._phi_center_static(phi_raw, level=core_lv)
        h_coherence   = data.get("h_coherence")

        # ── INTEGRITY ────────────────────────────────────────────────────
        # Dwie niezależne drogi do tego samego stanu. Zgodność dowodzi
        # nienaruszonego pliku i właściwej tożsamości (kotwicy).
        if h_coherence is None:
            integrity       = 1.0
            recovered_state = state_at_save
        else:
            h_arr      = np.array(h_coherence, dtype=np.float32)
            anchor_dim = int(data.get("anchor_dim", self.LEGACY_ANCHOR_DIM))
            anchor     = self._anchor(anchor_dim)
            use_dim    = min(len(h_arr), len(anchor))
            recovered_state = HolographicInterference.unbind(
                h_arr[:use_dim].tolist(), anchor[:use_dim], strict=False)

            s_dim = len(state_at_save)
            if len(recovered_state) < s_dim:
                pad = np.zeros(s_dim - len(recovered_state), dtype=np.float32)
                recovered_state = np.concatenate([recovered_state, pad])
            elif len(recovered_state) > s_dim:
                recovered_state = recovered_state[:s_dim]
            recovered_state = recovered_state / (np.linalg.norm(recovered_state) + 1e-8)
            integrity = float(np.dot(recovered_state, state_at_save))

        # Zmiana `total_dim` przesuwa oba ramiona zgodnie, więc integrity
        # zostaje ~1.0 — ale embeddingi w `store` są w starym wymiarze.
        # Odnotowujemy to jawnie, zamiast pozwalać na cichy rozjazd.
        if dim_changed:
            print(f"[Memory] Uwaga: total_dim zmieniony "
                  f"({phi_raw_orig.shape[2]} -> {total_dim}); "
                  f"embeddingi store zostaną dopasowane przy odczycie.")

        # ── Rozpad czasowy ───────────────────────────────────────────────
        phi_today = np.zeros_like(phi_raw)
        for lv in range(phi_raw.shape[0]):
            phi_today[lv] = TimeDecay.evolve_phi(
                phi_raw[lv], delta_hours,
                cfg.phi_half_life_hours, cfg.phi_min_norm, level=lv)

        # ── COHERENCE (nowa treść) ───────────────────────────────────────
        # Dryf tożsamości wywołany upływem realnego czasu — jedyna wielkość
        # w tym pliku zależna od czegoś SPOZA zapisanych danych.
        #
        # UWAGA: sam cosinus kierunku NIE wystarcza. Jeśli `evolve_phi` skaluje
        # wszystkie wiersze jednakowo, kierunek centrum się nie zmienia i cosinus
        # wychodzi 1.000000 zawsze — czyli dokładnie ta sama pułapka, co
        # w starej `coherence`. Zmierzone. Dlatego miara jest iloczynem dwóch
        # składników: obrotu tożsamości ORAZ retencji normy (to drugie rusza się
        # zgodnie z `phi_half_life_hours` i nie zależy od tego, czy `evolve_phi`
        # renormalizuje wiersze).
        coherence = self._decay_coherence(phi_raw, phi_today, core_lv)

        # ── Store — bramkowany przez INTEGRITY, nie przez dryf ───────────
        # Epizody (zwykłe) starzeją się i wypadają po store_decay_hours.
        # Typy trwałe (fact / work / insight / reminder) przeżywają przerwę —
        # inaczej po wakacjach agent budzi się bez użytecznego kontekstu
        # mimo integrity=1.0 (zmierzony failure mode: 34→0 po 112 dniach).
        store = []
        if integrity >= cfg.coherence_threshold:
            max_age = cfg.store_decay_hours * 4
            work_max = float(getattr(cfg, "work_decay_hours", 2160.0)) * 4
            age_cap  = int(getattr(cfg, "durable_age_cap", 48))
            keep_f   = bool(getattr(cfg, "keep_facts_forever", True))
            keep_w   = bool(getattr(cfg, "keep_work_forever", True))
            for obj in data.get("store", []):
                age_now = obj["age"] + int(delta_hours * 4)
                is_fact    = bool(obj.get("is_fact", False))
                is_work    = bool(obj.get("is_work", False))
                is_insight = bool(obj.get("is_insight", False))
                is_rem     = bool(obj.get("is_reminder", False))
                durable = is_insight or is_rem or (is_fact and keep_f) or (is_work and keep_w)
                if not durable and is_work and age_now > work_max:
                    continue
                if not durable and not is_work and age_now > max_age:
                    continue
                if durable:
                    age_now = min(age_now, age_cap)

                emb_arr = np.array(obj["embedding"], dtype=np.float32)
                use_dim = min(len(emb_arr), len(recovered_state))
                rec_emb = HolographicInterference.unbind(
                    emb_arr[:use_dim].tolist(), recovered_state[:use_dim],
                    strict=False)
                raw_emb = rec_emb.tolist()

                if len(raw_emb) < total_dim:
                    created = obj.get("created_at", time.time())
                    t_vec   = time_embed(created, total_dim - len(raw_emb)).tolist()
                    raw_emb = raw_emb + t_vec
                    v       = np.array(raw_emb, dtype=np.float32)
                    raw_emb = (v / (np.linalg.norm(v) + 1e-8)).tolist()
                elif len(raw_emb) > total_dim:
                    v       = np.array(raw_emb[:total_dim], dtype=np.float32)
                    raw_emb = (v / (np.linalg.norm(v) + 1e-8)).tolist()

                item = Item(
                    id=obj["id"], content=obj["content"], embedding=raw_emb,
                    age=age_now, recalled=False,
                    relevance=obj.get("relevance", 1.0),
                    created_at=obj.get("created_at", time.time()),
                    is_insight=obj.get("is_insight", False),
                    insight_level=obj.get("insight_level", -1),
                    cluster_size=obj.get("cluster_size", 1),
                    is_reminder=obj.get("is_reminder", False),
                    is_fact=obj.get("is_fact", False),
                    is_work=obj.get("is_work", False))

                if "is_fired" in obj:
                    setattr(item, "is_fired", obj["is_fired"])
                store.append(item)
        else:
            print(f"[Memory] Integralność {integrity:.3f} poniżej progu "
                  f"{cfg.coherence_threshold} — store pominięty "
                  f"(embeddingi odbindowałyby się w szum).")

        return {
            "phi":           phi_today,
            "store":         store,
            "turns":         turns,
            "delta_hours":   delta_hours,
            "aii":           data.get("aii", {}),
            "phi_stability": data.get("phi_stability"),
            "wake": TimeDecay.wake_message(
                delta_hours, turns, len(store), coherence),
            "loaded":      True,
            "coherence":   coherence,
            "integrity":   integrity,
            "load_failed": False,
            "error":       None,
            "W_time": np.array(data["W_time"], dtype=np.float32)
                      if data.get("W_time") else None,
            "W_gen":  np.array(data["W_gen"],  dtype=np.float32)
                      if data.get("W_gen")  else None,
        }

    # ── Delete ────────────────────────────────────────────────────────────

    def delete(self, include_backups: bool = False):
        if self.path.exists():
            self.path.unlink()
        if include_backups:
            for p in (self.tmp_path, self.bak_path, self.rescue_path):
                if p.exists():
                    p.unlink()