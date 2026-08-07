# -*- coding: utf-8 -*-
"""Testy konfiguratora / holon_settings."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from holon_settings import (
    PRESETS,
    apply_preset,
    doctor,
    load_config,
    load_settings,
    normalize_lang,
    normalize_settings,
    preset_text,
    resolve_ui_lang,
    save_settings,
    sanitize_overrides,
)
from holon_configure import main as configure_main


class TestSettings(unittest.TestCase):
    def test_sanitize_drops_unknown(self):
        o = sanitize_overrides({"top_n_recall": 9, "evil": 1, "use_prism": "false"})
        self.assertEqual(o["top_n_recall"], 9)
        self.assertNotIn("evil", o)
        self.assertIs(o["use_prism"], False)

    def test_preset_se_compact(self):
        s = apply_preset("se-compact")
        self.assertEqual(s["profile"], "agent")
        self.assertEqual(s["overrides"].get("handoff_max_facts"), 4)
        cfg = load_config(settings=s, apply_env=False)
        self.assertEqual(cfg.handoff_max_facts, 4)
        self.assertEqual(cfg.profile, "agent")

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "holon_settings.json"
            s = apply_preset("se-long")
            s["default_project"] = "Holon"
            save_settings(s, path)
            loaded = load_settings(path)
            self.assertEqual(loaded["default_project"], "Holon")
            self.assertEqual(loaded["preset"], "se-long")
            cfg = load_config(settings=loaded, apply_env=False)
            self.assertGreaterEqual(cfg.hard_prune_store_max, 800)

    def test_doctor_structure(self):
        rep = doctor()
        self.assertIn("checks", rep)
        self.assertIn("positioning", rep)
        self.assertTrue(any(c["name"] == "agent_boot" for c in rep["checks"]))
        self.assertTrue(any(p["capability"].startswith("Local-first") for p in rep["positioning"]))

    def test_all_presets_load(self):
        for name in PRESETS:
            s = apply_preset(name)
            cfg = load_config(settings=s, apply_env=False)
            self.assertIn(cfg.profile, ("agent", "chat", "flat"))

    def test_ui_lang_normalize(self):
        self.assertEqual(normalize_lang("EN"), "en")
        self.assertEqual(normalize_lang("polish"), "pl")
        s = normalize_settings({"ui_lang": "en", "profile": "agent"})
        self.assertEqual(s["ui_lang"], "en")
        self.assertEqual(resolve_ui_lang("en", settings={"ui_lang": "pl"}), "en")
        pl_label, _ = preset_text("se-compact", "pl")
        en_label, _ = preset_text("se-compact", "en")
        self.assertIn("kompakt", pl_label.lower())
        self.assertIn("compact", en_label.lower())

    def test_help_cli_en(self):
        code = configure_main(["--lang", "en", "help"])
        self.assertEqual(code, 0)

    def test_surface_status(self):
        from karmin_app import surface_status

        st = surface_status("Holon")
        self.assertIn("surfaces", st)
        self.assertIn("agent_boot", st["surfaces"])
        self.assertIn("stats", st)
        self.assertIn("doctor_score", st)


if __name__ == "__main__":
    unittest.main()
