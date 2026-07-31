# -*- coding: utf-8 -*-
"""Golden eval + profile/LLM slot — unittest wrapper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holon_memory_eval import run_golden_eval


class TestGoldenMemoryEval(unittest.TestCase):
    def test_all_golden_checks(self):
        report = run_golden_eval()
        failed = [c["name"] for c in report["checks"] if not c["pass"]]
        self.assertTrue(
            report["ok"],
            f"failed={failed} detail={[c for c in report['checks'] if not c['pass']]}",
        )


if __name__ == "__main__":
    unittest.main()
