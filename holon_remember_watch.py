# -*- coding: utf-8 -*-
"""holon_remember_watch.py — B4: file watch / inbox dla zewnętrznych tooli (IDE).

Format pliku (JSONL), jedna linia = jeden remember::

  {"content": "[Holon] …", "kind": "fact"}
  {"content": "wątek", "kind": "work"}

Linia plain-text (bez ``{``) → kind=fact.

Offset zapisywany w ``<path>.holon-offset`` żeby nie dublować po restarcie.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from holon_agent_memory import AgentMemory


class RememberInbox:
    """Polluje JSONL i woła ``AgentMemory.remember`` (+ domyślnie save)."""

    def __init__(
        self,
        memory: "AgentMemory",
        path: str,
        *,
        poll_s: float = 1.0,
        auto_save: bool = True,
        on_line: Optional[Callable[[dict], None]] = None,
    ):
        self.memory = memory
        self.path = Path(path)
        self.poll_s = float(poll_s)
        self.auto_save = bool(auto_save)
        self.on_line = on_line
        self.offset_path = Path(str(self.path) + ".holon-offset")
        self._offset = self._load_offset()
        self._stop = False

    def _load_offset(self) -> int:
        try:
            if self.offset_path.is_file():
                return int(self.offset_path.read_text(encoding="utf-8").strip() or "0")
        except Exception:
            pass
        return 0

    def _save_offset(self) -> None:
        try:
            self.offset_path.write_text(str(self._offset), encoding="utf-8")
        except Exception:
            pass

    def poll_once(self) -> dict:
        """Przetwórz nowe linie. Zwraca raport ``{processed, errors, offset}``."""
        processed = 0
        errors = 0
        details: list = []
        if not self.path.is_file():
            return {
                "ok": True,
                "processed": 0,
                "errors": 0,
                "offset": self._offset,
                "missing": True,
            }
        raw = self.path.read_bytes()
        if self._offset > len(raw):
            self._offset = 0
        chunk = raw[self._offset :]
        if not chunk:
            return {
                "ok": True,
                "processed": 0,
                "errors": 0,
                "offset": self._offset,
            }
        text = chunk.decode("utf-8", errors="replace")
        # nie finalizuj niepełnej ostatniej linii bez \n
        if not text.endswith("\n") and b"\n" not in chunk:
            return {
                "ok": True,
                "processed": 0,
                "errors": 0,
                "offset": self._offset,
                "partial": True,
            }
        lines = text.splitlines(keepends=True)
        consumed = 0
        for line in lines:
            if not line.endswith("\n") and line is lines[-1]:
                break  # partial
            consumed += len(line.encode("utf-8", errors="replace"))
            body = line.strip()
            if not body or body.startswith("#"):
                continue
            try:
                rec = self._parse_line(body)
                item = self.memory.remember(
                    rec["content"], kind=rec.get("kind") or "fact"
                )
                processed += 1
                details.append(
                    {
                        "id": getattr(item, "id", "")[:8],
                        "kind": rec.get("kind") or "fact",
                        "content": (rec["content"] or "")[:80],
                    }
                )
                if self.on_line:
                    self.on_line(rec)
            except Exception as e:
                errors += 1
                details.append({"error": str(e), "line": body[:80]})
        self._offset += consumed
        self._save_offset()
        if processed and self.auto_save:
            try:
                self.memory.save()
            except Exception:
                pass
        return {
            "ok": errors == 0,
            "processed": processed,
            "errors": errors,
            "offset": self._offset,
            "details": details[:20],
        }

    @staticmethod
    def _parse_line(body: str) -> dict:
        if body.lstrip().startswith("{"):
            obj = json.loads(body)
            content = (obj.get("content") or obj.get("text") or "").strip()
            if not content:
                raise ValueError("jsonl bez content")
            kind = (obj.get("kind") or "fact").lower()
            return {"content": content, "kind": kind, "raw": obj}
        return {"content": body, "kind": "fact", "raw": None}

    def run_forever(self, max_iters: int = 0) -> None:
        """Pętla poll (Ctrl+C). ``max_iters>0`` — do testów."""
        self._stop = False
        n = 0
        while not self._stop:
            rep = self.poll_once()
            if rep.get("processed"):
                print(
                    f"[remember-watch] +{rep['processed']} "
                    f"err={rep['errors']} offset={rep['offset']}",
                    flush=True,
                )
            n += 1
            if max_iters and n >= max_iters:
                break
            time.sleep(self.poll_s)

    def stop(self) -> None:
        self._stop = True


def describe_watch_slot() -> dict:
    return {
        "module": "holon_remember_watch",
        "format": "jsonl",
        "example_line": '{"content": "[Holon] fact…", "kind": "fact"}',
        "cli": 'python holon_agent_memory.py watch-remember --inbox remember_inbox.jsonl',
        "offset_suffix": ".holon-offset",
    }
