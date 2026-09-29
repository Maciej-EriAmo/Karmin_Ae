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
        self.assertTrue(a.use_bridge)
        self.assertFalse(c.use_bridge)
        self.assertFalse(Config.flat().use_bridge)
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


class TestMemoryPhysics(unittest.TestCase):
    def test_merge_noise_keeps_unit_norm(self):
        with tempfile.TemporaryDirectory() as td:
            am = AgentMemory.open(
                memory_path=str(Path(td) / "m.json"),
                profile="agent",
                use_settings=False,
            )
            a = am.remember("[Holon] ten sam fakt o freelist slab", kind="fact")
            b = am.remember("[Holon] ten sam fakt o freelist slab", kind="fact")
            self.assertEqual(a.id, b.id)
            n = float(np.linalg.norm(np.asarray(b.embedding, dtype=np.float32)))
            self.assertAlmostEqual(n, 1.0, places=5)

    def test_recall_penalizes_foreign_chamber(self):
        with tempfile.TemporaryDirectory() as td:
            am = AgentMemory.open(
                memory_path=str(Path(td) / "m.json"),
                profile="agent",
                use_settings=False,
            )
            am.remember("[Holon] unikalny token xyzzyholon freelist", kind="fact")
            am.remember("[Karmin_Sheet] unikalny token xyzzyholon freelist", kind="fact")
            am.touch_last_project("Holon")
            ranked = am.recall("xyzzyholon freelist", top_k=5)
            self.assertGreaterEqual(len(ranked), 2)
            by_tag = {
                am._project_tag(it.content): score for score, it in ranked
            }
            self.assertIn("Holon", by_tag)
            self.assertIn("Karmin_Sheet", by_tag)
            self.assertGreater(by_tag["Holon"], by_tag["Karmin_Sheet"])

    def test_crystallize_skips_cross_chamber_unless_flag(self):
        with tempfile.TemporaryDirectory() as td:
            am = AgentMemory.open(
                memory_path=str(Path(td) / "m.json"),
                profile="agent",
                use_settings=False,
            )
            am.remember("[Alpha] wspólny temat slab freelist path", kind="fact")
            am.remember("[Beta] wspólny temat slab freelist path", kind="fact")
            before = len(am.hm.store)
            rep = am.crystallize(project="", dry_run=False, cross_project_merge=False)
            self.assertTrue(rep.get("ok"))
            self.assertEqual(len(am.hm.store), before)
            tagged = [
                i for i in am.hm.store
                if am._project_tag(i.content) in ("Alpha", "Beta")
            ]
            self.assertEqual(len(tagged), 2)

    def test_entanglement_singleton_work_ok(self):
        with tempfile.TemporaryDirectory() as td:
            am = AgentMemory.open(
                memory_path=str(Path(td) / "m.json"),
                profile="agent",
                use_settings=False,
            )
            am.remember("[Holon] fakt A o protokole SE boot", kind="fact")
            am.remember("[Holon] fakt B o komorach prefix tag", kind="fact")
            am.remember("[Holon] fakt C o crystallize merge", kind="fact")
            am.remember("[Holon] work: dopracuj metrykę entangle", kind="work")
            rep = am.entanglement_score("Holon")
            self.assertTrue(rep.get("ok"), rep)
            self.assertEqual(rep["work_n"], 1)
            self.assertIsNone(rep["within_work_sim"])
            self.assertIsInstance(rep["within_facts_sim"], float)
            self.assertIsInstance(rep["entanglement"], float)


