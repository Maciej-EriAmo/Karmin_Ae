# -*- coding: utf-8 -*-
"""Most Holon ↔ Karmin_DB (B3 zamiast SQLite). Skip gdy brak DBase."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holon_backend_karmin import (
    SNAPSHOT_FORMAT,
    KarminMirror,
    describe_karmin_slot,
    karmin_available,
)


@unittest.skipUnless(karmin_available(), "Karmin_DB / DBase niedostępny")
class TestKarminBridge(unittest.TestCase):
    def test_slot_describes_not_sqlite(self):
        d = describe_karmin_slot()
        self.assertTrue(d["available"])
        self.assertIn("Karmin", d["replaces_plan"])

    def test_upsert_fetch_snapshot_roundtrip(self):
        m = KarminMirror.open()

        class T:
            pass

        it = T()
        it.id = uuid.uuid4().hex
        it.content = f"Karmin bridge fact {it.id[:8]}"
        it.is_fact = True
        it.is_work = False
        it.is_insight = False
        it.is_reminder = False
        it.created_at = 1_700_000_000.0
        it.age = 0
        it.relevance = 1.5
        it.embedding = [0.1, 0.2, 0.3]

        bid = m.upsert_item(it)
        self.assertTrue(bid.startswith("h_"))
        rows = m.fetch_rows(kind="fact")
        self.assertTrue(any(it.content in str(r.get("content")) for r in rows))

        with tempfile.TemporaryDirectory() as td:
            snap = Path(td) / "s.holon-karmin.json"
            m.export_snapshot(snap)
            data = json.loads(snap.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], SNAPSHOT_FORMAT)
            self.assertGreaterEqual(data["n"], 1)

            m2 = KarminMirror.open()
            n = m2.import_snapshot(snap)
            self.assertGreaterEqual(n, 1)
            rows2 = m2.fetch_rows()
            self.assertTrue(
                any(it.content in str(r.get("content")) for r in rows2)
            )

    def test_agent_export_import(self):
        from holon_agent_memory import AgentMemory

        with tempfile.TemporaryDirectory() as td:
            mem_path = str(Path(td) / "m.json")
            snap = str(Path(td) / "out.holon-karmin.json")
            am = AgentMemory.open(memory_path=mem_path)
            token = f"KBRIDGE_{uuid.uuid4().hex[:8]}"
            am.remember(f"Durable via karmin {token}", kind="fact")
            am.save()
            rep = am.karmin_export(snap)
            self.assertTrue(rep.get("ok"), rep)
            self.assertTrue(Path(snap).is_file())

            am2 = AgentMemory.open(memory_path=str(Path(td) / "m2.json"))
            imp = am2.karmin_import_merge(snap)
            self.assertTrue(imp.get("ok"), imp)
            self.assertTrue(
                any(token in (i.content or "") for i in am2.hm.store)
            )


if __name__ == "__main__":
    unittest.main()
