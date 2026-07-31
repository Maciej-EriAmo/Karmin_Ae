# -*- coding: utf-8 -*-
"""holon_agent_memory.py — cienki adapter pamięci Holona pod agenta kodowego (Grok/CLI).

Use-case: Holon-as-memory (ciągłość SE), NIE kanon czatu EriAmo.
Profil: zawsze ``Config.agent()`` (jawny; chat = ``Config.chat()`` w Session).

Kontrakt: ``MemoryAPI`` (remember / recall / digest / save) — patrz holon_memory_api.py.

  python holon_agent_memory.py digest
  python holon_agent_memory.py remember --fact "..."
  python holon_agent_memory.py remember --work "..."
  python holon_agent_memory.py recall "query"
  python holon_agent_memory.py seed
  python holon_agent_memory.py stats
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
import sys
import time
import uuid
from typing import List, Optional, Sequence, Tuple

import numpy as np

from holon_config import Config
from holon_embedder import Embedder
from holon_holomem import HoloMem
from holon_item import Item


# Domyślne kotwice pod pracę Grok Build — seed idempotentny po treści.
AGENT_SEED: Tuple[Tuple[str, str], ...] = (
    ("fact",
     "Partner użytkownika: Maciek (EriAmo). Komunikacja po polsku, partnersko. "
     "Holon = pamięć SE; KarmazynOs = osobny monorepo runtime (nie fork Holona)."),
    ("fact",
     "Agent CLI: Grok (xAI). OBOWIĄZKOWY start: `cd C:\\Users\\drwis\\holonOs` "
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

    @classmethod
    def open(
        cls,
        memory_path: str = "holon_memory.json",
        kurz_path: Optional[str] = None,
        profile: str = "agent",
        cfg: Optional[Config] = None,
    ) -> "AgentMemory":
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
        return res

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
            if cand is not None and best_sim > 0.88:
                best = cand
        if best is not None:
            self.hm._semantic_merge(best, emb)
            if len(content) >= len(best.content):
                best.content = content[:800]
            best.is_fact = best.is_fact or is_fact
            best.is_work = best.is_work or is_work
            best.relevance = max(best.relevance, relevance)
            best.age = 0
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
        return item

    def recall(self, query: str, top_k: int = 8) -> List[Tuple[float, Item]]:
        """Hybryda zgodna z HoloMem: cosine + lexical (cfg.hybrid_lexical_weight)."""
        if not self._started:
            self.start()
        q = self.hm.embedder.encode(query, timestamp=time.time())
        cdim = self.hm.cfg.dim
        q_c = q[:cdim]
        lex_w = float(getattr(self.hm.cfg, "hybrid_lexical_weight", 0.18))
        scored: List[Tuple[float, Item]] = []
        for item in self.hm.store:
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
        return base

    def set_work(self, content: str, project: str = "",
                 max_active: int = 3) -> Item:
        """Ustaw aktywne work; nadmiar work (ten sam projekt) → fact (historia).

        Prefiks ``[Project]`` dodawany gdy ``project`` podany i brak w treści.
        """
        content = (content or "").strip()
        if not content:
            raise ValueError("pusta treść")
        proj = (project or "").strip()
        if proj and f"[{proj}]" not in content and f"[{proj.lower()}]" not in content.lower():
            content = f"[{proj}] {content}"
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
        return item

    def handoff(self, project: str = "", max_work: int = 4,
                max_facts: int = 8, include_digest: bool = True) -> dict:
        """Maszynowy bootstrap sesji agenta (JSON) — mniej szumu niż pełny digest.

        Protokół: holon-agent-handoff-v1
        """
        if not self._started:
            self.start()
        st = self.stats()
        work = [i for i in self.hm.store
                if i.is_work and self._match_project(i.content, project)]
        work.sort(key=lambda x: -(x.created_at or 0))
        facts = [i for i in self.hm.store
                 if i.is_fact and not i.is_work
                 and self._match_project(i.content, project)]
        facts.sort(key=lambda x: -(x.created_at or 0))

        def pack(i: Item) -> dict:
            return {
                "when": self._past_label(i.created_at),
                "created_at": i.created_at,
                "content": (i.content or "")[:500],
                "flags": {
                    "fact": bool(i.is_fact),
                    "work": bool(i.is_work),
                    "insight": bool(i.is_insight),
                },
            }

        wake = getattr(self.hm, "_last_wake", "") or ""
        out = {
            "protocol": "holon-agent-handoff-v1",
            "profile": st.get("profile"),
            "project_filter": project or None,
            "stats": {
                "turns": st.get("turns"),
                "store": st.get("store"),
                "delta_hours": st.get("delta_hours"),
                "facts": st.get("facts"),
                "work": st.get("work"),
                "episodic": st.get("episodic"),
            },
            "wake": wake,
            "active_work": [pack(i) for i in work[:max_work]],
            "key_facts": [pack(i) for i in facts[:max_facts]],
            "agent_protocol": [
                "1. Na start sesji: handoff (ten JSON) lub digest.",
                "2. Po decyzji trwałej: remember --fact \"...\" (prefiks [Projekt]).",
                "3. Aktywny wątek: set-work / remember --work; nie mnożyć work.",
                "4. Nie kasuj/resetuj holon_memory.json bez prośby użytkownika.",
                "5. Kod Holon ≠ KarmazynOs — Holon=pamięć; runtime w KarmazynOs.",
                "6. Ewal regregresji: python holon_agent_memory.py eval",
                "7. Docs: AGENTS.md, docs/AGENT_WORKFLOW.md, docs/MEMORY_API.md",
            ],
            "paths": {
                "memory": self.memory_path,
                "docs": "docs/",
                "agents_md": "AGENTS.md",
                "api": "holon_memory_api.py",
            },
        }
        if include_digest:
            out["digest"] = self.digest(
                max_facts=max_facts, max_work=max_work, project=project)
        return out

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
        "llm-slot", "handoff", "set-work", "boot",
        "karmin-sync", "karmin-export", "karmin-import", "karmin-slot"])
    p.add_argument("text", nargs="?", default="",
                   help="treść (remember/set-work) lub zapytanie (recall)")
    p.add_argument("--fact", dest="as_fact", action="store_true")
    p.add_argument("--work", dest="as_work", action="store_true")
    p.add_argument("--kind", default="", help="fact|work|note")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--path", default="holon_memory.json")
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--project", default="",
                   help="filtr / prefiks projektu (Holon, Karmazyn, …)")
    p.add_argument("--no-digest", action="store_true",
                   help="handoff: bez pełnego digest w JSON")
    p.add_argument("--max-active", type=int, default=3,
                   help="set-work: ile work zostawić aktywnych")
    p.add_argument("--snapshot", default="holon_karmin_snapshot.json",
                   help="ścieżka snapshotu Karmin (export/import)")
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
        if not args.no_digest:
            boot_argv.append("--full")
        boot_argv.extend(["--path", args.path])
        return int(boot_main(boot_argv) or 0)

    if args.cmd == "handoff":
        import json
        h = am.handoff(
            project=args.project,
            include_digest=not args.no_digest,
        )
        print(json.dumps(h, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.cmd == "stats":
        import json
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