class TestMemoryBugfixes(unittest.TestCase):
    def _am(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        return AgentMemory.open(
            memory_path=str(Path(td.name) / "m.json"),
            profile="agent",
            use_settings=False,
        )

    def test_crystallize_keeps_one_work_per_chamber(self):
        am = self._am()
        h = am.remember("[Holon] work holon alpha unikalny", kind="work")
        k = am.remember("[Karmazyn] work karmazyn beta unikalny", kind="work")
        k.created_at = time.time() + 500
        rep = am.crystallize(
            project="", dry_run=False, max_active_work=1, reinforce_phi=False
        )
        alive = [i for i in am.hm.store if i.is_work]
        self.assertEqual(rep["demoted_work_to_fact"], 0)
        self.assertEqual({i.id for i in alive}, {h.id, k.id})

    def test_remember_shared_window_stays_two_facts(self):
        am = self._am()
        prefix = "[Holon] " + ("WSPOLNY PREFIKS " * 6)
        a = am.remember(prefix + "KONIEC-A unikalne-a", kind="fact")
        b = am.remember(prefix + "KONIEC-B unikalne-b", kind="fact")
        self.assertNotEqual(a.id, b.id)
        rep = am.crystallize(project="Holon", dry_run=False, reinforce_phi=False)
        self.assertEqual(rep["merged"], 0)
        texts = [i.content for i in am.hm.store]
        self.assertTrue(any("KONIEC-A" in t for t in texts))
        self.assertTrue(any("KONIEC-B" in t for t in texts))

    def test_remember_true_extension_still_merges(self):
        am = self._am()
        base = "[Holon] " + ("dokladnie ten sam fakt o slabie " * 2)
        a = am.remember(base, kind="fact")
        b = am.remember(base + " i dopisek na koncu", kind="fact")
        self.assertEqual(a.id, b.id)
        self.assertIn("dopisek", b.content)

    def test_remember_same_moment_does_not_fuse_distinct(self):
        am = self._am()
        a = am.remember(
            "[Holon] swiezy odrebny temat alfa numer0 bez wspolnego ogona",
            kind="fact",
        )
        b = am.remember(
            "[Holon] swiezy odrebny temat delta numer3 bez wspolnego ogona",
            kind="fact",
        )
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(am.hm.store), 2)

    def test_set_work_text_tag_wins_over_project_arg(self):
        am = self._am()
        am.set_work("stary holon", project="Holon")
        am.set_work("stary karmazyn", project="Karmazyn")
        am.set_work("[Holon] nowy holon inny tekst", project="Karmazyn")
        works = [i for i in am.hm.store if i.is_work]
        tags = [am._project_tag(i.content) for i in works]
        self.assertEqual(tags.count("Holon"), 1)
        self.assertEqual(tags.count("Karmazyn"), 1)
        self.assertTrue(any("nowy holon" in (i.content or "") for i in works))
        self.assertEqual(am.read_hammer(), "Holon")

    def test_restore_skips_shared_prefix_sibling(self):
        am = self._am()
        prefix = "[Holon] " + ("WSPOLNY PREFIKS " * 6)
        b = am.remember(prefix + "KONIEC-B unikalne-b", kind="fact")
        a = am.remember(prefix + "KONIEC-A unikalne-a", kind="fact")
        am.hm.store = [b, a]
        ok = am._restore_chamber_work(
            "Holon",
            {"work_id": "brak", "work": prefix + "KONIEC-A unikalne-a"},
        )
        self.assertTrue(ok)
        self.assertTrue(a.is_work)
        self.assertFalse(b.is_work)

    def test_turn_does_not_merge_across_chambers(self):
        cfg = Config.chat()
        with tempfile.TemporaryDirectory() as td:
            hm = HoloMem(
                Embedder(dim=cfg.dim, time_dim=cfg.time_dim),
                cfg,
                str(Path(td) / "c.json"),
            )
            hm.start_session()
            body = "identyczny fakt komory o slabie freelist " * 3
            hm.turn("[Holon] " + body)
            hm.turn("[Karmazyn] " + body)
            texts = [i.content or "" for i in hm.store]
            self.assertEqual(len(hm.store), 2)
            self.assertTrue(any(t.startswith("[Holon]") for t in texts))
            self.assertTrue(any(t.startswith("[Karmazyn]") for t in texts))

    def test_set_work_without_project_keeps_other_chamber(self):
        am = self._am()
        am.set_work("watek holon pierwszy", project="Holon")
        am.set_work("watek karmazyn osobny", project="Karmazyn")
        am.set_work("[Holon] nowy watek holon zupelnie inny")
        tags = [am._project_tag(i.content) for i in am.hm.store if i.is_work]
        self.assertEqual(tags.count("Holon"), 1)
        self.assertEqual(tags.count("Karmazyn"), 1)
        self.assertIn("nowy watek holon", " ".join(i.content for i in am.hm.store if i.is_work))

    def test_set_work_untagged_does_not_demote_chambers(self):
        am = self._am()
        am.set_work("watek holon zostaje", project="Holon")
        am.set_work("luzny watek bez tagu numer jeden")
        am.set_work("luzny watek bez tagu numer dwa")
        holon = [
            i for i in am.hm.store
            if i.is_work and am._match_project(i.content, "Holon")
        ]
        bare = [
            i for i in am.hm.store
            if i.is_work and not am._project_tag(i.content or "")
        ]
        self.assertEqual(len(holon), 1)
        self.assertEqual(len(bare), 1)
        self.assertIn("numer dwa", bare[0].content)

    def test_turn_keeps_diverging_tails_and_merges_exact(self):
        cfg = Config.chat()
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "m.json")
            hm = HoloMem(
                Embedder(dim=cfg.dim, time_dim=cfg.time_dim),
                cfg,
                path,
            )
            hm.start_session()
            prefix = "WSPOLNY PREFIKS " * 6
            hm.turn(prefix + "KONIEC-A unikalne-a")
            hm.turn(prefix + "KONIEC-B unikalne-b")
            texts = [i.content or "" for i in hm.store]
            self.assertTrue(any("KONIEC-A" in t for t in texts))
            self.assertTrue(any("KONIEC-B" in t for t in texts))
            hm.turn("dokladnie ta sama tura o slabie freelist")
            hm.turn("dokladnie ta sama tura o slabie freelist")
            same = [t for t in (i.content or "" for i in hm.store) if "slabie freelist" in t]
            self.assertEqual(len(same), 1)
            hm2 = HoloMem(
                Embedder(dim=cfg.dim, time_dim=cfg.time_dim),
                cfg,
                str(Path(td) / "m2.json"),
            )
            hm2.start_session()
            hm2.after_turn(prefix + "KONIEC-A unikalne-a", "odpowiedz alfa")
            hm2.after_turn(prefix + "KONIEC-B unikalne-b", "odpowiedz beta")
            tails = [i.content or "" for i in hm2.store]
            self.assertTrue(any("KONIEC-A" in t for t in tails))
            self.assertTrue(any("KONIEC-B" in t for t in tails))

    def test_set_work_after_merge_keeps_one(self):
        am = self._am()
        stem = "[Holon] " + ("abcde " * 20)
        old = am.set_work(stem, project="Holon")
        old.created_at = 1000.0
        am.remember("[Holon] zupelnie inny watek numer 777", kind="work")
        am.set_work(stem + "DOPISEK NOWY", project="Holon")
        works = [i for i in am.hm.store if i.is_work]
        self.assertEqual(len(works), 1)
        self.assertIn("DOPISEK", works[0].content)

    def test_restore_ignores_foreign_quote(self):
        am = self._am()
        am.remember(
            "[Karmazyn] cytat cudzej komory: TOKEN-RESTORE-XYZ reszta",
            kind="fact",
        )
        ok = am._restore_chamber_work(
            "Holon",
            {"work_id": "brak-takiego-id", "work": "TOKEN-RESTORE-XYZ"},
        )
        self.assertFalse(ok)
        self.assertEqual(sum(1 for i in am.hm.store if i.is_work), 0)

    def test_restore_same_chamber_by_prefix(self):
        am = self._am()
        item = am.remember(
            "[Holon] TOKEN-RESTORE-XYZ dluzszy opis worku komory",
            kind="fact",
        )
        ok = am._restore_chamber_work(
            "Holon",
            {
                "work_id": "brak-takiego-id",
                "work": "[Holon] TOKEN-RESTORE-XYZ dluzszy opis worku komory",
            },
        )
        self.assertTrue(ok)
        self.assertTrue(item.is_work)
        self.assertEqual(am._project_tag(item.content), "Holon")

    def test_recall_pool_keeps_old_unique_hit(self):
        am = self._am()
        am.hm.cfg.lexical_index_min_store = 1
        am.hm.cfg.lexical_index_max_candidates = 3
        oldf = am.remember("[Holon] archiwum ZEGARQQQ999 tylko tutaj", kind="fact")
        oldf.age = 90
        for i in range(8):
            it = am.remember(
                f"[Holon] qwerty{i} zxcv{i * 17} plmok{i * 13} unik{i}",
                kind="fact",
            )
            it.age = 0
        pool = am._recall_pool("ZEGARQQQ999")
        self.assertTrue(any(i.id == oldf.id for i in pool))
        ranked = am.recall("ZEGARQQQ999", top_k=5)
        self.assertTrue(any(it.id == oldf.id for _, it in ranked))


if __name__ == "__main__":
    unittest.main()
