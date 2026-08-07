# -*- coding: utf-8 -*-
"""holon_agent_memory.py — cienki adapter pamięci Holona pod agenta kodowego (Grok/CLI).

Holon **v5.13** — Plan B + B10 handoff projection (hybrid since, anchors/chronicle,
close, recommended_actions, suggested_mneme, last-project).

Use-case: Holon-as-memory (ciągłość SE), NIE kanon czatu EriAmo.
Profil: zawsze ``Config.agent()`` (jawny; chat = ``Config.chat()`` w Session).

Kontrakt: ``MemoryAPI`` (remember / recall / digest / save) — patrz holon_memory_api.py.

  python holon_agent_memory.py digest
  python holon_agent_memory.py remember --fact "..."
  python holon_agent_memory.py remember --work "..."
  python holon_agent_memory.py close --work "..." --fact "..." --project P
  python holon_agent_memory.py recall "query"
  python holon_agent_memory.py seed
  python holon_agent_memory.py stats
  python holon_agent_memory.py crystallize [--dry-run] [--project P]
  python holon_agent_memory.py eval

Użycie z kodu:
  from holon_memory_api import open_memory
  am = open_memory()          # profile=agent
  print(am.digest())
  am.remember("Preferencja: ...", kind="fact")
  am.save()
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

from holon_config import Config
from holon_embedder import Embedder
from holon_holomem import HoloMem
from holon_item import Item
from holon_lexindex import LexicalIndex


# Domyślne kotwice pod pracę Grok Build — seed idempotentny po treści.
AGENT_SEED: Tuple[Tuple[str, str], ...] = (
    ("fact",
     "Partner użytkownika: Maciek (EriAmo). Komunikacja po polsku, partnersko. "
     "Holon = pamięć SE; KarmazynOs = osobny monorepo runtime (nie fork Holona)."),
    ("fact",
     "Agent CLI: Grok (xAI). OBOWIĄZKOWY start: `cd C:\\Users\\drwis\\Karmin_Ae` "
     "&& `python agent_boot.py` (lub agent_boot.cmd). Potem Mneme-L / remember. "
     "Nie chwal cudzych memory SaaS — tu jest własny stack SE."),
    ("fact",
     "[Holon] Pamięć: Config.agent() + holon_memory.json. Kontrakt MemoryAPI: "
     "remember/recall/digest/save (holon_memory_api). Profile: agent|chat|flat. "
     "Ewal: `python holon_agent_memory.py eval`. Docs: docs/ + AGENTS.md."),
    ("fact",
     "[Holon] LLM slot (opcjonalny): holon_llm.register_local_model_factory / "
     "HOLON_LLM_BASE_URL (OpenAI-compatible). Pamięć działa bez LLM."),
    ("fact",
     "[Holon] Kluczowe pliki: holon_agent_memory.py, holon_memory_api.py, holon_config.py, "
     "holon_holomem.py, holon_memory.py, holon_prompts.py, holon_llm.py, docs/."),
    ("fact",
     "Konwencja multi-projekt: prefiks treści `[Holon]` / `[Karmazyn]` w fact|work; "
     "handoff --project filtruje. set-work demotuje stare work → fact."),
    ("fact",
     "Marker-agent-holon-v2: handoff + golden eval + MemoryAPI (2026-07). "
     "Testy: unittest tests + `python holon_agent_memory.py eval`."),
    ("work",
     "[Holon] Utrzymywać: handoff na start, eval zielony, docs/ zgodne z kodem; "
     "nie puchnąć work — set-work / jeden aktywny wątek na projekt."),
    ("work",
     "[Karmazyn] Aktywny runtime SE: C:/Users/drwis/KarmazynOs (github Maciej-EriAmo/KarmazynOs). "
     "Holon tylko pamięć. Następne Karmazyn: wg Documents/rust_roadmap_tech (po R5)."),
)


class AgentMemory:
    """Odczyt/zapis store Holona pod kątem agenta SE, bez LLM."""

    def __init__(self, holomem: HoloMem, memory_path: str = "holon_memory.json"):
        self.hm = holomem
        self.memory_path = memory_path
        self._started = False
        # B2 lexical index
        min_tok = int(getattr(holomem.cfg, "hybrid_min_token_len", 3))
        self.lex_index = LexicalIndex(min_token_len=min_tok)
        holomem.lex_index = self.lex_index  # type: ignore[attr-defined]
        # B4 on_remember hooks: cb(item, *, kind, action, memory)
        self._remember_hooks: List[Callable] = []

    @classmethod
    def open(
        cls,
        memory_path: str = "holon_memory.json",
        kurz_path: Optional[str] = None,
        profile: str = "agent",
        cfg: Optional[Config] = None,
        *,
        use_settings: bool = True,
    ) -> "AgentMemory":
        # ścieżka z settings, gdy caller zostawił default
        if use_settings and memory_path in ("", "holon_memory.json"):
            try:
                from holon_settings import resolve_memory_path

                memory_path = resolve_memory_path(cli_path=None)
            except Exception:
                memory_path = memory_path or "holon_memory.json"
        if cfg is None:
            if use_settings:
                try:
                    cfg = Config.from_settings(profile=profile or "agent")
                except Exception:
                    cfg = None
            if cfg is None:
                p = (profile or "agent").strip().lower()
                if p == "chat":
                    cfg = Config.chat()
                elif p == "flat":
                    cfg = Config.flat(base="agent")
                else:
                    cfg = Config.agent()
        kurz = kurz_path or memory_path.replace(".json", "_kurz.json")
        emb = Embedder(dim=cfg.dim, dict_path=kurz, time_dim=cfg.time_dim)
        hm = HoloMem(emb, cfg, memory_path)
        am = cls(hm, memory_path)
        am.start()
        return am

    def start(self) -> dict:
        res = self.hm.start_session()
        self._started = True
        try:
            self.lex_index.rebuild(self.hm.store)
        except Exception:
            self.lex_index.mark_dirty()
        return res

    # ── B4 hooks ──────────────────────────────────────────────────────────

    def on_remember(self, callback: Optional[Callable] = None):
        """Zarejestruj hook po ``remember`` (B4).

        Użycie::

            am.on_remember(lambda item, **kw: print(item.content))

            @am.on_remember
            def _log(item, **kw): ...
        """
        if callback is None:
            def _decorator(fn: Callable) -> Callable:
                self._remember_hooks.append(fn)
                return fn
            return _decorator
        self._remember_hooks.append(callback)
        return callback

    def clear_remember_hooks(self) -> None:
        self._remember_hooks.clear()

    def _fire_remember(
        self, item: Item, *, kind: str, action: str
    ) -> None:
        for h in list(self._remember_hooks):
            try:
                h(item, kind=kind, action=action, memory=self)
            except Exception:
                pass

    def _lex_should_prune(self) -> bool:
        cfg = self.hm.cfg
        n = len(self.hm.store)
        force = bool(getattr(cfg, "lexical_index_force", False))
        thr = int(getattr(cfg, "lexical_index_min_store", 500))
        return force or n >= thr

    def _recall_pool(self, query: str) -> List[Item]:
        """B2: pełny store albo kandydaci z inverted index."""
        store = self.hm.store
        if not store:
            return []
        if not self._lex_should_prune():
            return store
        max_c = int(getattr(self.hm.cfg, "lexical_index_max_candidates", 256))
        try:
            self.lex_index.ensure(store)
            return self.lex_index.candidates(
                query, store, always_durable=True, max_candidates=max_c
            )
        except Exception:
            return store

    # ── Zapis / odczyt ────────────────────────────────────────────────────

    def remember(self, content: str, kind: str = "fact",
                 relevance: float = 1.5) -> Item:
        """Dodaje lub sematycznie scala wpis. kind: fact | work | note."""
        if not self._started:
            self.start()
        content = (content or "").strip()
        if not content:
            raise ValueError("pusta treść")
        kind = kind.lower().strip()
        is_fact = kind in ("fact", "f", "fakt")
        is_work = kind in ("work", "w", "projekt", "task")
        # note = epizod, ale z podbitym relevance; i tak wygasa

        emb = self.hm.embedder.encode(content, timestamp=time.time())
        best = None
        merge_thr = float(getattr(self.hm.cfg, "remember_merge_sim", 0.88))
        # 1) exact / prefix — KuRz często nie scala tego samego tekstu (sim≪0.9)
        c_norm = content[:800].strip().lower()
        for it in self.hm.store:
            ic = (it.content or "").strip().lower()
            if ic == c_norm or (len(c_norm) > 40 and (ic.startswith(c_norm[:80])
                                                      or c_norm.startswith(ic[:80]))):
                best = it
                break
        if best is None and self.hm.store:
            best_sim, cand = self.hm._find_best_match(emb)
            if cand is not None and best_sim > merge_thr:
                best = cand
        if best is not None:
            self.hm._semantic_merge(best, emb)
            if len(content) >= len(best.content):
                best.content = content[:800]
            best.is_fact = best.is_fact or is_fact
            best.is_work = best.is_work or is_work
            best.relevance = max(best.relevance, relevance)
            best.age = 0
            try:
                self.lex_index.update_item(best)
            except Exception:
                self.lex_index.mark_dirty()
            self._fire_remember(best, kind=kind, action="merge")
            return best

        item = Item(
            id=str(uuid.uuid4()),
            content=content[:800],
            embedding=emb.tolist(),
            age=0,
            relevance=relevance,
            is_fact=is_fact,
            is_work=is_work,
        )
        self.hm.store.append(item)
        # Lekka aktualizacja Φ wokół nowego faktu (bez pełnej tury chat)
        try:
            self.hm._update_phi([item])
        except Exception:
            pass
        try:
            self.lex_index.add_item(item)
        except Exception:
            self.lex_index.mark_dirty()
        self._fire_remember(item, kind=kind, action="add")
        return item

    def recall(self, query: str, top_k: int = 8) -> List[Tuple[float, Item]]:
        """Hybryda zgodna z HoloMem: cosine + lexical (cfg.hybrid_lexical_weight).

        B2: przy dużym store scoring na kandydatach z inverted index.
        """
        if not self._started:
            self.start()
        q = self.hm.embedder.encode(query, timestamp=time.time())
        cdim = self.hm.cfg.dim
        q_c = q[:cdim]
        lex_w = float(getattr(self.hm.cfg, "hybrid_lexical_weight", 0.18))
        pool = self._recall_pool(query)
        scored: List[Tuple[float, Item]] = []
        for item in pool:
            e = item.emb_content(cdim)
            s = self.hm._cosine_sim(e, q_c)
            s += lex_w * self.hm._lexical_overlap(query, item.content)
            if item.is_work:
                s += 0.08
            if item.is_fact:
                s += 0.05
            if item.is_insight:
                s += 0.04
            s *= 1.0 / (1.0 + 0.01 * min(item.age, 64))
            scored.append((s, item))
        scored.sort(key=lambda x: -x[0])
        return scored[:top_k]

    @staticmethod
    def _past_label(created_at: float) -> str:
        from holon_aii import TimeDecay
        if not created_at:
            return "?"
        dh = max(0.0, (time.time() - float(created_at)) / 3600.0)
        return TimeDecay.format_pastness(dh)

    def _match_project(self, content: str, project: str) -> bool:
        if not project:
            return True
        c = (content or "").lower()
        p = project.lower().strip()
        if f"[{p}]" in c:
            return True
        # aliasy
        aliases = {
            "karmazyn": ("karmazyn", "kentry", "slab", "karmazynos"),
            "holon": ("holon", "eriamo", "agent memory", "memoryapi"),
        }
        for key, words in aliases.items():
            if p == key or p in words:
                return any(w in c for w in words)
        return p in c

    def digest(self, max_facts: int = 12, max_work: int = 8,
               max_recent: int = 6, project: str = "") -> str:
        """Tekst pod wklejenie w kontekst agenta — niski szum, wysoki sygnał.

        Healthy temporal: pastness (kiedy), oś czasu, wake po przerwie —
        wspomnienia jako PRZESZŁOŚĆ z dystansem, nie wieczne teraz.
        ``project`` — filtr (np. Holon, Karmazyn).
        """
        if not self._started:
            self.start()
        s = self.hm.stats()
        aii = s.get("aii", {})
        lines = [
            "=== HOLON AGENT DIGEST ===",
            f"profile={getattr(self.hm.cfg, 'profile', '?')} "
            f"turns={s.get('turns')} store={s.get('store')} "
            f"delta_h={s.get('delta_hours')} "
            f"aii={aii.get('emotion')}/focus={aii.get('focus')} "
            f"vac={aii.get('vacuum_signal', 0):+.2f}",
        ]
        if project:
            lines.append(f"project_filter={project}")
        wake = getattr(self.hm, "_last_wake", "") or ""
        if wake:
            lines.append(wake)
        elif float(s.get("delta_hours") or 0) >= 0.1:
            from holon_aii import TimeDecay
            lines.append(TimeDecay.wake_message(
                float(s["delta_hours"]), int(s.get("turns") or 0),
                int(s.get("store") or 0),
                float(getattr(self.hm, "_last_coherence", 1.0))))
        n_fact = sum(1 for i in self.hm.store if i.is_fact)
        n_work = sum(1 for i in self.hm.store if i.is_work)
        n_ins = sum(1 for i in self.hm.store if i.is_insight)
        lines.append(f"durable: facts={n_fact} work={n_work} insights={n_ins}")
        lines.append("")

        work = [i for i in self.hm.store
                if i.is_work and self._match_project(i.content, project)]
        work.sort(key=lambda x: (-(x.created_at or 0), x.age))
        if work:
            lines.append("AKTYWNE PROJEKTY / WORK:")
            for i in work[:max_work]:
                when = self._past_label(i.created_at)
                lines.append(f"  • [{when}] {i.content[:400]}")
            lines.append("")

        facts = [i for i in self.hm.store
                 if i.is_fact and not i.is_work
                 and self._match_project(i.content, project)]
        facts.sort(key=lambda x: (-(x.created_at or 0), x.age))
        if facts:
            lines.append("TRWAŁE FAKTY (z datą — to było wtedy, nie „wieczne teraz”):")
            for i in facts[:max_facts]:
                when = self._past_label(i.created_at)
                lines.append(f"  • [{when}] {i.content[:300]}")
            lines.append("")

        # Oś czasu: konkretne ślady w kolejności kalendarzowej (zdrowa sekwencja)
        n_tl = int(getattr(self.hm.cfg, "digest_timeline_items", 8))
        timeline = sorted(
            [i for i in self.hm.store
             if i.created_at and self._match_project(i.content, project)],
            key=lambda x: x.created_at,
        )
        if timeline and n_tl > 0:
            lines.append("OŚ CZASU (od starszych → nowszych, fragment):")
            # pokaż ogon najnowszych z zachowaniem kolejności
            for i in timeline[-n_tl:]:
                flags = []
                if i.is_fact:
                    flags.append("F")
                if i.is_work:
                    flags.append("W")
                tag = "".join(flags) or "E"
                when = self._past_label(i.created_at)
                lines.append(f"  · {when} [{tag}] {i.content[:160]}")
            lines.append("")

        recent = [i for i in self.hm.store
                  if not i.is_fact and not i.is_work and not i.is_reminder
                  and self._match_project(i.content, project)]
        recent.sort(key=lambda x: x.age)
        if recent:
            lines.append("OSTATNIE EPIZODY (mogą wygasnąć):")
            for i in recent[:max_recent]:
                when = self._past_label(i.created_at)
                lines.append(f"  • [{when}|age={i.age}] {i.content[:220]}")
            lines.append("")

        if not work and not facts:
            lines.append("(brak trwałego kontekstu — uruchom: "
                         "python holon_agent_memory.py seed)")
        lines.append("=== END DIGEST ===")
        return "\n".join(lines)

    def seed(self, entries: Sequence[Tuple[str, str]] = AGENT_SEED,
             force: bool = False) -> int:
        """Idempotentnie dodaje kotwice agenta. Zwraca liczbę nowych wpisów."""
        if not self._started:
            self.start()
        added = 0
        for kind, text in entries:
            # pomiń jeśli bardzo podobna treść już jest
            emb = self.hm.embedder.encode(text, timestamp=time.time())
            if self.hm.store and not force:
                best_sim, _ = self.hm._find_best_match(emb)
                if best_sim > 0.90:
                    # i tak odśwież flagi kind
                    self.remember(text, kind=kind)
                    continue
            self.remember(text, kind=kind)
            added += 1
        return added

    def save(self) -> bool:
        if not self._started or self.hm.phi is None:
            return False
        ok = self.hm.memory.save(
            self.hm.phi, self.hm.store, self.hm.turns, self.hm.cfg,
            self.hm.aii.to_dict(), self.hm.phi_stability.tolist(),
            self.hm.W_time, self.hm.W_gen)
        if ok:
            try:
                self.hm.embedder.save()
            except Exception:
                pass
        return ok

    def stats(self) -> dict:
        if not self._started:
            self.start()
        base = self.hm.stats()
        base["profile"] = getattr(self.hm.cfg, "profile", "agent")
        base["facts"] = sum(1 for i in self.hm.store if i.is_fact)
        base["work"] = sum(1 for i in self.hm.store if i.is_work)
        base["insights"] = sum(1 for i in self.hm.store if i.is_insight)
        base["episodic"] = sum(
            1 for i in self.hm.store
            if not i.is_fact and not i.is_work and not i.is_insight
            and not i.is_reminder)
        try:
            base["lex_index"] = self.lex_index.stats()
            base["lex_index_active"] = self._lex_should_prune()
        except Exception:
            pass
        base["remember_hooks"] = len(self._remember_hooks)
        return base

    def set_work(self, content: str, project: str = "",
                 max_active: Optional[int] = None) -> Item:
        """Ustaw aktywne work; nadmiar work (ten sam projekt) → fact (historia).

        Prefiks ``[Project]`` dodawany gdy ``project`` podany i brak w treści.
        Domyślnie ``max_active=1`` (Config.set_work_max_active) — jeden wątek.
        """
        content = (content or "").strip()
        if not content:
            raise ValueError("pusta treść")
        proj = (project or "").strip()
        if proj and f"[{proj}]" not in content and f"[{proj.lower()}]" not in content.lower():
            content = f"[{proj}] {content}"
        if max_active is None:
            max_active = int(getattr(self.hm.cfg, "set_work_max_active", 1))
        max_active = max(1, int(max_active))
        item = self.remember(content, kind="work", relevance=1.6)
        works = [i for i in self.hm.store if i.is_work]
        if proj:
            works = [w for w in works if self._match_project(w.content, proj)]
        works.sort(key=lambda x: -(x.created_at or 0))
        for w in works[max_active:]:
            if w is item:
                continue
            w.is_work = False
            w.is_fact = True  # historia projektu zostaje durable
        if proj:
            self.touch_last_project(proj)
        return item

    # ── B10: last-project + close sesji ───────────────────────────────────

    def meta_path(self) -> Path:
        """``holon_memory.meta.json`` obok store (last_project, nie w gicie)."""
        p = Path(self.memory_path)
        return p.with_name(p.stem + ".meta.json")

    def touch_last_project(self, project: str) -> None:
        """Zapisz ostatni projekt (dla boot bez --project)."""
        proj = (project or "").strip()
        if not proj:
            return
        path = self.meta_path()
        data = {"last_project": proj, "updated_at": time.time()}
        try:
            if path.is_file():
                old = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(old, dict):
                    old.update(data)
                    data = old
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def read_last_project(self) -> str:
        """Odczyt last_project: env → meta → ``holon_settings.json``."""
        env = (os.environ.get("HOLON_DEFAULT_PROJECT") or "").strip()
        if env:
            return env
        try:
            path = self.meta_path()
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    lp = str(data.get("last_project") or "").strip()
                    if lp:
                        return lp
        except Exception:
            pass
        try:
            from holon_settings import load_settings

            sp = str(load_settings().get("default_project") or "").strip()
            if sp:
                return sp
        except Exception:
            pass
        return ""

    def close(
        self,
        *,
        work: str = "",
        fact: str = "",
        project: str = "",
        max_active: Optional[int] = None,
        save: bool = True,
    ) -> dict:
        """B10: domknięcie sesji — atomowo 1 work + 1 fact summary.

        ``set-work`` (max_active domyślnie 1) + ``remember --fact`` + opcjonalny save.
        """
        if not self._started:
            self.start()
        proj = (project or "").strip()
        report: dict = {
            "ok": True,
            "op": "close",
            "project": proj or None,
            "work_id": None,
            "fact_id": None,
            "saved": False,
        }
        w = (work or "").strip()
        f = (fact or "").strip()
        if not w and not f:
            raise ValueError("close: podaj --work i/lub --fact")
        if w:
            item_w = self.set_work(w, project=proj, max_active=max_active)
            report["work_id"] = item_w.id
            report["work"] = (item_w.content or "")[:200]
        if f:
            if proj and f"[{proj}]" not in f and f"[{proj.lower()}]" not in f.lower():
                f = f"[{proj}] {f}"
            item_f = self.remember(f, kind="fact", relevance=1.55)
            report["fact_id"] = item_f.id
            report["fact"] = (item_f.content or "")[:200]
            if proj:
                self.touch_last_project(proj)
        if save:
            report["saved"] = bool(self.save())
        return report

    # ── Krystalizacja (B9) — utrwalanie stałych ścieżek pamięci ──────────

    @staticmethod
    def _is_durable_item(item: Item) -> bool:
        return bool(
            item.is_fact or item.is_work or item.is_insight or item.is_reminder
        )

    def _path_similarity(self, a: Item, b: Item) -> float:
        """Podobieństwo ścieżek: cosine content + lexical (pod SE / KuRz)."""
        cdim = self.hm.cfg.dim
        ea, eb = a.emb_content(cdim), b.emb_content(cdim)
        s = float(self.hm._cosine_sim(ea, eb))
        lex_w = float(getattr(self.hm.cfg, "hybrid_lexical_weight", 0.18))
        s += lex_w * self.hm._lexical_overlap(a.content or "", b.content or "")
        ca = (a.content or "").strip().lower()
        cb = (b.content or "").strip().lower()
        if ca and cb and (ca == cb or ca[:80] == cb[:80]):
            s = max(s, 0.99)
        return s

    def _crystal_survivor(self, a: Item, b: Item) -> Tuple[Item, Item]:
        """Wybierz ocalałą ścieżkę (survivor, donor). Preferuj durable / cluster / treść."""
        def score(it: Item) -> tuple:
            return (
                1 if self._is_durable_item(it) else 0,
                1 if it.is_fact else 0,
                int(it.cluster_size or 1),
                float(it.relevance or 0),
                len(it.content or ""),
            )
        if score(a) >= score(b):
            return a, b
        return b, a

    def _crystal_merge_into(self, survivor: Item, donor: Item) -> None:
        """Scal donor → survivor: emb, flagi, cluster; created_at = początek ścieżki."""
        cdim = self.hm.cfg.dim
        cs = max(1, int(survivor.cluster_size or 1))
        cd = max(1, int(donor.cluster_size or 1))
        s_c = survivor.emb_content(cdim)
        d_c = donor.emb_content(cdim)
        # czas z ocalałej (świeższy tor rankingu), treść dłuższa / bogatsza
        s_t = survivor.emb_time(cdim) if len(survivor.embedding or []) > cdim else None
        merged_c = (cs * s_c + cd * d_c) / float(cs + cd)
        if s_t is not None and len(s_t):
            merged = np.concatenate([merged_c, s_t])
        else:
            merged = merged_c
        nrm = float(np.linalg.norm(merged)) + 1e-8
        survivor.embedding = (merged / nrm).astype(np.float32).tolist()
        survivor.cluster_size = cs + cd
        survivor._norm = -1.0
        # początek ścieżki = najstarszy created_at (pastness)
        ta = float(survivor.created_at or 0) or time.time()
        tb = float(donor.created_at or 0) or time.time()
        survivor.created_at = min(ta, tb)
        survivor.relevance = max(
            float(survivor.relevance or 0),
            float(donor.relevance or 0),
            float(getattr(self.hm.cfg, "crystallize_relevance_floor", 1.4)),
        )
        survivor.is_fact = bool(survivor.is_fact or donor.is_fact)
        survivor.is_work = bool(survivor.is_work or donor.is_work)
        survivor.is_insight = bool(survivor.is_insight or donor.is_insight)
        survivor.is_reminder = bool(survivor.is_reminder or donor.is_reminder)
        # po merge ścieżka jest wiedzą, nie samym work-spamem gdy donor był fact
        if survivor.is_fact and survivor.is_work and not donor.is_work:
            # zachowaj work tylko jeśli survivor był work
            pass
        sc, dc = (survivor.content or ""), (donor.content or "")
        if len(dc) > len(sc):
            survivor.content = dc[:800]
        survivor.age = 0
        survivor.relevance = min(5.0, float(survivor.relevance) + 0.15)

    def crystallize(
        self,
        project: str = "",
        *,
        dry_run: bool = False,
        sim_threshold: Optional[float] = None,
        promote_cluster_min: Optional[int] = None,
        max_active_work: Optional[int] = None,
        reinforce_phi: bool = True,
    ) -> dict:
        """Offline: utrwal stałe ścieżki pamięci (B9).

        1. Merge near-duplikatów (cosine+lex) → jedna ścieżka, większy cluster_size
        2. Promote epizodów z dużym cluster_size → fact
        3. Demote nadmiaru work → fact (higiena SE, jak set-work)
        4. Podbij relevance durable + wzmocnij Φ wokół ocalałych ścieżek

        Zwraca raport JSON-friendly. ``dry_run`` nie mutuje store.
        Domyślnie **nie** zapisuje — wołający robi ``save()`` (CLI tak).
        """
        if not self._started:
            self.start()
        cfg = self.hm.cfg
        thr = float(
            sim_threshold
            if sim_threshold is not None
            else getattr(cfg, "crystallize_sim_threshold", 0.90)
        )
        prom_min = int(
            promote_cluster_min
            if promote_cluster_min is not None
            else getattr(cfg, "crystallize_promote_cluster_min", 2)
        )
        max_w = int(
            max_active_work
            if max_active_work is not None
            else getattr(cfg, "crystallize_max_active_work", 3)
        )
        floor = float(getattr(cfg, "crystallize_relevance_floor", 1.4))
        reinf_top = int(getattr(cfg, "crystallize_reinforce_top", 24))

        before = len(self.hm.store)
        candidates = [
            i for i in self.hm.store
            if self._match_project(i.content, project)
        ]
        # Greedy merge: sortuj durable/cluster malejąco, scal w lewo
        order = sorted(
            candidates,
            key=lambda x: (
                1 if self._is_durable_item(x) else 0,
                int(x.cluster_size or 1),
                float(x.relevance or 0),
            ),
            reverse=True,
        )
        alive: List[Item] = list(order)
        merged_pairs: List[dict] = []
        removed_ids: set = set()

        i = 0
        while i < len(alive):
            a = alive[i]
            if a.id in removed_ids:
                i += 1
                continue
            j = i + 1
            while j < len(alive):
                b = alive[j]
                if b.id in removed_ids:
                    j += 1
                    continue
                sim = self._path_similarity(a, b)
                if sim < thr:
                    j += 1
                    continue
                surv, don = self._crystal_survivor(a, b)
                if not dry_run:
                    self._crystal_merge_into(surv, don)
                merged_pairs.append({
                    "sim": round(sim, 4),
                    "kept": (surv.content or "")[:120],
                    "dropped": (don.content or "")[:120],
                    "cluster_after": int(surv.cluster_size or 1),
                })
                removed_ids.add(don.id)
                # kontynuuj z survivorem w pozycji a
                if surv is b:
                    alive[i] = surv
                    a = surv
                j += 1
            i += 1

        if not dry_run and removed_ids:
            self.hm.store = [x for x in self.hm.store if x.id not in removed_ids]
            try:
                self.lex_index.rebuild(self.hm.store)
            except Exception:
                self.lex_index.mark_dirty()

        promoted: List[str] = []
        for it in list(self.hm.store):
            if project and not self._match_project(it.content, project):
                continue
            if self._is_durable_item(it):
                continue
            if int(it.cluster_size or 1) >= prom_min:
                promoted.append((it.content or "")[:120])
                if not dry_run:
                    it.is_fact = True
                    it.relevance = max(float(it.relevance or 0), floor)
                    it.age = 0

        demoted_work: List[str] = []
        works = [
            i for i in self.hm.store
            if i.is_work and self._match_project(i.content, project)
        ]
        works.sort(key=lambda x: -(x.created_at or 0))
        for w in works[max_w:]:
            demoted_work.append((w.content or "")[:120])
            if not dry_run:
                w.is_work = False
                w.is_fact = True

        reinforced = 0
        if reinforce_phi and not dry_run:
            paths = [
                i for i in self.hm.store
                if self._is_durable_item(i)
                and self._match_project(i.content, project)
            ]
            paths.sort(
                key=lambda x: (
                    int(x.cluster_size or 1),
                    float(x.relevance or 0),
                ),
                reverse=True,
            )
            top = paths[: max(1, reinf_top)]
            for it in top:
                it.relevance = max(float(it.relevance or 0), floor)
            if top:
                try:
                    self.hm._update_phi(top)
                    reinforced = len(top)
                except Exception:
                    reinforced = 0

        after = len(self.hm.store)
        report = {
            "ok": True,
            "op": "crystallize",
            "dry_run": bool(dry_run),
            "project": project or None,
            "threshold": thr,
            "store_before": before,
            "store_after": after if not dry_run else before - len(removed_ids),
            "merged": len(merged_pairs),
            "merged_pairs": merged_pairs[:40],
            "promoted_to_fact": len(promoted),
            "promoted_samples": promoted[:20],
            "demoted_work_to_fact": len(demoted_work),
            "demoted_samples": demoted_work[:20],
            "phi_reinforced": reinforced,
            "removed_ids": len(removed_ids),
        }
        return report

    @staticmethod
    def parse_since(since) -> Optional[float]:
        """Parsuj ``24h`` / ``7d`` / ``90m`` / ``3600s`` / ``12`` → godziny.

        Zwraca ``None`` gdy brak filtra. Raises ``ValueError`` przy złym formacie.
        """
        if since is None or since is False:
            return None
        if isinstance(since, (int, float)):
            h = float(since)
            if h < 0:
                raise ValueError("since must be >= 0")
            return h
        s = str(since).strip().lower()
        if not s or s in ("0", "none", "off", "all", "-"):
            return None
        import re
        m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([dhms])?", s)
        if not m:
            raise ValueError(
                f"niepoprawne --since {since!r} (np. 24h, 7d, 90m, 12)"
            )
        val = float(m.group(1))
        unit = m.group(2) or "h"
        if unit == "d":
            return val * 24.0
        if unit == "h":
            return val
        if unit == "m":
            return val / 60.0
        if unit == "s":
            return val / 3600.0
        return val

    @staticmethod
    def _handoff_norm_content(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())[:160]

    def _handoff_dedupe(self, items: List[Item], max_n: int) -> List[Item]:
        """Usuń near-dupy w projekcji handoff (nie mutuje store)."""
        out: List[Item] = []
        seen: List[str] = []
        for it in items:
            if len(out) >= max_n:
                break
            n = self._handoff_norm_content(it.content or "")
            if not n:
                continue
            dup = False
            for s in seen:
                if n == s or (len(n) > 48 and (n[:64] in s or s[:64] in n)):
                    dup = True
                    break
                # token Jaccard na krótkich oknach
                ta, tb = set(n.split()), set(s.split())
                if ta and tb:
                    j = len(ta & tb) / max(1, len(ta | tb))
                    if j >= 0.72:
                        dup = True
                        break
            if dup:
                continue
            seen.append(n)
            out.append(it)
        return out

    def _fact_anchor_score(self, item: Item) -> tuple:
        """Kotwice: relevance + cluster + długość; lekka świeżość na remis."""
        return (
            float(item.relevance or 0),
            int(item.cluster_size or 1),
            len(item.content or ""),
            float(item.created_at or 0),
        )

    def _pack_item(self, i: Item, *, outside_window: Optional[bool] = None) -> dict:
        d = {
            "when": self._past_label(i.created_at),
            "created_at": i.created_at,
            "content": (i.content or "")[:500],
            "flags": {
                "fact": bool(i.is_fact),
                "work": bool(i.is_work),
                "insight": bool(i.is_insight),
            },
        }
        if outside_window is not None:
            d["outside_window"] = bool(outside_window)
        return d

    def _suggested_mneme(
        self, work_items: List[Item], project: str = ""
    ) -> List[str]:
        """Gotowe zapytania Mneme-L z active work (B10)."""
        if not work_items:
            return []
        raw = work_items[0].content or ""
        # zdejmij [Project]
        raw = re.sub(r"\[[^\]]+\]\s*", "", raw).strip()
        # tokeny alfanum ≥3, bez szumu
        stop = {
            "next", "optional", "later", "done", "saved", "the", "and", "for",
            "with", "from", "that", "this", "następny", "opcjonalnie", "dalej",
        }
        toks = [
            t for t in re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9_./-]{3,}", raw)
            if t.lower() not in stop
        ]
        if not toks:
            return []
        # preferuj tokeny z cyfrą / camel / path-ish
        ranked = sorted(
            toks,
            key=lambda t: (
                1 if any(c.isdigit() for c in t) else 0,
                1 if "/" in t or "." in t or "_" in t else 0,
                len(t),
            ),
            reverse=True,
        )
        primary = " ".join(ranked[:3])[:48].strip()
        secondary = ranked[0][:40] if ranked else primary
        if not primary:
            return []
        out = [
            f'RECALL "{primary}" TOP 5',
            f'NEAR "{secondary}" TOP 3',
        ]
        if project:
            out.append(f'FOCUS PROJECT {project}')
        return out[:3]

    def _recommended_actions(
        self,
        *,
        project: str,
        n_work: int,
        n_facts: int,
        delta_hours,
        since_h,
        hybrid_filled: bool,
        work_in_window: int,
        facts_in_window: int,
    ) -> List[str]:
        """Sygnały operacyjne z store (nie zmyślanie treści)."""
        acts: List[str] = []
        cfg = self.hm.cfg
        max_w = int(getattr(cfg, "set_work_max_active", 1))
        proj = (project or "").strip()
        pflag = f" --project {proj}" if proj else ""
        try:
            dh = float(delta_hours) if delta_hours is not None else 0.0
        except (TypeError, ValueError):
            dh = 0.0
        if n_work > max_w:
            acts.append(
                f"crystallize{pflag}  # work={n_work}>{max_w}; demote nadmiar"
            )
        if n_work > 1:
            acts.append(
                f'set-work "…" --max-active 1{pflag}  # jeden aktywny wątek'
            )
        if n_facts >= 40 and proj:
            acts.append(f"crystallize{pflag}  # store szumi (facts≥40 w projekcie)")
        if dh >= 48 and since_h is not None:
            acts.append(
                "agent_boot bez --since  # długa przerwa — pełne anchors"
            )
        if since_h is not None and work_in_window == 0 and facts_in_window == 0:
            if hybrid_filled:
                acts.append(
                    "brak delty w oknie; active_work z poza okna (hybrid) — "
                    "zapisz close/set-work gdy ruszysz wątek"
                )
            else:
                acts.append(
                    "brak delty w oknie; handoff pełny lub --since większe okno"
                )
        if not acts:
            acts.append(
                f'close --work "…" --fact "…" {pflag.strip()}  # domknięcie sesji B10'
                if proj
                else 'close --work "…" --fact "…" --project P  # domknięcie sesji B10'
            )
        return acts[:5]

    def handoff(
        self,
        project: str = "",
        max_work: Optional[int] = None,
        max_facts: Optional[int] = None,
        include_digest: bool = True,
        since=None,
        *,
        compact: bool = False,
        hybrid_since: Optional[bool] = None,
        max_chronicle: Optional[int] = None,
    ) -> dict:
        """Maszynowy bootstrap sesji agenta (JSON) — mniej szumu niż pełny digest.

        Protokół: holon-agent-handoff-v1 (+ B10 projection)

        ``since`` (B1): okno delty. **B10 hybrid** (domyślnie on): w ``active_work``
        dołóż last work spoza okna (``outside_window: true``), żeby re-boot
        nie dawał fałszywej amnezji.

        B10 warstwy factów:
          - ``anchors`` — stabilne kotwice (relevance/cluster)
          - ``chronicle`` — świeższy log (nie duplikuje anchors)
          - ``key_facts`` — kompat: w full=anchors; w delta/hybrid=nowe w oknie
        """
        if not self._started:
            self.start()
        st = self.stats()
        cfg = self.hm.cfg
        if max_work is None:
            max_work = int(getattr(cfg, "handoff_max_work", 2))
        if max_facts is None:
            max_facts = int(getattr(cfg, "handoff_max_facts", 6))
        if max_chronicle is None:
            max_chronicle = int(getattr(cfg, "handoff_max_chronicle", 4))
        if compact:
            max_work = min(max_work, 2)
            max_facts = min(max_facts, 5)
            max_chronicle = min(max_chronicle, 2)
        max_work = max(1, int(max_work))
        max_facts = max(1, int(max_facts))
        max_chronicle = max(0, int(max_chronicle))

        since_h = self.parse_since(since)
        now = time.time()
        cutoff = (now - since_h * 3600.0) if since_h is not None else None
        if hybrid_since is None:
            hybrid_since = bool(getattr(cfg, "handoff_hybrid_since", True))

        def in_window(i: Item) -> bool:
            if cutoff is None:
                return True
            ca = float(i.created_at or 0)
            if ca <= 0:
                return False
            return ca >= cutoff

        work_all = [
            i for i in self.hm.store
            if i.is_work and self._match_project(i.content, project)
        ]
        facts_all = [
            i for i in self.hm.store
            if i.is_fact and not i.is_work
            and self._match_project(i.content, project)
        ]
        work_all.sort(key=lambda x: -(x.created_at or 0))
        facts_all.sort(key=lambda x: -(x.created_at or 0))

        work_in = [i for i in work_all if in_window(i)]
        work_out = [i for i in work_all if not in_window(i)]
        facts_in = [i for i in facts_all if in_window(i)]

        # ── work projection (B10 hybrid) ─────────────────────────────────
        selected_work: List[Tuple[Item, bool]] = []
        hybrid_filled = False
        if since_h is not None:
            for i in work_in:
                if len(selected_work) >= max_work:
                    break
                selected_work.append((i, False))
            if hybrid_since:
                for i in work_out:
                    if len(selected_work) >= max_work:
                        break
                    selected_work.append((i, True))
                    hybrid_filled = True
            mode = "hybrid" if hybrid_filled else "delta"
        else:
            # full: jeden/kilka wątków, dedupe near-dup work
            for i in self._handoff_dedupe(work_all, max_work):
                selected_work.append((i, False))
            mode = "full"

        active_packed = [
            self._pack_item(i, outside_window=ow if since_h is not None else None)
            for i, ow in selected_work
        ]
        # recent_done: zdemotowane work→fact nie ma flagi work; pokazujemy starsze work
        # poza active (jeśli zostało) jako historię wątku
        selected_ids = {id(i) for i, _ in selected_work}
        recent_done = [
            self._pack_item(i)
            for i in work_all
            if id(i) not in selected_ids
        ][:2]

        # ── fact projection: anchors + chronicle ─────────────────────────
        anchors_src = sorted(facts_all, key=self._fact_anchor_score, reverse=True)
        anchors = self._handoff_dedupe(anchors_src, max_facts)
        anchor_ids = {id(x) for x in anchors}
        chronicle_src = [i for i in facts_all if id(i) not in anchor_ids]
        chronicle = self._handoff_dedupe(chronicle_src, max_chronicle)

        if since_h is not None:
            # key_facts = delty w oknie (kompat B1); nie mieszaj starych do key_facts
            key_facts_items = self._handoff_dedupe(facts_in, max_facts)
        else:
            key_facts_items = anchors

        wake = getattr(self.hm, "_last_wake", "") or ""
        if since_h is not None and not work_in and not facts_in and hybrid_filled:
            wake = (
                (wake + " " if wake else "")
                + "[B10 hybrid: brak delty w oknie — active_work spoza --since.]"
            ).strip()

        work_items_for_mneme = [i for i, _ in selected_work]
        out = {
            "protocol": "holon-agent-handoff-v1",
            "profile": st.get("profile"),
            "project_filter": project or None,
            "mode": mode,
            "stats": {
                "turns": st.get("turns"),
                "store": st.get("store"),
                "delta_hours": st.get("delta_hours"),
                "facts": st.get("facts"),
                "work": st.get("work"),
                "episodic": st.get("episodic"),
            },
            "wake": wake,
            "active_work": active_packed,
            "recent_done": recent_done,
            "key_facts": [self._pack_item(i) for i in key_facts_items],
            "anchors": [self._pack_item(i) for i in anchors],
            "chronicle": [self._pack_item(i) for i in chronicle],
            "recommended_actions": self._recommended_actions(
                project=project or "",
                n_work=len(work_all),
                n_facts=len(facts_all),
                delta_hours=st.get("delta_hours"),
                since_h=since_h,
                hybrid_filled=hybrid_filled,
                work_in_window=len(work_in),
                facts_in_window=len(facts_in),
            ),
            "suggested_mneme": self._suggested_mneme(
                work_items_for_mneme, project=project or ""
            ),
            "agent_protocol": [
                "1. Na start sesji: handoff / agent_boot.py; re-boot: --since 24h (B1+B10 hybrid).",
                "2. Po decyzji trwałej: remember --fact \"...\" (prefiks [Projekt]).",
                "3. Aktywny wątek: set-work (domyślnie 1) / close na koniec sesji.",
                "4. Po sesji / gdy store szumi: crystallize [--project P] — B9 ścieżki.",
                "5. Nie kasuj/resetuj holon_memory.json bez prośby użytkownika.",
                "6. Kod Holon ≠ KarmazynOs — Holon=pamięć; runtime w KarmazynOs.",
                "7. Ewal: python holon_agent_memory.py eval",
                "8. Docs: AGENTS.md, docs/AGENT_WORKFLOW.md, docs/MEMORY_API.md",
            ],
            "paths": {
                "memory": self.memory_path,
                "docs": "docs/",
                "agents_md": "AGENTS.md",
                "api": "holon_memory_api.py",
            },
        }
        if compact:
            # mniej tokenów: protokół skrócony; chronicle tylko gdy full
            out["agent_protocol"] = [
                "boot → work/fact → close; crystallize gdy szumi; nie resetuj store.",
            ]
            if since_h is not None:
                out["chronicle"] = []
                out["anchors"] = out["anchors"][:3]

        if since_h is not None:
            out["since"] = {
                "raw": since if not isinstance(since, (int, float)) else f"{since_h}h",
                "hours": round(since_h, 6),
                "cutoff": cutoff,
                "work_in_window": len(work_in),
                "facts_in_window": len(facts_in),
                "work_total_project": len(work_all),
                "facts_total_project": len(facts_all),
                "hybrid": bool(hybrid_since),
                "hybrid_filled": bool(hybrid_filled),
            }
            if not compact:
                out["agent_protocol"] = [
                    "mode=delta|hybrid: facts w oknie; work hybrid dopełnia spoza okna.",
                    "strict delta: handoff(..., hybrid_since=False) / agent_boot --strict-delta.",
                    "Zapis: close / remember --fact / set-work; crystallize gdy store szumi.",
                ]
        if include_digest:
            if since_h is not None:
                lines = [
                    "=== HOLON AGENT DIGEST (DELTA/HYBRID) ===",
                    f"since={out['since']['raw']} hours={since_h} "
                    f"project={project or '*'} hybrid={hybrid_filled}",
                    f"new_work={len(work_in)} new_facts={len(facts_in)} "
                    f"(project totals work={len(work_all)} facts={len(facts_all)})",
                    "",
                ]
                if active_packed:
                    lines.append("ACTIVE WORK (hybrid-aware):")
                    for p in active_packed[:max_work]:
                        tag = " [outside]" if p.get("outside_window") else ""
                        lines.append(
                            f"  • [{p.get('when')}]{tag} "
                            f"{(p.get('content') or '')[:400]}"
                        )
                    lines.append("")
                if key_facts_items:
                    lines.append("NOWE FAKTY (w oknie):")
                    for i in key_facts_items[:max_facts]:
                        lines.append(
                            f"  • [{self._past_label(i.created_at)}] "
                            f"{(i.content or '')[:300]}"
                        )
                    lines.append("")
                if not work_in and not facts_in and not hybrid_filled:
                    lines.append("(brak delty w oknie — store bez nowych wpisów)")
                elif not work_in and not facts_in and hybrid_filled:
                    lines.append(
                        "(brak delty w oknie — pokazano work spoza okna, B10 hybrid)"
                    )
                lines.append("=== END DIGEST ===")
                out["digest"] = "\n".join(lines)
            else:
                out["digest"] = self.digest(
                    max_facts=max_facts, max_work=max_work, project=project)
        return out

    @staticmethod
    def format_handoff_md(h: dict) -> str:
        """B7: handoff JSON → czytelny Markdown (dla człowieka / wklejki SE)."""
        from datetime import datetime, timezone

        lines: List[str] = []
        mode = h.get("mode") or "full"
        proj = h.get("project_filter") or "all"
        gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.append("# Holon agent handoff")
        lines.append("")
        lines.append(f"- **protocol:** `{h.get('protocol', '?')}`")
        lines.append(f"- **mode:** `{mode}`")
        lines.append(f"- **profile:** `{h.get('profile', '?')}`")
        lines.append(f"- **project:** `{proj}`")
        lines.append(f"- **generated:** {gen}")
        st = h.get("stats") or {}
        if st:
            lines.append(
                f"- **stats:** store={st.get('store')} facts={st.get('facts')} "
                f"work={st.get('work')} episodic={st.get('episodic')} "
                f"Δh={st.get('delta_hours')}"
            )
        lines.append("")

        wake = (h.get("wake") or "").strip()
        if wake:
            lines.append("## Wake")
            lines.append("")
            lines.append(wake)
            lines.append("")

        since = h.get("since")
        if isinstance(since, dict):
            lines.append("## Delta window (`--since`)")
            lines.append("")
            lines.append(
                f"- raw=`{since.get('raw')}` hours={since.get('hours')} "
                f"work_in_window={since.get('work_in_window')}/"
                f"{since.get('work_total_project')} "
                f"facts_in_window={since.get('facts_in_window')}/"
                f"{since.get('facts_total_project')}"
            )
            lines.append("")

        work = h.get("active_work") or []
        lines.append("## Active work")
        lines.append("")
        if work:
            for i, it in enumerate(work, 1):
                when = it.get("when") or "?"
                content = (it.get("content") or "").strip()
                ow = " *(outside window)*" if it.get("outside_window") else ""
                lines.append(f"{i}. **[{when}]**{ow} {content}")
        else:
            lines.append("_brak work w tym widoku_")
        lines.append("")

        recent = h.get("recent_done") or []
        if recent:
            lines.append("## Recent done (other active work)")
            lines.append("")
            for i, it in enumerate(recent, 1):
                when = it.get("when") or "?"
                content = (it.get("content") or "").strip()
                lines.append(f"{i}. **[{when}]** {content}")
            lines.append("")

        facts = h.get("key_facts") or []
        lines.append("## Key facts")
        lines.append("")
        if facts:
            for i, it in enumerate(facts, 1):
                when = it.get("when") or "?"
                content = (it.get("content") or "").strip()
                lines.append(f"{i}. **[{when}]** {content}")
        else:
            lines.append("_brak factów w tym widoku_")
        lines.append("")

        anchors = h.get("anchors") or []
        if anchors and h.get("mode") in ("delta", "hybrid"):
            lines.append("## Anchors (stable)")
            lines.append("")
            for i, it in enumerate(anchors[:6], 1):
                when = it.get("when") or "?"
                content = (it.get("content") or "").strip()
                lines.append(f"{i}. **[{when}]** {content}")
            lines.append("")

        chronicle = h.get("chronicle") or []
        if chronicle and h.get("mode") == "full":
            lines.append("## Chronicle")
            lines.append("")
            for i, it in enumerate(chronicle, 1):
                when = it.get("when") or "?"
                content = (it.get("content") or "").strip()
                lines.append(f"{i}. **[{when}]** {content}")
            lines.append("")

        rec = h.get("recommended_actions") or []
        if rec:
            lines.append("## Recommended actions")
            lines.append("")
            for a in rec:
                lines.append(f"- {a}")
            lines.append("")

        mneme = h.get("suggested_mneme") or []
        if mneme:
            lines.append("## Suggested Mneme")
            lines.append("")
            for m in mneme:
                lines.append(f"- `{m}`")
            lines.append("")

        proto = h.get("agent_protocol") or []
        if proto:
            lines.append("## Agent protocol")
            lines.append("")
            for p in proto:
                lines.append(f"- {p}")
            lines.append("")

        paths = h.get("paths") or {}
        if paths:
            lines.append("## Paths")
            lines.append("")
            for k, v in paths.items():
                lines.append(f"- **{k}:** `{v}`")
            lines.append("")

        dig = (h.get("digest") or "").strip()
        if dig:
            lines.append("## Digest")
            lines.append("")
            lines.append("```")
            lines.append(dig)
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("_Źródło: `holon-agent-handoff-v1` → B7 markdown (+ B10)_")
        lines.append("")
        return "\n".join(lines)

    def handoff_md(
        self,
        project: str = "",
        max_work: Optional[int] = None,
        max_facts: Optional[int] = None,
        include_digest: bool = False,
        since=None,
        out_path: Optional[str] = None,
        *,
        compact: bool = False,
        hybrid_since: Optional[bool] = None,
    ) -> str:
        """B7: handoff jako Markdown; opcjonalnie zapis do pliku.

        Domyślnie **bez** pełnego digest (krótszy md); włącz ``include_digest=True``.
        """
        h = self.handoff(
            project=project,
            max_work=max_work,
            max_facts=max_facts,
            include_digest=include_digest,
            since=since,
            compact=compact,
            hybrid_since=hybrid_since,
        )
        md = self.format_handoff_md(h)
        if out_path:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(md, encoding="utf-8")
        return md

    def collab_test(self) -> dict:
        """Powtarzalny test współpracy agenta z pamięcią (nie niszczy store na stałe
        poza dopisaniem oznaczonego faktu testowego, jeśli wywołane na żywej ścieżce).

        Zwraca dict z polami pass/fail i metrykami.
        """
        import json
        import shutil
        import tempfile
        from pathlib import Path

        from holon_memory import PersistentMemory

        results = []
        ok = True

        def check(name: str, cond: bool, detail: str = ""):
            nonlocal ok
            if not cond:
                ok = False
            results.append({"name": name, "pass": bool(cond), "detail": detail})

        # 1) baseline
        st = self.stats()
        check("load_store_nonempty", st.get("store", 0) > 0,
              f"store={st.get('store')}")
        check("has_facts", st.get("facts", 0) >= 1, f"facts={st.get('facts')}")
        dig = self.digest()
        check("digest_has_header", "HOLON AGENT DIGEST" in dig)
        check("digest_has_facts_or_work",
              "TRWAŁE FAKTY" in dig or "AKTYWNE PROJEKTY" in dig)

        # 2) remember → save → reload (na kopii pliku)
        src = Path(self.memory_path)
        tmpdir = Path(tempfile.mkdtemp(prefix="holon_collab_"))
        try:
            tmp_mem = tmpdir / "holon_memory.json"
            shutil.copy2(src, tmp_mem)
            kurz_src = Path(str(src).replace(".json", "_kurz.json"))
            if kurz_src.is_file():
                shutil.copy2(kurz_src, tmpdir / kurz_src.name)

            token = f"COLLABTOKEN_{int(time.time())}"
            am2 = AgentMemory.open(memory_path=str(tmp_mem))
            am2.remember(
                f"Fakt testowy współpracy: unikalny znacznik {token} "
                f"dla holon_agent_memory collab-test.",
                kind="fact")
            check("save_after_remember", am2.save(), "save()")

            am3 = AgentMemory.open(memory_path=str(tmp_mem))
            hit = any(token in i.content for i in am3.hm.store)
            check("reload_preserves_fact", hit, token)
            ranked = am3.recall(f"znacznik {token} collab-test", top_k=5)
            top_txt = " | ".join(i.content[:80] for _, i in ranked[:3])
            check("recall_ranks_token_top5",
                  any(token in i.content for _, i in ranked), top_txt)

            # 3) long absence durability
            raw = json.loads(tmp_mem.read_text(encoding="utf-8"))
            raw["timestamp"] = time.time() - 180 * 24 * 3600
            aged = tmpdir / "aged.json"
            aged.write_text(json.dumps(raw), encoding="utf-8")
            res = PersistentMemory(str(aged)).load(Config.agent())
            n_fact = sum(1 for i in res["store"] if i.is_fact)
            still = any(token in i.content for i in res["store"])
            check("durable_after_180d", still and n_fact >= 1,
                  f"facts={n_fact} token={still} coherence={res.get('coherence')}")

            # 4) turn injects memory block + hybrid recall path
            am4 = AgentMemory.open(memory_path=str(tmp_mem))
            msgs = am4.hm.turn(
                f"Przypomnij fakt o {token} i KarmazynOs",
                system_prompt="agent-test")
            blob = "\n".join(m.get("content", "") for m in msgs)
            check("turn_has_internal_state", "STAN WEWNĘTRZNY" in blob)
            # po turn store ma co najmniej poprzednie fakty
            check("turn_store_keeps_facts",
                  sum(1 for i in am4.hm.store if i.is_fact) >= 1)

            # 5) vacuum must not drop durable when over MAX
            am5 = AgentMemory.open(memory_path=str(tmp_mem))
            before_f = sum(1 for i in am5.hm.store if i.is_fact)
            # force many episodics
            for n in range(80):
                emb = am5.hm.embedder.encode(f"ephemeral noise {n}", timestamp=time.time())
                am5.hm.store.append(Item(
                    id=str(uuid.uuid4()), content=f"noise {n}",
                    embedding=emb.tolist(), age=10, relevance=0.1))
            am5.hm.turns = max(am5.hm.turns, 1)
            q = am5.hm.embedder.encode("noise", timestamp=time.time())
            am5.hm._vacuum(q)
            after_f = sum(1 for i in am5.hm.store if i.is_fact)
            check("vacuum_preserves_facts", after_f >= before_f,
                  f"before={before_f} after={after_f} store={len(am5.hm.store)}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        return {"ok": ok, "checks": results, "stats": st}

    def golden_eval(self) -> dict:
        """Samowystarczalny golden eval na temp store (nie rusza holon_memory.json)."""
        from holon_memory_eval import run_golden_eval

        return run_golden_eval()

    def karmin_sync(self, durable_only: bool = True) -> dict:
        """Mirror fact/work → Karmin_DB (in-process). Wymaga DBase / cynober-db."""
        from holon_backend_karmin import KarminMirror, karmin_available

        if not karmin_available():
            return {"ok": False, "error": "karmin_unavailable"}
        if not self._started:
            self.start()
        m = KarminMirror.open()
        res = m.sync_items(self.hm.store, durable_only=durable_only)
        res["ok"] = True
        res["mirror_stats"] = m.stats()
        return res

    def karmin_export(self, snapshot_path: str, *, sync_first: bool = True) -> dict:
        """Backup durable → snapshot JSON (holon-karmin-snapshot-v1). Zastępuje plan SQLite."""
        from holon_backend_karmin import KarminMirror, karmin_available

        if not karmin_available():
            return {"ok": False, "error": "karmin_unavailable"}
        if not self._started:
            self.start()
        m = KarminMirror.open()
        if sync_first:
            m.sync_items(self.hm.store, durable_only=True)
        path = m.export_snapshot(snapshot_path)
        return {"ok": True, "path": str(path), "stats": m.stats()}

    def karmin_import_merge(
        self, snapshot_path: str, *, reembed: bool = True
    ) -> dict:
        """Wczytaj snapshot Karmin → scal do store Holona (fact/work)."""
        from holon_backend_karmin import KarminMirror, karmin_available

        if not karmin_available():
            return {"ok": False, "error": "karmin_unavailable"}
        if not self._started:
            self.start()
        m = KarminMirror.open()
        n_eng = m.import_snapshot(snapshot_path)
        rows = m.fetch_rows()
        merged = 0
        for row in rows:
            content = (row.get("content") or "").strip()
            if not content:
                continue
            kind = "fact"
            if row.get("kind") == "work" or str(row.get("is_work")) in ("1", "True"):
                kind = "work"
            self.remember(content, kind=kind)
            merged += 1
        return {
            "ok": True,
            "engine_rows": n_eng,
            "merged_to_holon": merged,
            "reembed": reembed,
        }


def _main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Holon agent memory (Grok/CLI)")
    p.add_argument("cmd", choices=[
        "digest", "remember", "recall", "seed", "stats", "collab-test", "eval",
        "ablation", "llm-slot", "handoff", "handoff-md", "set-work", "close",
        "boot", "crystallize", "watch-remember",
        "karmin-sync", "karmin-export", "karmin-import", "karmin-slot"])
    p.add_argument("text", nargs="?", default="",
                   help="treść (remember/set-work) lub zapytanie (recall)")
    p.add_argument("--fact", dest="as_fact", action="store_true")
    p.add_argument("--work", dest="as_work", action="store_true")
    p.add_argument(
        "--fact-text",
        default="",
        help="close: treść fact summary (osobno od flagi --fact)",
    )
    p.add_argument(
        "--work-text",
        default="",
        help="close: treść work (alternatywa do positional text)",
    )
    p.add_argument("--kind", default="", help="fact|work|note")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--path", default="holon_memory.json")
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--project", default="",
                   help="filtr / prefiks projektu (Holon, Karmazyn, …)")
    p.add_argument("--no-digest", action="store_true",
                   help="handoff: bez pełnego digest w JSON")
    p.add_argument(
        "--since",
        default="",
        help="handoff B1/B10: okno delty — 24h | 7d | 90m | godziny (np. 12)",
    )
    p.add_argument(
        "--strict-delta",
        action="store_true",
        help="handoff: wyłącz B10 hybrid (tylko work w oknie --since)",
    )
    p.add_argument(
        "--compact",
        action="store_true",
        help="handoff: mniej tokenów (krótki protocol, ciaśniejsze limity)",
    )
    p.add_argument(
        "--max-active",
        type=int,
        default=None,
        help="set-work / close / crystallize: ile work zostawić (domyślnie 1)",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="crystallize: raport bez mutacji store")
    p.add_argument("--sim", type=float, default=None,
                   help="crystallize: próg similarity (domyślnie z Config)")
    p.add_argument("--snapshot", default="holon_karmin_snapshot.json",
                   help="ścieżka snapshotu Karmin (export/import)")
    p.add_argument(
        "--out",
        default="",
        help="handoff-md: zapisz Markdown do pliku (np. handoff.md)",
    )
    p.add_argument(
        "--inbox",
        default="remember_inbox.jsonl",
        help="watch-remember: ścieżka JSONL inbox (B4)",
    )
    p.add_argument(
        "--poll",
        type=float,
        default=1.0,
        help="watch-remember: interwał poll (s)",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="watch-remember: jeden poll i wyjście",
    )
    args = p.parse_args(argv)

    am = AgentMemory.open(memory_path=args.path)

    if args.cmd == "digest":
        print(am.digest(project=args.project))
        return 0

    if args.cmd == "boot":
        # alias → agent_boot.py (jedna ścieżka dla agenta)
        from agent_boot import main as boot_main
        boot_argv = []
        if args.project:
            boot_argv.extend(["--project", args.project])
        if args.since:
            boot_argv.extend(["--since", args.since])
        if args.strict_delta:
            boot_argv.append("--strict-delta")
        if args.compact:
            boot_argv.append("--compact")
        if not args.no_digest:
            boot_argv.append("--full")
        boot_argv.extend(["--path", args.path])
        return int(boot_main(boot_argv) or 0)

    if args.cmd == "handoff":
        try:
            h = am.handoff(
                project=args.project,
                include_digest=not args.no_digest,
                since=args.since or None,
                compact=bool(args.compact),
                hybrid_since=False if args.strict_delta else None,
            )
        except ValueError as e:
            print(f"handoff: {e}", file=sys.stderr)
            return 2
        print(json.dumps(h, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.cmd == "handoff-md":
        # B7: Markdown. Domyślnie bez digest; dodaj digest: handoff-md digest
        try:
            want_dig = (args.text or "").strip().lower() in (
                "digest", "full", "with-digest",
            ) and not args.no_digest
            md = am.handoff_md(
                project=args.project,
                include_digest=want_dig,
                since=args.since or None,
                out_path=args.out or None,
                compact=bool(args.compact),
                hybrid_since=False if args.strict_delta else None,
            )
        except ValueError as e:
            print(f"handoff-md: {e}", file=sys.stderr)
            return 2
        if args.out:
            print(f"handoff-md: wrote {args.out} ({len(md)} chars)")
        else:
            sys.stdout.write(md if md.endswith("\n") else md + "\n")
        return 0

    if args.cmd == "stats":
        print(json.dumps(am.stats(), indent=2, ensure_ascii=False, default=str))
        return 0

    if args.cmd == "recall":
        q = args.text or "projekt holon agent praca"
        for score, item in am.recall(q, top_k=args.top):
            if args.project and not am._match_project(item.content, args.project):
                continue
            flags = []
            if item.is_fact:
                flags.append("F")
            if item.is_work:
                flags.append("W")
            if item.is_insight:
                flags.append("I")
            tag = "".join(flags) or "-"
            print(f"{score:.3f} [{tag}] {item.content[:300]}")
        return 0

    if args.cmd == "seed":
        n = am.seed()
        if not args.no_save:
            ok = am.save()
            print(f"seed: +{n} (merge/refresh), save={'ok' if ok else 'FAIL'}")
        else:
            print(f"seed: +{n} (bez zapisu)")
        print()
        print(am.digest(project=args.project))
        return 0

    if args.cmd == "set-work":
        text = args.text.strip()
        if not text:
            print('Podaj treść: set-work "..." [--project X]', file=sys.stderr)
            return 2
        item = am.set_work(text, project=args.project, max_active=args.max_active)
        if not args.no_save:
            ok = am.save()
            print(f"set-work id={item.id[:8]}… save={'ok' if ok else 'FAIL'}")
        else:
            print(f"set-work id={item.id[:8]}… (bez zapisu)")
        return 0

    if args.cmd == "close":
        # B10: close --work-text "…" --fact-text "…" --project P
        # albo: close "work text" --fact-text "…"
        w = (args.work_text or "").strip() or (
            args.text.strip() if not args.as_fact else ""
        )
        f = (args.fact_text or "").strip()
        if args.as_fact and args.text.strip() and not f:
            f = args.text.strip()
        if args.as_work and args.text.strip() and not w:
            w = args.text.strip()
        try:
            rep = am.close(
                work=w,
                fact=f,
                project=args.project,
                max_active=args.max_active,
                save=not args.no_save,
            )
        except ValueError as e:
            print(f"close: {e}", file=sys.stderr)
            print(
                'Użycie: close --work-text "…" --fact-text "…" --project P',
                file=sys.stderr,
            )
            return 2
        print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "crystallize":
        import json as _json
        rep = am.crystallize(
            project=args.project,
            dry_run=bool(args.dry_run),
            sim_threshold=args.sim,
            max_active_work=args.max_active,
        )
        if not args.dry_run and not args.no_save:
            rep["save"] = am.save()
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "collab-test":
        import json as _json
        report = am.collab_test()
        for c in report["checks"]:
            mark = "PASS" if c["pass"] else "FAIL"
            extra = f" — {c['detail']}" if c.get("detail") else ""
            print(f"[{mark}] {c['name']}{extra}")
        print()
        print("COLLAB_TEST:", "OK" if report["ok"] else "FAILED")
        print(_json.dumps({"ok": report["ok"], "n_checks": len(report["checks"]),
                           "stats": report["stats"]}, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if args.cmd == "eval":
        import json as _json
        from holon_memory_eval import run_golden_eval
        report = run_golden_eval()
        for c in report["checks"]:
            mark = "PASS" if c["pass"] else "FAIL"
            extra = f" — {c['detail']}" if c.get("detail") else ""
            print(f"[{mark}] {c['name']}{extra}")
        print()
        print("GOLDEN_EVAL:", "OK" if report["ok"] else "FAILED")
        print(_json.dumps(
            {"ok": report["ok"], "n_checks": len(report["checks"])},
            ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if args.cmd == "ablation":
        import json as _json
        from holon_memory_eval import run_ablation_report
        report = run_ablation_report()
        print(_json.dumps(report, indent=2, ensure_ascii=False, default=str))
        print()
        print("ABLATION:", "OK" if report.get("ok") else "FAILED")
        return 0 if report.get("ok") else 1

    if args.cmd == "watch-remember":
        import json as _json
        from holon_remember_watch import RememberInbox, describe_watch_slot
        if args.once:
            w = RememberInbox(
                am, args.inbox, poll_s=args.poll, auto_save=not args.no_save
            )
            rep = w.poll_once()
            print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
            return 0 if rep.get("ok") else 1
        print(_json.dumps(describe_watch_slot(), indent=2, ensure_ascii=False))
        print(f"watching {args.inbox} poll={args.poll}s (Ctrl+C stop)", flush=True)
        w = RememberInbox(
            am, args.inbox, poll_s=args.poll, auto_save=not args.no_save
        )
        try:
            w.run_forever()
        except KeyboardInterrupt:
            print("\n[remember-watch] stop")
        return 0

    if args.cmd == "llm-slot":
        import json as _json
        from holon_llm import describe_llm_slot, build_llm_client
        print(_json.dumps(describe_llm_slot(), indent=2, ensure_ascii=False))
        c = build_llm_client(backend="mock", quiet=True)
        print("mock_client:", type(c).__name__ if c else None)
        return 0

    if args.cmd == "karmin-slot":
        import json as _json
        from holon_backend_karmin import describe_karmin_slot
        print(_json.dumps(describe_karmin_slot(), indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "karmin-sync":
        import json as _json
        rep = am.karmin_sync()
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "karmin-export":
        import json as _json
        rep = am.karmin_export(args.snapshot)
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "karmin-import":
        import json as _json
        rep = am.karmin_import_merge(args.snapshot)
        if rep.get("ok") and not args.no_save:
            rep["holon_save"] = am.save()
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 0 if rep.get("ok") else 1

    if args.cmd == "remember":
        text = args.text.strip()
        if not text:
            print("Podaj treść: remember \"...\" [--fact|--work]", file=sys.stderr)
            return 2
        if args.as_work:
            kind = "work"
        elif args.as_fact:
            kind = "fact"
        elif args.kind:
            kind = args.kind
        else:
            kind = "fact"
        item = am.remember(text, kind=kind)
        if not args.no_save:
            ok = am.save()
            print(f"remembered [{kind}] id={item.id[:8]}… save={'ok' if ok else 'FAIL'}")
        else:
            print(f"remembered [{kind}] id={item.id[:8]}… (bez zapisu)")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
