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
    data_home,
    doctor,
    load_config,
    load_settings,
    normalize_lang,
    normalize_settings,
    preset_text,
    relocate_repo_state,
    repo_root,
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
        self.assertEqual(s["overrides"].get("handoff_max_facts"), 3)
        cfg = load_config(settings=s, apply_env=False)
        self.assertEqual(cfg.handoff_max_facts, 3)
        self.assertEqual(cfg.handoff_max_work, 1)
        self.assertEqual(cfg.profile, "agent")
        # se default also compact handoff
        se = apply_preset("se")
        se_cfg = load_config(settings=se, apply_env=False)
        self.assertEqual(se_cfg.handoff_max_work, 1)
        self.assertLessEqual(se_cfg.handoff_max_facts, 4)

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

    def test_data_home_is_not_repo(self):
        home = data_home()
        root = repo_root()
        self.assertNotEqual(home.resolve(), root.resolve())
        self.assertFalse(str(home.resolve()).startswith(str(root.resolve()) + "\\"))

    def test_relocate_moves_state_out_of_project(self):
        import os

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "proj"
            dest = Path(td) / "data"
            repo.mkdir()
            (repo / "holon_memory.json").write_text('{"store":[]}\n', encoding="utf-8")
            old = os.environ.get("HOLON_DATA_HOME")
            os.environ["HOLON_DATA_HOME"] = str(dest)
            try:
                rep = relocate_repo_state(root=repo)
                self.assertTrue((dest / "holon_memory.json").is_file())
                self.assertFalse((repo / "holon_memory.json").is_file())
                self.assertIn("holon_memory.json", rep["moved"])
            finally:
                if old is None:
                    os.environ.pop("HOLON_DATA_HOME", None)
                else:
                    os.environ["HOLON_DATA_HOME"] = old

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

    def test_run_line_help_and_status(self):
        from karmin_app import run_line

        h = run_line("help")
        self.assertTrue(h["ok"])
        self.assertIn("fact", h["output"])
        self.assertIn("chat", h["output"].lower())
        s = run_line("status Holon", project="Holon")
        self.assertTrue(s["ok"])
        self.assertIn("doctor=", s["output"])

    def test_launch_chat_mode_map(self):
        from karmin_app import CHAT_MODES, launch_chat

        self.assertIn("brainstorm", CHAT_MODES)
        self.assertTrue((__import__("pathlib").Path("main_aware.py")).is_file())
        # invalid mode does not spawn
        bad = launch_chat("no-such-mode")
        self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
