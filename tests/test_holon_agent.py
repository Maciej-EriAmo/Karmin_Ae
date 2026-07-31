# -*- coding: utf-8 -*-
"""Lekkie testy domknięcia Holon agent + prompt v2 (bez LLM)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holon_prompts import (
    DEFAULT_SYSTEM,
    DEFAULT_SYSTEM_AWARE,
    format_internal_state,
)
from holon_config import Config
from holon_memory import PersistentMemory
from holon_item import Item
from holon_embedder import Embedder
from holon_holomem import HoloMem
from holon_agent_memory import AgentMemory
import uuid


class TestHealthyTemporal(unittest.TestCase):
    def test_pastness_labels(self):
        from holon_aii import TimeDecay
        self.assertIn("min", TimeDecay.format_pastness(0.5))
        self.assertIn("d", TimeDecay.format_pastness(48))
        self.assertIn("PRZESZŁOŚĆ", TimeDecay.wake_message(100.0, 10, 5, 0.4))

    def test_aii_relaxes_after_long_gap(self):
        from holon_aii import AIIState
        a = AIIState(None)
        a.emotion = "strach"
        a.vacuum_signal = -1.0
        a.focus_active = True
        a.relax_toward_baseline(400.0, half_life_hours=72.0)
        self.assertEqual(a.emotion, "neutral")
        self.assertLess(abs(a.vacuum_signal), 0.05)
        self.assertFalse(a.focus_active)


class TestPromptsV2(unittest.TestCase):
    def test_core_has_truth_and_priority(self):
        self.assertIn("Nie wymyślaj faktów", DEFAULT_SYSTEM)
        self.assertIn("Najpierw treść merytoryczna", DEFAULT_SYSTEM)
        self.assertNotIn("CRITICAL DIRECTIVES", DEFAULT_SYSTEM)
        self.assertTrue(
            "CZAS" in DEFAULT_SYSTEM or "przeszłość" in DEFAULT_SYSTEM.lower())

    def test_aware_has_tools(self):
        self.assertIn("zapisz:", DEFAULT_SYSTEM_AWARE)
        self.assertIn("Nie wymyślaj faktów", DEFAULT_SYSTEM_AWARE)

    def test_internal_state_calm(self):
        aii = type("A", (), {
            "emotion": "neutral", "vacuum_signal": 0.0, "focus_active": False,
        })()
        s = format_internal_state(aii)
        self.assertIn("STAN WEWNĘTRZNY", s)
        self.assertIn("teatralnego", s)


class TestConfigProfiles(unittest.TestCase):
    def test_agent_vs_chat(self):
        a, c = Config.agent(), Config.chat()
        self.assertEqual(a.profile, "agent")
        self.assertEqual(c.profile, "chat")
        self.assertGreater(a.store_decay_hours, c.store_decay_hours)
        self.assertFalse(Config.flat().use_prism)


class TestDurableLoad(unittest.TestCase):
    def test_fact_survives_long_absence(self):
        cfg = Config.agent()
        emb = Embedder(dim=cfg.dim, dict_path=str(
            Path(tempfile.gettempdir()) / "holon_test_kurz.json"),
            time_dim=cfg.time_dim)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "m.json"
            hm = HoloMem(emb, cfg, str(path))
            hm.start_session()
            text = "Fakt testowy durable unit"
            e = emb.encode(text, timestamp=time.time())
            hm.store.append(Item(
                id=str(uuid.uuid4()), content=text, embedding=e.tolist(),
                age=0, is_fact=True, relevance=1.5))
            ep = emb.encode("ephemeral noise xyz", timestamp=time.time())
            hm.store.append(Item(
                id=str(uuid.uuid4()), content="ephemeral noise xyz",
                embedding=ep.tolist(), age=5, is_fact=False, relevance=0.2))
            ok = hm.memory.save(
                hm.phi, hm.store, hm.turns, cfg,
                hm.aii.to_dict(), hm.phi_stability.tolist(),
                hm.W_time, hm.W_gen)
            self.assertTrue(ok)

            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["timestamp"] = time.time() - 200 * 24 * 3600
            path.write_text(json.dumps(raw), encoding="utf-8")

            res = PersistentMemory(str(path)).load(cfg)
            contents = [i.content for i in res["store"]]
            self.assertTrue(any("durable unit" in c for c in contents))
            self.assertFalse(any("ephemeral noise" in c for c in contents))


class TestAgentDedupe(unittest.TestCase):
    def test_remember_dedupes_exact(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "a.json")
            am = AgentMemory.open(memory_path=path)
            am.remember("Unikalny fakt dedupe ABC", kind="fact")
            am.remember("Unikalny fakt dedupe ABC", kind="fact")
            n = sum(1 for i in am.hm.store
                    if "dedupe ABC" in i.content)
            self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
