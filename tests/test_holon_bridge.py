# -*- coding: utf-8 -*-
"""Testy BridgeStack + Prism teleport (bez Embeddera)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holon_bridge import (
    BridgeStack,
    bridge_energy_importance,
    bridge_home_turf_quick,
    load_bridge_module,
    prism_wins_demo,
)


def _bridge_available() -> bool:
    try:
        load_bridge_module()
        return True
    except (FileNotFoundError, ImportError):
        return False


@unittest.skipUnless(_bridge_available(), "transform.py Bridge niedostępny")
class TestBridgeStack(unittest.TestCase):
    def test_forward_without_embedder(self):
        import torch

        stack = BridgeStack(d_model=32, n_heads=2, n_layers=1, n_classes=8, phi_levels=3)
        x = torch.randn(1, 12, 32)
        tracer = torch.rand(1, 12, 1)
        fwd = stack.forward_tokens(x, tracer, pool="cls")
        self.assertEqual(fwd.pattern.shape, (32,))
        self.assertAlmostEqual(float(np.linalg.norm(fwd.pattern)), 1.0, places=4)
        self.assertEqual(tuple(fwd.logits.shape), (1, 8))

    def test_teleport_to_phi_levels(self):
        import torch

        stack = BridgeStack(d_model=32, n_heads=2, n_layers=1, phi_levels=3)
        x = torch.randn(8, 32)
        tracer = torch.linspace(0, 2, 8)
        fwd, tele = stack.bridge_then_prism(x, tracer, importance=2.2, pool="mean")
        self.assertEqual(len(tele.updates), 3)
        self.assertEqual(len(tele.weights), 3)
        self.assertAlmostEqual(float(tele.weights.sum()), 1.0, places=5)
        self.assertTrue(0 <= tele.dominant_level < 3)
        self.assertEqual(fwd.pattern.shape, (32,))


class TestPrismWins(unittest.TestCase):
    def test_prism_wins_demo_flags(self):
        rep = prism_wins_demo(phi_levels=3)
        self.assertTrue(rep["ok"])
        self.assertTrue(rep["prism_wins"], rep)
        self.assertGreater(rep["prism_phase_spread_high"], 1e-4)
        self.assertGreater(rep["prism_entropy_high"], rep["flat_entropy_high"])


class TestBridgeEnergyImportance(unittest.TestCase):
    def test_multi_structured_boosts_over_flat(self):
        lo, hi = 0.8, 2.6
        base = 1.0
        flat = np.ones(16, dtype=np.float64)
        # wielowymiarowy: kilka ostrych pików energii (Bridge turf)
        multi = np.array(
            [3.0, 0.01, 0.01, 2.5, 0.01, 0.02, 2.0] + [0.01] * 9,
            dtype=np.float64,
        )
        imp_flat, m_flat = bridge_energy_importance(base, flat, (lo, hi))
        imp_multi, m_multi = bridge_energy_importance(base, multi, (lo, hi))
        self.assertGreater(m_multi["ok"], 0.5)
        self.assertGreater(imp_multi, imp_flat + 0.1)
        self.assertGreater(m_multi["structure"], m_flat["structure"])
        self.assertGreaterEqual(imp_multi, lo)
        self.assertLessEqual(imp_multi, hi)

    def test_routes_prism_p_differently(self):
        from holon_holography import PrismRouter, PrismConfig

        pr = PrismRouter(PrismConfig(num_levels=3))
        pat = np.random.randn(64).astype(np.float32)
        pat /= np.linalg.norm(pat) + 1e-8
        flat = np.ones(20)
        multi = np.linspace(0.01, 3.0, 20) ** 2
        imp_f, _ = bridge_energy_importance(1.0, flat)
        imp_m, _ = bridge_energy_importance(1.0, multi)
        _, p_f, _ = pr.route(imp_f, pat)
        _, p_m, _ = pr.route(imp_m, pat)
        tv = 0.5 * float(np.abs(np.asarray(p_f) - np.asarray(p_m)).sum())
        self.assertGreater(tv, 0.01, f"tv={tv} p_f={p_f} p_m={p_m}")


@unittest.skipUnless(_bridge_available(), "transform.py Bridge niedostępny")
class TestBridgeHomeTurf(unittest.TestCase):
    def test_bridge_beats_softmax_at_600(self):
        # <~200 kroków bywa flaky; 600 jak w BRIDGE_TRANSFORMER_RESULTS
        rep = bridge_home_turf_quick(steps=600, seed=11)
        self.assertTrue(rep.get("ok"), rep)
        self.assertGreater(rep["acc_bridge_transform_py"], 0.5)
        self.assertGreater(
            rep["acc_bridge_transform_py"], rep["acc_softmax"] + 0.2, rep
        )


@unittest.skipUnless(_bridge_available(), "transform.py Bridge niedostępny")
class TestBridgeEnabledInHoloMem(unittest.TestCase):
    def test_phi_update_sets_bridge_on(self):
        import tempfile
        import time
        from holon_config import Config
        from holon_embedder import Embedder
        from holon_holomem import HoloMem
        from holon_item import Item
        import uuid

        cfg = Config.agent(bridge_calibrate_steps=120, bridge_d_model=32,
                           bridge_n_heads=2, bridge_n_layers=1)
        self.assertTrue(cfg.use_bridge)
        with tempfile.TemporaryDirectory() as td:
            emb = Embedder(dim=cfg.dim, time_dim=cfg.time_dim)
            hm = HoloMem(emb, cfg, str(Path(td) / "m.json"))
            hm.start_session()
            items = []
            for i, text in enumerate(
                ("[Holon] alpha freelist", "[Holon] beta slab path",
                 "[Holon] gamma chamber tag")
            ):
                e = emb.encode(text, timestamp=time.time())
                it = Item(
                    id=str(uuid.uuid4()), content=text, embedding=e.tolist(),
                    age=0, is_fact=True, relevance=1.5 + 0.1 * i,
                )
                hm.store.append(it)
                items.append(it)
            hm._update_phi(items)
            self.assertEqual(hm._bridge_status, "on", hm._bridge_status)
            st = hm.stats()
            self.assertTrue(st.get("bridge_mode"))
            self.assertEqual(st.get("bridge_status"), "on")
            self.assertTrue(st.get("bridge_energy_to_importance"))
            be = st.get("bridge_energy") or {}
            self.assertGreater(float(be.get("ok", 0)), 0.5, be)
            self.assertIn("imp_out", be)


if __name__ == "__main__":
    unittest.main()
