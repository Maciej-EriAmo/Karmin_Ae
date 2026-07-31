# -*- coding: utf-8 -*-
"""
holon_backend_karmin.py — opcjonalny backend trwałości za MemoryAPI.

**Zamiast SQLite (odrzucone w planie B3):** własny **Karmin_DB / Cynober**
(`C:/Users/drwis/DBase`, pakiet cynober-db).

Rola:
  - mirror fact/work (i opcjonalnie epizodów) w KarminQL / Store T×reach
  - snapshot przenośny JSON (backup / multi-session) w formacie holon↔karmin
  - NIE zastępuje holon_memory.json + Φ (to nadal primary runtime SE)

Użycie::

    from holon_backend_karmin import KarminMirror, karmin_available
    if karmin_available():
        m = KarminMirror.open()
        m.sync_items(am.hm.store)
        m.export_snapshot("backup.holon-karmin.json")
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


SNAPSHOT_FORMAT = "holon-karmin-snapshot-v1"
DEFAULT_DBASE_CANDIDATES = (
    os.environ.get("HOLON_KARMIN_PATH", "").strip(),
    os.environ.get("DBASE_ROOT", "").strip(),
    r"C:\Users\drwis\DBase",
    str(Path(__file__).resolve().parent.parent / "DBase"),
    str(Path.home() / "DBase"),
)


def resolve_dbase_root() -> Optional[Path]:
    for raw in DEFAULT_DBASE_CANDIDATES:
        if not raw:
            continue
        p = Path(raw)
        if (p / "cynober_query_engine.py").is_file() or (
            p / "cynober_db"
        ).is_dir():
            return p.resolve()
    # zainstalowany pakiet bez drzewa źródłowego
    try:
        import cynober_query_engine  # noqa: F401

        return None  # available via site-packages; root unknown
    except ImportError:
        return None


def karmin_available() -> bool:
    root = resolve_dbase_root()
    if root is not None:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    try:
        from cynober_query_engine import KarminEngine  # noqa: F401
        import karmazyn_kernel  # noqa: F401

        return True
    except ImportError:
        return False


def _esc(val: str) -> str:
    return (
        (val or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _bubble_name(item_id: str) -> str:
    raw = (item_id or uuid.uuid4().hex).replace("-", "")
    return "h_" + raw[:32]


class KarminMirror:
    """In-process KarminEngine mirror for Holon items."""

    def __init__(self, engine: Any, *, label: str = "holon_se"):
        self.engine = engine
        self.label = label
        self._ensured = False

    @classmethod
    def open(cls, dbase_root: Optional[str] = None) -> "KarminMirror":
        if dbase_root:
            root = Path(dbase_root)
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
        elif not karmin_available():
            raise RuntimeError(
                "Karmin_DB niedostępny. Ustaw HOLON_KARMIN_PATH=…/DBase "
                "lub pip install cynober-db / sklonuj DBase."
            )
        else:
            root = resolve_dbase_root()
            if root is not None and str(root) not in sys.path:
                sys.path.insert(0, str(root))

        import karmazyn_kernel as kernel
        from cynober_query_engine import KarminEngine

        store = kernel.Store(thermal=True)
        engine = KarminEngine(store)
        return cls(engine)

    def _exec(self, script: str) -> List[dict]:
        return self.engine.execute(script, strict=False)

    def ensure_meta(self) -> None:
        if self._ensured:
            return
        # meta bubble — etykieta przestrzeni logicznej
        name = f"holon_meta_{self.label}"
        self._exec(f'UTRWAL "{_esc(name)}"')
        self._exec(
            f'WSTRZYKNIJ "role" = "holon_memory_mirror" DO "{_esc(name)}"'
        )
        self._exec(
            f'WSTRZYKNIJ "format" = "{SNAPSHOT_FORMAT}" DO "{_esc(name)}"'
        )
        self._ensured = True

    def upsert_item(self, item: Any) -> str:
        """Zapisz / nadpisz item Holona jako bąbel Karmin. Zwraca nazwę bąbla."""
        self.ensure_meta()
        bid = _bubble_name(getattr(item, "id", "") or uuid.uuid4().hex)
        content = (getattr(item, "content", None) or "")[:2000]
        kind = "episode"
        if getattr(item, "is_work", False):
            kind = "work"
        elif getattr(item, "is_fact", False):
            kind = "fact"
        elif getattr(item, "is_insight", False):
            kind = "insight"
        elif getattr(item, "is_reminder", False):
            kind = "reminder"

        created = float(getattr(item, "created_at", 0) or time.time())
        age = int(getattr(item, "age", 0) or 0)
        rel = float(getattr(item, "relevance", 1.0) or 1.0)
        emb = getattr(item, "embedding", None)
        if emb is None and hasattr(item, "emb_content"):
            try:
                emb = item.embedding
            except Exception:
                emb = None
        emb_s = ""
        if emb is not None:
            try:
                # skrót — pełny wektor bywa duży; do restore ranking lexical i tak działa
                seq = list(emb) if not isinstance(emb, list) else emb
                emb_s = json.dumps([float(x) for x in seq[:64]], separators=(",", ":"))
            except Exception:
                emb_s = "[]"

        self._exec(f'UTRWAL "{bid}"')
        props = {
            "holon_id": getattr(item, "id", bid),
            "content": content,
            "kind": kind,
            "is_fact": "1" if getattr(item, "is_fact", False) else "0",
            "is_work": "1" if getattr(item, "is_work", False) else "0",
            "created_at": f"{created:.6f}",
            "age": str(age),
            "relevance": f"{rel:.4f}",
            "emb_head": emb_s or "[]",
            "source": "holon",
        }
        for k, v in props.items():
            self._exec(
                f'WSTRZYKNIJ "{_esc(k)}" = "{_esc(str(v))}" DO "{bid}"'
            )
        return bid

    def sync_items(
        self,
        items: Sequence[Any],
        *,
        durable_only: bool = True,
    ) -> Dict[str, Any]:
        """Upsert listy Item. Domyślnie tylko fact/work/insight/reminder."""
        n = 0
        skipped = 0
        names: List[str] = []
        for it in items:
            if durable_only:
                if not (
                    getattr(it, "is_fact", False)
                    or getattr(it, "is_work", False)
                    or getattr(it, "is_insight", False)
                    or getattr(it, "is_reminder", False)
                ):
                    skipped += 1
                    continue
            names.append(self.upsert_item(it))
            n += 1
        return {"upserted": n, "skipped_episodic": skipped, "bubbles": names}

    def fetch_rows(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """WYPISZ wiersze holon_*; filtr kind opcjonalny."""
        if kind:
            q = (
                f'WYPISZ "BĄBEL", "holon_id", "content", "kind", "is_fact", '
                f'"is_work", "created_at", "age", "relevance", "emb_head" '
                f'GDZIE "kind" = "{_esc(kind)}" ORAZ "source" = "holon"'
            )
        else:
            q = (
                f'WYPISZ "BĄBEL", "holon_id", "content", "kind", "is_fact", '
                f'"is_work", "created_at", "age", "relevance", "emb_head" '
                f'GDZIE "source" = "holon"'
            )
        results = self._exec(q)
        rows: List[Dict[str, Any]] = []
        for res in results:
            if res.get("action") == "PROJECT_WHERE":
                rows.extend(res.get("rows") or [])
        return rows

    def export_snapshot(self, path: str | Path) -> Path:
        """Przenośny backup (JSON) — rola, którą w planie pełnił SQLite."""
        path = Path(path)
        rows = self.fetch_rows()
        payload = {
            "format": SNAPSHOT_FORMAT,
            "exported_at": time.time(),
            "label": self.label,
            "n": len(rows),
            "rows": rows,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def import_snapshot(self, path: str | Path) -> int:
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != SNAPSHOT_FORMAT:
            raise ValueError(f"zły format snapshotu: {data.get('format')}")
        n = 0
        for row in data.get("rows") or []:
            # minimalny duck item
            class _Tmp:
                pass

            t = _Tmp()
            t.id = row.get("holon_id") or row.get("BĄBEL") or uuid.uuid4().hex
            t.content = row.get("content") or ""
            t.is_fact = str(row.get("is_fact", "0")) in ("1", "True", "true")
            t.is_work = str(row.get("is_work", "0")) in ("1", "True", "true")
            t.is_insight = row.get("kind") == "insight"
            t.is_reminder = row.get("kind") == "reminder"
            if row.get("kind") == "fact":
                t.is_fact = True
            if row.get("kind") == "work":
                t.is_work = True
            try:
                t.created_at = float(row.get("created_at") or time.time())
            except (TypeError, ValueError):
                t.created_at = time.time()
            try:
                t.age = int(float(row.get("age") or 0))
            except (TypeError, ValueError):
                t.age = 0
            try:
                t.relevance = float(row.get("relevance") or 1.0)
            except (TypeError, ValueError):
                t.relevance = 1.0
            try:
                t.embedding = json.loads(row.get("emb_head") or "[]")
            except json.JSONDecodeError:
                t.embedding = []
            self.upsert_item(t)
            n += 1
        return n

    def rows_to_holon_items(self, rows: Optional[Sequence[Dict]] = None):
        """Konwersja wierszy Karmin → holon_item.Item (wymaga embedder poza)."""
        from holon_item import Item

        rows = list(rows if rows is not None else self.fetch_rows())
        out = []
        for row in rows:
            try:
                emb = json.loads(row.get("emb_head") or "[]")
            except json.JSONDecodeError:
                emb = []
            if not emb:
                emb = [0.0] * 8  # placeholder; AgentMemory i tak re-encode przy need
            it = Item(
                id=str(row.get("holon_id") or uuid.uuid4()),
                content=str(row.get("content") or ""),
                embedding=emb if isinstance(emb, list) else list(emb),
                age=int(float(row.get("age") or 0)),
                relevance=float(row.get("relevance") or 1.0),
                is_fact=str(row.get("is_fact", "0")) in ("1", "True", "true")
                or row.get("kind") == "fact",
                is_work=str(row.get("is_work", "0")) in ("1", "True", "true")
                or row.get("kind") == "work",
            )
            try:
                it.created_at = float(row.get("created_at") or time.time())
            except (TypeError, ValueError):
                pass
            out.append(it)
        return out

    def stats(self) -> Dict[str, Any]:
        rows = self.fetch_rows()
        kinds: Dict[str, int] = {}
        for r in rows:
            k = r.get("kind") or "?"
            kinds[k] = kinds.get(k, 0) + 1
        st = {}
        try:
            st = self.engine.api.store.stats()
        except Exception:
            pass
        return {
            "backend": "karmin_db",
            "label": self.label,
            "holon_rows": len(rows),
            "kinds": kinds,
            "store_stats": st,
            "dbase_root": str(resolve_dbase_root() or "site-packages"),
        }


def describe_karmin_slot() -> Dict[str, Any]:
    return {
        "available": karmin_available(),
        "dbase_root": str(resolve_dbase_root() or ""),
        "env_HOLON_KARMIN_PATH": os.environ.get("HOLON_KARMIN_PATH", ""),
        "replaces_plan": "B3 SQLite → Karmin_DB (własny stack, T×reach)",
        "snapshot_format": SNAPSHOT_FORMAT,
    }
