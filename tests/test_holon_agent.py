# -*- coding: utf-8 -*-
"""Lekkie testy domknięcia Holon agent + prompt v2 (bez LLM)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

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
        # SE default = krotki handoff, 1 work
        self.assertEqual(a.handoff_max_work, 1)
        self.assertLessEqual(a.handoff_max_facts, 4)
        self.assertEqual(a.set_work_max_active, 1)


class TestHandoffCompact(unittest.TestCase):
    def test_compact_one_work_and_short_lists(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "m.json")
            am = AgentMemory.open(memory_path=path, profile="agent", use_settings=False)
            # set_work juz demotuje — dwa work: zostaje 1
            am.set_work("first thread", project="T")
            am.set_work("second thread wins", project="T")
            am.remember("[T] fact alpha durable", kind="fact")
            am.remember("[T] fact beta durable", kind="fact")
            am.remember("[T] fact gamma durable", kind="fact")
            am.remember("[T] fact delta durable", kind="fact")
            am.save()
            works = [i for i in am.hm.store if i.is_work]
            self.assertEqual(len(works), 1)
            # recznie dorzuc drugi work (omijajac set_work) i enforce
            am.remember("[T] stale work item", kind="work")
            rep = am.enforce_max_work(project="T", max_active=1)
            self.assertEqual(rep["kept"], 1)
            self.assertGreaterEqual(rep["demoted"], 1)
            h = am.handoff(project="T", compact=True, include_digest=False)
            self.assertTrue(h.get("compact"))
            self.assertLessEqual(len(h.get("active_work") or []), 1)
            self.assertLessEqual(len(h.get("key_facts") or []), 3)
            self.assertEqual(h.get("chronicle") or [], [])
            self.assertEqual(h.get("recent_done") or [], [])
            acts = h.get("recommended_actions") or []
            self.assertGreaterEqual(len(acts), 1)
            self.assertLessEqual(len(acts), 3)
            for w in h.get("active_work") or []:
                self.assertLessEqual(len(w.get("content") or ""), 280)


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


class TestHashEmbedder(unittest.TestCase):
    def test_fallback_is_deterministic_not_noise(self):
        from holon_embedder import Embedder, KURZ_IS_FALLBACK

        e1 = Embedder(dim=64, time_dim=4)
        e2 = Embedder(dim=64, time_dim=4)
        a = e1._kurz.encode("slab freelist kentry")
        b = e2._kurz.encode("slab freelist kentry")
        c = e1._kurz.encode("przepis na bigos z kapusta")
        near = e1._kurz.encode("slab freelist")

        def cos(x, y):
            x = np.asarray(x, dtype=np.float32)
            y = np.asarray(y, dtype=np.float32)
            return float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))

        self.assertGreater(cos(a, b), 0.999)
        self.assertGreater(cos(a, near), cos(a, c))
        # timestamp nie psuje content-wektora (cache + hash)
        t0 = 1_700_000_000.0
        u = e1.encode("slab freelist kentry", timestamp=t0)
        v = e1.encode("slab freelist kentry", timestamp=t0)
        self.assertGreater(cos(u, v), 0.999)
        if KURZ_IS_FALLBACK:
            self.assertEqual(e1.backend, "hash")


class TestProjectChambers(unittest.TestCase):
    def test_enforce_empty_keeps_one_work_per_project(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "m.json")
            am = AgentMemory.open(
                memory_path=path, profile="agent", use_settings=False
            )
            am.set_work("A work", project="Alpha")
            am.set_work("B work", project="Beta")
            rep = am.enforce_max_work(project="", max_active=1)
            works = [i for i in am.hm.store if i.is_work]
            self.assertEqual(len(works), 2)
            self.assertEqual(rep["chambers"], 2)
            self.assertEqual(rep["demoted"], 0)

    def test_enter_snapshots_previous_and_keeps_other_chamber(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "m.json")
            am = AgentMemory.open(
                memory_path=path, profile="agent", use_settings=False
            )
            am.set_work("A thread", project="Alpha")
            am.remember("[Alpha] fact A durable", kind="fact")
            am.enter("Alpha")
            rep = am.enter("Beta")
            self.assertTrue(rep["switched"])
            self.assertEqual(rep["previous"], "Alpha")
            am.set_work("B thread", project="Beta")
            am.remember("[Beta] fact B durable", kind="fact")
            ch = am.read_chamber("Alpha")
            self.assertIn("A thread", ch.get("work") or "")
            self.assertEqual(sum(1 for i in am.hm.store if i.is_work), 2)
            h = am.handoff(project="Beta", compact=True, include_digest=False)
            self.assertIn("Alpha", h.get("chambers") or [])
            self.assertIn("Beta", h.get("chambers") or [])

    def test_restore_work_from_chamber_if_demoted(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "m.json")
            am = AgentMemory.open(
                memory_path=path, profile="agent", use_settings=False
            )
            am.set_work("Only Alpha", project="Alpha")
            am.enter("Alpha")
            for i in am.hm.store:
                if i.is_work:
                    i.is_work = False
                    i.is_fact = True
            self.assertEqual(sum(1 for i in am.hm.store if i.is_work), 0)
            rep = am.enter("Alpha")
            self.assertTrue(rep["restored_work"])
            self.assertEqual(
                sum(
                    1
                    for i in am.hm.store
                    if i.is_work and am._match_project(i.content, "Alpha")
                ),
                1,
            )

    def test_close_writes_chamber(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "m.json")
            am = AgentMemory.open(
                memory_path=path, profile="agent", use_settings=False
            )
            am.close(work="next X", fact="did Y", project="Zed")
            ch = am.read_chamber("Zed")
            self.assertIn("next X", ch.get("work") or "")
            self.assertTrue(any("did Y" in f for f in (ch.get("facts") or [])))
            self.assertEqual(am.read_last_project(), "Zed")


class TestChamberIsolation(unittest.TestCase):
    def test_match_is_prefix_not_substring(self):
        with tempfile.TemporaryDirectory() as td:
            am = AgentMemory.open(
                memory_path=str(Path(td) / "m.json"),
                profile="agent",
                use_settings=False,
            )
            am.remember("[lore-editor] Holon wspomniany przy okazji", kind="fact")
            am.remember("[Holon] tylko protokół SE", kind="fact")
            h = am.handoff(project="Holon", compact=True, include_digest=False)
            texts = " ".join(x.get("content") or "" for x in (h.get("key_facts") or []))
            self.assertIn("protokół SE", texts)
            self.assertNotIn("lore-editor", texts)

    def test_no_merge_across_chambers(self):
        with tempfile.TemporaryDirectory() as td:
            am = AgentMemory.open(
                memory_path=str(Path(td) / "m.json"),
                profile="agent",
                use_settings=False,
            )
            a = am.remember("[Alpha] ten sam temat slab freelist", kind="fact")
            b = am.remember("[Beta] ten sam temat slab freelist", kind="fact")
            self.assertNotEqual(a.id, b.id)
            tagged = [
                i
                for i in am.hm.store
                if i.is_fact and am._project_tag(i.content) in ("Alpha", "Beta")
            ]
            self.assertEqual(len(tagged), 2)

    def test_remember_stamps_project(self):
        with tempfile.TemporaryDirectory() as td:
            am = AgentMemory.open(
                memory_path=str(Path(td) / "m.json"),
                profile="agent",
                use_settings=False,
            )
            it = am.remember("goły tekst bez tagu", kind="fact", project="AstraEdit")
            self.assertEqual(am._project_tag(it.content), "AstraEdit")

    def test_separate_moves_sheet_out_of_karminql(self):
        with tempfile.TemporaryDirectory() as td:
            am = AgentMemory.open(
                memory_path=str(Path(td) / "m.json"),
                profile="agent",
                use_settings=False,
            )
            am.remember("[KarminQL] Karmin_Sheet Faza 3 JEST", kind="fact")
            am.remember("[KarminQL] silnik SCAL PO w DBase", kind="fact")
            dry = am.separate_chambers(dry_run=True)
            self.assertEqual(dry["moved"], 1)
            self.assertEqual(am._project_tag(am.hm.store[0].content), "KarminQL")
            live = am.separate_chambers(dry_run=False)
            self.assertEqual(live["moved"], 1)
            sheet = [i for i in am.hm.store if am._match_project(i.content, "Karmin_Sheet")]
            ql = [i for i in am.hm.store if am._match_project(i.content, "KarminQL")]
            self.assertEqual(len(sheet), 1)
            self.assertEqual(len(ql), 1)
            h = am.handoff(project="KarminQL", compact=True, include_digest=False)
            blob = " ".join(x.get("content") or "" for x in (h.get("key_facts") or []))
            self.assertIn("SCAL PO", blob)
            self.assertNotIn("Faza 3", blob)


class TestHolonItemInject(unittest.TestCase):
    def test_inject_note_uses_real_item(self):
        from notes_manager import NotesManager, NOTE_PREFIX

        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "m.json")
            notes_dir = str(Path(td) / "notes")
            am = AgentMemory.open(
                memory_path=path, profile="agent", use_settings=False
            )
            nm = NotesManager(notes_dir=notes_dir)
            note = nm.create(title="Test nota", content="tresc notatki hash")
            nm.inject_note(am.hm, note)
            found = [i for i in am.hm.store if NOTE_PREFIX in (i.content or "")]
            self.assertEqual(len(found), 1)
            self.assertTrue(hasattr(found[0], "emb_np"))
            self.assertGreater(float(np.linalg.norm(found[0].emb_np())), 0.0)


if __name__ == "__main__":
    unittest.main()
