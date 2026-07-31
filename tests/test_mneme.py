# -*- coding: utf-8 -*-
"""Mneme-L + thin graph over Holon."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holon_agent_memory import AgentMemory
from holon_mneme import Mneme


class TestMneme(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.path = str(Path(self.td.name) / "m.json")
        self.am = AgentMemory.open(memory_path=self.path)
        self.m = Mneme(self.am)

    def tearDown(self):
        self.td.cleanup()

    def test_hold_recall(self):
        r = self.m.execute('HOLD fact "Mneme alpha token XYZ" PROJECT Holon')[0]
        self.assertTrue(r.ok)
        self.assertEqual(r.hits[0]["kind"], "fact")
        self.assertIn("temu", r.hits[0]["when"])
        r2 = self.m.recall("alpha token XYZ", top=3, project="Holon")
        self.assertTrue(r2.ok)
        self.assertTrue(any("XYZ" in h["content"] for h in r2.hits))

    def test_link_walk_trace(self):
        a = self.m.hold("fact", "Node A unique aaa", project="T")
        b = self.m.hold("fact", "Node B unique bbb", project="T")
        ida, idb = a.hits[0]["id"], b.hits[0]["id"]
        lr = self.m.link(ida, "about", idb)
        self.assertTrue(lr.ok)
        tr = self.m.trace(ida, depth=1)
        self.assertTrue(any(idb.startswith(h["id"][:8]) or h["id"] == idb for h in tr.hits))
        w = self.m.walk(ida, ["about"], depth=1)
        self.assertTrue(w.ok)
        self.assertGreaterEqual(len(w.hits), 2)

    def test_near_and_focus(self):
        self.m.hold("fact", "vector neighbor one", project="V")
        self.m.hold("fact", "vector neighbor two", project="V")
        self.m.focus("PROJECT V")
        n = self.m.near("vector neighbor", top=3)
        self.assertTrue(n.ok)
        self.assertTrue(len(n.hits) >= 1)

    def test_unrecognized(self):
        r = self.m.execute("SELECT * FROM memory")[0]
        self.assertFalse(r.ok)


if __name__ == "__main__":
    unittest.main()
