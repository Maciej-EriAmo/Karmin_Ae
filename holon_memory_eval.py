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

    return {"ok": ok, "checks": checks, "n_pass": sum(1 for c in checks if c["pass"]),
            "n_total": len(checks)}
