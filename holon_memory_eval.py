# -*- coding: utf-8 -*-
"""
holon_memory_eval.py — golden eval pamięci (bez LLM, temp store).

Uruchom:
  python holon_agent_memory.py eval
  python -m unittest tests.test_memory_eval -q
"""

from __future__ import annotations

import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from holon_agent_memory import AgentMemory
from holon_config import Config
from holon_embedder import Embedder
from holon_item import Item
from holon_memory import PersistentMemory


def run_golden_eval() -> Dict[str, Any]:
    """Zestaw scenariuszy: durable, decay, recall, profile, pastness, LLM slot."""
    checks: List[Dict[str, Any]] = []
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        checks.append({"name": name, "pass": bool(cond), "detail": detail})

    # ── profile split ────────────────────────────────────────────────────
    ca, cc = Config.agent(), Config.chat()
    check("profile_agent_name", ca.profile == "agent")
    check("profile_chat_name", cc.profile == "chat")
    check(
        "agent_longer_decay_than_chat",
        ca.store_decay_hours > cc.store_decay_hours,
        f"agent={ca.store_decay_hours} chat={cc.store_decay_hours}",
    )
    check(
        "agent_larger_store_cap",
        ca.hard_prune_store_max > cc.hard_prune_store_max,
        f"agent={ca.hard_prune_store_max} chat={cc.hard_prune_store_max}",
    )
    cf = Config.flat()
    check("flat_disables_prism", cf.use_prism is False, f"profile={cf.profile}")

    # ── durable fact vs ephemeral after long gap ─────────────────────────
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "m.json"
        kurz = str(Path(td) / "k.json")
        cfg = Config.agent()
        emb = Embedder(dim=cfg.dim, dict_path=kurz, time_dim=cfg.time_dim)
        am = AgentMemory.open(memory_path=str(path), kurz_path=kurz, cfg=cfg)
        token = f"GOLDEN_{uuid.uuid4().hex[:10]}"
        am.remember(f"Trwały fakt golden: {token}", kind="fact")
        am.remember("Aktywny projekt golden KarmazynOs", kind="work")
        # ephemeral
        e = emb.encode("szum epizodyczny xyz123", timestamp=time.time())
        am.hm.store.append(
            Item(
                id=str(uuid.uuid4()),
                content="szum epizodyczny xyz123",
                embedding=e.tolist(),
                age=3,
                relevance=0.2,
                is_fact=False,
            )
        )
        check("save_ok", am.save())

        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["timestamp"] = time.time() - 200 * 24 * 3600  # ~200 dni
        path.write_text(json.dumps(raw), encoding="utf-8")

        loaded = PersistentMemory(str(path)).load(cfg)
        contents = [i.content for i in loaded["store"]]
        check(
            "fact_survives_200d",
            any(token in c for c in contents),
            f"n={len(contents)}",
        )
        check(
            "work_survives_200d",
            any("KarmazynOs" in c for c in contents),
        )
        check(
            "ephemeral_gone_after_decay",
            not any("xyz123" in c for c in contents),
            f"store={contents[:3]!r}",
        )

        # reload + recall
        am2 = AgentMemory.open(memory_path=str(path), kurz_path=kurz, cfg=cfg)
        ranked = am2.recall(f"golden fakt {token}", top_k=5)
        check(
            "recall_finds_fact",
            any(token in i.content for _, i in ranked),
            " | ".join(i.content[:60] for _, i in ranked[:3]),
        )
        dig = am2.digest()
        check("digest_has_pastness_or_timeline",
              "DIGEST" in dig and ("temu" in dig or "OŚ CZASU" in dig or "TRWAŁE" in dig))
        check("digest_marks_work", "PROJEKT" in dig.upper() or "WORK" in dig.upper()
              or "Karmazyn" in dig)

    # ── chat profile still keeps facts forever (flag) ────────────────────
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "chat.json"
        kurz = str(Path(td) / "ck.json")
        cfg = Config.chat()
        am = AgentMemory.open(memory_path=str(path), kurz_path=kurz, cfg=cfg)
        am.remember("Fakt chat-profile durable", kind="fact")
        am.save()
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["timestamp"] = time.time() - 60 * 24 * 3600
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = PersistentMemory(str(path)).load(cfg)
        check(
            "chat_keeps_facts_forever",
            any("chat-profile" in i.content for i in loaded["store"]),
        )

    # ── pastness + AII baseline ──────────────────────────────────────────
    from holon_aii import AIIState, TimeDecay

    check("pastness_hours", "h" in TimeDecay.format_pastness(5.0)
          or "min" in TimeDecay.format_pastness(5.0))
    a = AIIState(None)
    a.emotion = "strach"
    a.vacuum_signal = -1.0
    a.focus_active = True
    a.relax_toward_baseline(500.0, half_life_hours=72.0)
    check("aii_baseline_after_gap", a.emotion == "neutral" and abs(a.vacuum_signal) < 0.05)

    # ── LLM slot (mock, no network) ──────────────────────────────────────
    from holon_llm import (
        MockLLMClient,
        build_llm_client,
        describe_llm_slot,
        register_local_model_factory,
    )

    mock = build_llm_client(backend="mock", model="t", quiet=True)
    check("llm_mock_builds", mock is not None and "mock" in mock.chat_completion(
        [{"role": "user", "content": "ping"}]).lower())

    def _factory(*, model="x", **kw):
        return MockLLMClient(model=f"local:{model}")

    register_local_model_factory(_factory)
    try:
        loc = build_llm_client(backend="local", model="gguf-future", quiet=True)
        check(
            "llm_local_factory_slot",
            loc is not None and "local:gguf" in loc.chat_completion(
                [{"role": "user", "content": "hi"}]),
            describe_llm_slot(),
        )
    finally:
        register_local_model_factory(None)

    # ── MemoryAPI protocol ───────────────────────────────────────────────
    from holon_memory_api import MemoryAPI, open_memory

    with tempfile.TemporaryDirectory() as td:
        p = str(Path(td) / "api.json")
        mem = open_memory(p, profile="agent")
        check("open_memory_is_api", isinstance(mem, MemoryAPI))
        mem.remember("API fact", kind="fact")
        check("api_save", mem.save())
        check("api_stats_facts", mem.stats().get("facts", 0) >= 1)
        h = mem.handoff(include_digest=False)
        check("handoff_protocol", h.get("protocol") == "holon-agent-handoff-v1")
        check("handoff_has_agent_protocol", len(h.get("agent_protocol") or []) >= 3)
        check("handoff_mode_full", h.get("mode") == "full", str(h.get("mode")))
        mem.set_work("Wątek A", project="Holon", max_active=1)
        mem.set_work("Wątek B", project="Holon", max_active=1)
        n_work = sum(1 for i in mem.hm.store
                     if i.is_work and "Holon" in (i.content or ""))
        check("set_work_demotes_old", n_work == 1, f"work={n_work}")

        # B1: handoff --since — tylko delty (created_at w oknie)
        tok_old = f"OLDFACT_{uuid.uuid4().hex[:6]}"
        tok_new = f"NEWFACT_{uuid.uuid4().hex[:6]}"
        mem.remember(f"[Holon] stary fact {tok_old}", kind="fact")
        for it in mem.hm.store:
            if tok_old in (it.content or ""):
                it.created_at = time.time() - 72 * 3600  # 3 dni temu
        mem.remember(f"[Holon] nowy fact {tok_new}", kind="fact")
        for it in mem.hm.store:
            if tok_new in (it.content or ""):
                it.created_at = time.time() - 0.5 * 3600  # 30 min temu
        hd = mem.handoff(project="Holon", include_digest=True, since="24h")
        check("handoff_since_mode_delta", hd.get("mode") == "delta", str(hd.get("mode")))
        check("handoff_since_meta", isinstance(hd.get("since"), dict)
              and float(hd["since"].get("hours") or 0) == 24.0,
              str(hd.get("since")))
        blob_f = " ".join(
            (x.get("content") or "") for x in (hd.get("key_facts") or [])
        )
        check("handoff_since_has_new", tok_new in blob_f, blob_f[:200])
        check("handoff_since_drops_old", tok_old not in blob_f, blob_f[:200])
        dig = hd.get("digest") or ""
        check("handoff_since_digest_delta", "DELTA" in dig or "since=" in dig.lower(),
              dig[:120])
        try:
            AgentMemory.parse_since("nope")
            check("parse_since_rejects_bad", False, "should raise")
        except ValueError:
            check("parse_since_rejects_bad", True)
        check("parse_since_7d", abs(AgentMemory.parse_since("7d") - 168.0) < 1e-6)
        check("parse_since_90m", abs(AgentMemory.parse_since("90m") - 1.5) < 1e-6)

        # B7: handoff → markdown
        md = mem.handoff_md(project="Holon", include_digest=False, since="24h")
        check("handoff_md_header", "# Holon agent handoff" in md, md[:80])
        check("handoff_md_has_work_or_facts_section",
              "## Active work" in md and "## Key facts" in md, md[:200])
        check("handoff_md_mode_delta", "delta" in md.lower() or "`delta`" in md, md[:150])
        from pathlib import Path as _P
        md_path = _P(td) / "handoff_out.md"
        md2 = mem.handoff_md(project="Holon", out_path=str(md_path))
        check("handoff_md_writes_file",
              md_path.is_file() and md_path.stat().st_size > 20,
              f"size={md_path.stat().st_size if md_path.is_file() else 0}")
        check("handoff_md_file_matches", md_path.read_text(encoding="utf-8") == md2)

    # ── crystallize B9 — merge near-dup + promote cluster + work demote ─
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "cr.json"
        kurz = str(Path(td) / "crk.json")
        cfg = Config.agent()
        am = AgentMemory.open(memory_path=str(path), kurz_path=kurz, cfg=cfg)
        token = f"CRYSTAL_{uuid.uuid4().hex[:8]}"
        base = f"[Holon] Ścieżka krystalizacji test {token}"
        am.remember(base, kind="fact")
        # exact near-dup (ten sam tekst) — remember scala; doklejamy drugi Item ręcznie
        emb2 = am.hm.embedder.encode(base, timestamp=time.time())
        am.hm.store.append(
            Item(
                id=str(uuid.uuid4()),
                content=base,
                embedding=emb2.tolist(),
                age=0,
                relevance=1.5,
                is_fact=True,
                cluster_size=1,
            )
        )
        # epizod z dużym cluster_size → promote (musi matchować --project Holon)
        e = Embedder(dim=cfg.dim, dict_path=kurz, time_dim=cfg.time_dim)
        ep_txt = f"[Holon] epizod do promote {token}"
        ep = e.encode(ep_txt, timestamp=time.time())
        am.hm.store.append(
            Item(
                id=str(uuid.uuid4()),
                content=ep_txt,
                embedding=ep.tolist(),
                age=2,
                relevance=0.8,
                cluster_size=3,
                is_fact=False,
            )
        )
        am.set_work("W1 crystal", project="Holon", max_active=5)
        am.set_work("W2 crystal", project="Holon", max_active=5)
        am.set_work("W3 crystal", project="Holon", max_active=5)
        before = len(am.hm.store)
        dry = am.crystallize(project="Holon", dry_run=True, max_active_work=1)
        check("crystallize_dry_run_ok", dry.get("ok") is True, str(dry)[:200])
        check(
            "crystallize_dry_run_no_shrink",
            len(am.hm.store) == before,
            f"before={before} after={len(am.hm.store)}",
        )
        rep = am.crystallize(
            project="Holon", dry_run=False, max_active_work=1, sim_threshold=0.85
        )
        check("crystallize_ok", rep.get("ok") is True, str(rep)[:200])
        n_tok = sum(1 for i in am.hm.store if token in (i.content or ""))
        check(
            "crystallize_merged_or_kept_token",
            n_tok >= 1,
            f"n_tok={n_tok} merged={rep.get('merged')}",
        )
        promoted_ok = any(
            i.is_fact and "epizod do promote" in (i.content or "")
            for i in am.hm.store
        )
        check(
            "crystallize_promotes_cluster",
            promoted_ok or int(rep.get("promoted_to_fact") or 0) >= 1,
            str(rep.get("promoted_samples")),
        )
        check(
            "crystallize_merged_dups",
            int(rep.get("merged") or 0) >= 1 or n_tok == 1,
            f"merged={rep.get('merged')} n_tok={n_tok}",
        )
        n_work_h = sum(
            1 for i in am.hm.store
            if i.is_work and "crystal" in (i.content or "").lower()
        )
        check(
            "crystallize_demotes_work",
            n_work_h <= 1,
            f"work={n_work_h} demoted={rep.get('demoted_work_to_fact')}",
        )
        check("crystallize_phi_reinforced", int(rep.get("phi_reinforced") or 0) >= 1,
              str(rep.get("phi_reinforced")))
        check("crystallize_save", am.save())

    # ── B2 lexical index + B4 on_remember hooks ──────────────────────────
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "lex.json"
        kurz = str(Path(td) / "lexk.json")
        cfg = Config.agent(lexical_index_force=True, lexical_index_min_store=10)
        am = AgentMemory.open(memory_path=str(path), kurz_path=kurz, cfg=cfg)
        hook_log: List[str] = []

        def _hook(item, **kw):
            hook_log.append(f"{kw.get('action')}:{item.content[:40]}")

        am.on_remember(_hook)
        needle = f"LEXNEEDLE_{uuid.uuid4().hex[:8]}"
        am.remember(f"[Holon] indeks lexical {needle} ścieżka B2", kind="fact")
        for i in range(40):
            am.remember(f"noise filler item number {i} xyz", kind="note")
        check("b2_lex_index_docs",
              am.lex_index.stats().get("docs", 0) >= 10,
              str(am.lex_index.stats()))
        check("b2_lex_should_prune", am._lex_should_prune() is True)
        pool = am._recall_pool(f"indeks {needle}")
        check(
            "b2_lex_pool_smaller_or_hits",
            len(pool) <= len(am.hm.store)
            and any(needle in (i.content or "") for i in pool),
            f"pool={len(pool)} store={len(am.hm.store)}",
        )
        ranked = am.recall(f"lexical {needle}", top_k=5)
        check(
            "b2_lex_recall_hits_needle",
            any(needle in i.content for _, i in ranked),
            " | ".join(i.content[:50] for _, i in ranked[:3]),
        )
        check("b4_hook_fired", len(hook_log) >= 1, str(hook_log[:3]))
        check("b4_hook_has_add_or_merge",
              any(x.startswith("add:") or x.startswith("merge:") for x in hook_log),
              str(hook_log[:5]))

        # B4 inbox watch
        from holon_remember_watch import RememberInbox
        inbox = Path(td) / "inbox.jsonl"
        line = json.dumps(
            {"content": f"[Holon] inbox watch {needle}", "kind": "fact"},
            ensure_ascii=False,
        ) + "\n"
        inbox.write_text(line, encoding="utf-8")
        w = RememberInbox(am, str(inbox), auto_save=False)
        wr = w.poll_once()
        check("b4_watch_processed", int(wr.get("processed") or 0) >= 1, str(wr))
        check(
            "b4_watch_in_store",
            any("inbox watch" in (i.content or "") for i in am.hm.store),
        )

    # ── B6 ablation smoke (pełny raport osobno: CLI ablation) ────────────
    ab = run_ablation_report()
    check("b6_ablation_ok", ab.get("ok") is True, str(ab.get("error") or ab.get("summary")))
    check(
        "b6_ablation_has_prism_and_flat",
        "prism" in (ab.get("profiles") or {}) and "flat" in (ab.get("profiles") or {}),
        str(list((ab.get("profiles") or {}).keys())),
    )

    return {"ok": ok, "checks": checks, "n_pass": sum(1 for c in checks if c["pass"]),
            "n_total": len(checks)}


def run_ablation_report() -> Dict[str, Any]:
    """B6: porównanie Config.agent() (prism) vs Config.flat() na temp store.

    Jedna komenda: ``python holon_agent_memory.py ablation``
    Metryki: recall hit@5, durable count, wall time remember+recall, use_prism.
    """
    profiles_out: Dict[str, Any] = {}
    ok = True
    scenarios = [
        ("prism", Config.agent()),
        ("flat", Config.flat(base="agent")),
    ]

    for name, cfg in scenarios:
        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / f"{name}.json"
            kurz = str(Path(td) / f"{name}_k.json")
            am = AgentMemory.open(memory_path=str(path), kurz_path=kurz, cfg=cfg)
            token = f"ABL_{name}_{uuid.uuid4().hex[:6]}"
            facts = [
                f"Ablation fact alpha {token} holon memory",
                f"Ablation fact beta KarmazynOs slab {token}",
                f"Preferencja: komunikacja po polsku {token}",
            ]
            for f in facts:
                am.remember(f, kind="fact")
            am.remember(f"Work thread ablation {token}", kind="work")
            for i in range(15):
                am.remember(f"episodic noise {name} {i}", kind="note")
            t_rem = time.perf_counter()
            ranked = am.recall(f"ablation fact alpha {token}", top_k=5)
            hit = any(token in i.content and "alpha" in i.content.lower()
                      for _, i in ranked)
            ranked2 = am.recall(f"KarmazynOs slab {token}", top_k=5)
            hit2 = any("slab" in (i.content or "").lower() for _, i in ranked2)
            t1 = time.perf_counter()
            st = am.stats()
            profiles_out[name] = {
                "use_prism": bool(getattr(cfg, "use_prism", True)),
                "profile": getattr(cfg, "profile", name),
                "store": st.get("store"),
                "facts": st.get("facts"),
                "work": st.get("work"),
                "recall_hit_alpha": bool(hit),
                "recall_hit_slab": bool(hit2),
                "top1": (ranked[0][1].content[:80] if ranked else ""),
                "ms_remember": round((t_rem - t0) * 1000, 2),
                "ms_total": round((t1 - t0) * 1000, 2),
            }
            if not (hit and hit2):
                ok = False

    prism = profiles_out.get("prism") or {}
    flat = profiles_out.get("flat") or {}
    summary = {
        "both_recall_ok": bool(
            prism.get("recall_hit_alpha") and prism.get("recall_hit_slab")
            and flat.get("recall_hit_alpha") and flat.get("recall_hit_slab")
        ),
        "prism_use_prism": prism.get("use_prism"),
        "flat_use_prism": flat.get("use_prism"),
        "ms_prism": prism.get("ms_total"),
        "ms_flat": flat.get("ms_total"),
        "note": (
            "flat = use_prism=False (ablacja PrismRouter); "
            "agent domyślnie prism. Oba powinny trafiać recall SE."
        ),
    }
    if summary["prism_use_prism"] is not True or summary["flat_use_prism"] is not False:
        ok = False
    if not summary["both_recall_ok"]:
        ok = False

    return {
        "ok": ok,
        "op": "ablation",
        "protocol": "holon-ablation-v1",
        "profiles": profiles_out,
        "summary": summary,
    }
