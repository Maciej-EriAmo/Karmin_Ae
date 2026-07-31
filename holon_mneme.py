# -*- coding: utf-8 -*-
"""
holon_mneme.py — Mneme: mała baza SE + meta-język (Mneme-L).

Design: docs/MNEME.md
Warstwa nad AgentMemory: HOLD/RECALL/NEAR/ALONG/WALK/TRACE/LINK/DIGEST/FOCUS.

  python -m holon_mneme "RECALL \"slab\" TOP 5"
  python -m holon_mneme -c script.mneme
  python holon_mneme.py REPL
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from holon_agent_memory import AgentMemory
from holon_aii import TimeDecay


LINKS_FORMAT = "holon-mneme-links-v1"
CANON_RELS = frozenset(
    {"in", "about", "follows", "supports", "conflicts", "see"}
)

# ─── edges ──────────────────────────────────────────────────────────────────


@dataclass
class Edge:
    id: str
    src: str
    dst: str
    rel: str
    w: float = 1.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(
            id=str(d.get("id") or uuid.uuid4().hex[:12]),
            src=str(d["src"]),
            dst=str(d["dst"]),
            rel=str(d.get("rel") or "see"),
            w=float(d.get("w") or 1.0),
            created_at=float(d.get("created_at") or time.time()),
        )


class LinkStore:
    def __init__(self, path: str):
        self.path = path
        self.edges: List[Edge] = []
        self.load()

    def load(self) -> None:
        p = Path(self.path)
        if not p.is_file():
            self.edges = []
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self.edges = [Edge.from_dict(e) for e in data.get("edges") or []]
        except (OSError, json.JSONDecodeError):
            self.edges = []

    def save(self) -> bool:
        p = Path(self.path)
        payload = {
            "format": LINKS_FORMAT,
            "edges": [e.to_dict() for e in self.edges],
        }
        try:
            p.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False

    def add(self, src: str, dst: str, rel: str, w: float = 1.0) -> Edge:
        rel = (rel or "see").lower().strip()
        for e in self.edges:
            if e.src == src and e.dst == dst and e.rel == rel:
                e.w = max(e.w, w)
                return e
        e = Edge(
            id=uuid.uuid4().hex[:12],
            src=src,
            dst=dst,
            rel=rel,
            w=w,
        )
        self.edges.append(e)
        return e

    def remove(self, src: str, dst: str, rel: str) -> int:
        rel = (rel or "").lower().strip()
        before = len(self.edges)
        self.edges = [
            e
            for e in self.edges
            if not (e.src == src and e.dst == dst and (not rel or e.rel == rel))
        ]
        return before - len(self.edges)

    def out_edges(self, src: str, rels: Optional[Sequence[str]] = None) -> List[Edge]:
        rs = {r.lower() for r in rels} if rels else None
        out = []
        for e in self.edges:
            if e.src != src:
                continue
            if rs is not None and e.rel not in rs:
                continue
            out.append(e)
        return out


# ─── result ─────────────────────────────────────────────────────────────────


@dataclass
class MnemeResult:
    ok: bool
    op: str
    hits: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""
    graph: Optional[Dict[str, int]] = None
    focus: Optional[str] = None
    raw: Any = None

    def to_dict(self) -> dict:
        d = {
            "ok": self.ok,
            "op": self.op,
            "hits": self.hits,
            "message": self.message,
            "graph": self.graph,
            "focus": self.focus,
        }
        return d


# ─── Mneme core ─────────────────────────────────────────────────────────────


class Mneme:
    """Queryable SE memory over AgentMemory + explicit link graph."""

    def __init__(self, am: AgentMemory, links_path: Optional[str] = None):
        self.am = am
        if links_path is None:
            links_path = str(am.memory_path).replace(".json", "_links.json")
            if links_path == am.memory_path:
                links_path = am.memory_path + "_links.json"
        self.links = LinkStore(links_path)
        self.focus_project: str = ""
        self.focus_query: str = ""

    # —— helpers ——

    def _past(self, created_at: float) -> str:
        if not created_at:
            return "?"
        dh = max(0.0, (time.time() - float(created_at)) / 3600.0)
        return TimeDecay.format_pastness(dh)

    def _project_of(self, content: str) -> str:
        m = re.match(r"\s*\[([^\]]+)\]", content or "")
        return m.group(1).strip() if m else ""

    def _kind_of(self, item) -> str:
        if getattr(item, "is_work", False):
            return "work"
        if getattr(item, "is_insight", False):
            return "insight"
        if getattr(item, "is_reminder", False):
            return "reminder"
        if getattr(item, "is_fact", False):
            return "fact"
        return "episode"

    def _hit(self, item, score: float = 0.0, via: Any = None) -> dict:
        return {
            "id": item.id,
            "kind": self._kind_of(item),
            "when": self._past(getattr(item, "created_at", 0) or 0),
            "score": round(float(score), 4),
            "project": self._project_of(item.content or ""),
            "content": (item.content or "")[:500],
            "via": via,
        }

    def _find_item(self, ref: str):
        """id prefix or exact content quote match."""
        ref = (ref or "").strip()
        if not ref:
            return None
        # strip quotes
        if (ref.startswith('"') and ref.endswith('"')) or (
            ref.startswith("'") and ref.endswith("'")
        ):
            ref = ref[1:-1]
        store = self.am.hm.store
        for it in store:
            if it.id == ref or it.id.startswith(ref):
                return it
        low = ref.lower()
        for it in store:
            if (it.content or "").strip().lower() == low:
                return it
        for it in store:
            if low in (it.content or "").lower():
                return it
        return None

    def _parse_duration_hours(self, s: str) -> float:
        s = (s or "").strip().lower()
        m = re.match(r"(\d+(?:\.\d+)?)\s*(h|d|w|m)?", s)
        if not m:
            return 0.0
        v = float(m.group(1))
        u = m.group(2) or "h"
        if u == "h":
            return v
        if u == "d":
            return v * 24
        if u == "w":
            return v * 24 * 7
        if u == "m":
            return v * 24 * 30
        return v

    def _graph_stats(self) -> dict:
        return {
            "nodes": len(self.am.hm.store),
            "edges": len(self.links.edges),
        }

    def _ensure_project_hub(self, project: str):
        if not project:
            return None
        hub_content = f"[{project}] · project hub"
        for it in self.am.hm.store:
            if (it.content or "").strip() == hub_content:
                return it
        return self.am.remember(hub_content, kind="fact", relevance=1.2)

    # —— ops ——

    def hold(
        self, kind: str, content: str, project: str = "", auto_link: bool = True
    ) -> MnemeResult:
        kind = (kind or "fact").lower()
        content = (content or "").strip()
        if not content:
            return MnemeResult(False, "HOLD", message="empty content")
        proj = project or self.focus_project
        if proj and f"[{proj}]" not in content:
            content = f"[{proj}] {content}"
        if kind == "work":
            item = self.am.set_work(content, project=proj or "", max_active=5)
        else:
            map_k = "fact" if kind in ("fact", "f") else (
                "work" if kind in ("work", "w") else "note"
            )
            item = self.am.remember(content, kind=map_k)
        via = None
        if auto_link and proj:
            hub = self._ensure_project_hub(proj)
            if hub and hub.id != item.id:
                e = self.links.add(item.id, hub.id, "in")
                via = {"rel": "in", "dst": hub.id, "edge": e.id}
        return MnemeResult(
            True,
            "HOLD",
            hits=[self._hit(item, 1.0, via=via)],
            message=f"held {self._kind_of(item)}",
            graph=self._graph_stats(),
            focus=self.focus_project or None,
        )

    def recall(
        self,
        query: str,
        top: int = 5,
        project: str = "",
        kind: str = "any",
        since_h: float = 0.0,
    ) -> MnemeResult:
        q = (query or "").strip()
        proj = project or self.focus_project
        ranked = self.am.recall(q or " ", top_k=max(top * 4, 16))
        hits = []
        now = time.time()
        for score, item in ranked:
            if proj and not self.am._match_project(item.content, proj):
                continue
            k = self._kind_of(item)
            if kind and kind != "any" and k != kind:
                continue
            if since_h > 0:
                age_h = (now - float(item.created_at or now)) / 3600.0
                if age_h > since_h:
                    continue
            hits.append(self._hit(item, score))
            if len(hits) >= top:
                break
        return MnemeResult(
            True,
            "RECALL",
            hits=hits,
            graph=self._graph_stats(),
            focus=self.focus_project or None,
        )

    def near(self, ref: str, top: int = 5) -> MnemeResult:
        """Continuous graph: embedding neighborhood (classic Holon exploration)."""
        import numpy as np

        item = self._find_item(ref)
        cdim = self.am.hm.cfg.dim
        if item is not None:
            q = item.emb_content(cdim)
            q_text = item.content or ""
        else:
            q_full = self.am.hm.embedder.encode(ref, timestamp=time.time())
            q = q_full[:cdim]
            q_text = ref
        scored = []
        for it in self.am.hm.store:
            if item is not None and it.id == item.id:
                continue
            s = self.am.hm._cosine_sim(it.emb_content(cdim), q)
            s += 0.1 * self.am.hm._lexical_overlap(q_text, it.content or "")
            scored.append((s, it))
        scored.sort(key=lambda x: -x[0])
        hits = [self._hit(it, s) for s, it in scored[:top]]
        return MnemeResult(
            True, "NEAR", hits=hits, graph=self._graph_stats(), focus=self.focus_project or None
        )

    def along(self, query: str, hours_ago: float = 0.0, top: int = 5) -> MnemeResult:
        """Temporal exploration — HoloMem.recall_at."""
        target = time.time() - max(0.0, hours_ago) * 3600.0
        ranked = self.am.hm.recall_at(query, target_time=target, top_k=top)
        hits = [self._hit(it, sc) for it, sc in ranked]
        return MnemeResult(
            True,
            "ALONG",
            hits=hits,
            message=f"hours_ago={hours_ago:.2f}",
            graph=self._graph_stats(),
            focus=self.focus_project or None,
        )

    def link(self, src_ref: str, rel: str, dst_ref: str) -> MnemeResult:
        a = self._find_item(src_ref)
        b = self._find_item(dst_ref)
        if not a or not b:
            return MnemeResult(
                False, "LINK", message=f"missing node src={bool(a)} dst={bool(b)}"
            )
        rel = (rel or "see").lower()
        e = self.links.add(a.id, b.id, rel)
        self.links.save()
        return MnemeResult(
            True,
            "LINK",
            hits=[self._hit(a, 1.0, via={"rel": rel, "dst": b.id, "edge": e.id})],
            message=f"{a.id[:8]} -{rel}-> {b.id[:8]}",
            graph=self._graph_stats(),
        )

    def unlink(self, src_ref: str, rel: str, dst_ref: str) -> MnemeResult:
        a = self._find_item(src_ref)
        b = self._find_item(dst_ref)
        if not a or not b:
            return MnemeResult(False, "UNLINK", message="missing node")
        n = self.links.remove(a.id, b.id, rel)
        self.links.save()
        return MnemeResult(True, "UNLINK", message=f"removed={n}", graph=self._graph_stats())

    def trace(self, ref: str, depth: int = 1) -> MnemeResult:
        item = self._find_item(ref)
        if not item:
            return MnemeResult(False, "TRACE", message="not found")
        hits = [self._hit(item, 1.0)]
        seen = {item.id}
        frontier = [item.id]
        for d in range(max(1, depth)):
            nxt = []
            for nid in frontier:
                for e in self.links.out_edges(nid):
                    if e.dst in seen:
                        continue
                    seen.add(e.dst)
                    other = self._find_item(e.dst)
                    if other:
                        hits.append(
                            self._hit(
                                other,
                                1.0 / (d + 2),
                                via={"rel": e.rel, "from": nid, "depth": d + 1},
                            )
                        )
                        nxt.append(e.dst)
            frontier = nxt
        return MnemeResult(
            True, "TRACE", hits=hits, graph=self._graph_stats(), focus=self.focus_project or None
        )

    def walk(
        self, start_ref: str, rels: Sequence[str], depth: int = 2, top: int = 12
    ) -> MnemeResult:
        start = self._find_item(start_ref)
        if not start:
            # soft start: RECALL then walk first hit
            r = self.recall(start_ref, top=1)
            if not r.hits:
                return MnemeResult(False, "WALK", message="start not found")
            start = self._find_item(r.hits[0]["id"])
        assert start is not None
        rel_set = [x.lower().strip() for x in rels if x.strip()] or None
        hits = [self._hit(start, 1.0, via={"depth": 0})]
        seen = {start.id}
        frontier = [start.id]
        for d in range(max(1, depth)):
            nxt = []
            for nid in frontier:
                for e in self.links.out_edges(nid, rel_set):
                    if e.dst in seen:
                        continue
                    seen.add(e.dst)
                    other = self._find_item(e.dst)
                    if not other:
                        continue
                    hits.append(
                        self._hit(
                            other,
                            1.0 / (d + 2),
                            via={"rel": e.rel, "from": nid, "depth": d + 1},
                        )
                    )
                    nxt.append(e.dst)
                    if len(hits) >= top:
                        return MnemeResult(
                            True, "WALK", hits=hits, graph=self._graph_stats()
                        )
            frontier = nxt
            if not frontier:
                break
        return MnemeResult(True, "WALK", hits=hits, graph=self._graph_stats())

    def digest(self, project: str = "") -> MnemeResult:
        proj = project or self.focus_project
        text = self.am.digest(project=proj)
        return MnemeResult(
            True,
            "DIGEST",
            message=text,
            graph=self._graph_stats(),
            focus=proj or None,
        )

    def focus(self, what: str) -> MnemeResult:
        what = (what or "").strip()
        if not what or what.upper() == "CLEAR":
            self.focus_project = ""
            self.focus_query = ""
            return MnemeResult(True, "FOCUS", message="cleared", focus=None)
        if what.upper().startswith("PROJECT "):
            self.focus_project = what[8:].strip().strip('"').strip("'")
            self.focus_query = ""
            return MnemeResult(
                True, "FOCUS", message=f"project={self.focus_project}", focus=self.focus_project
            )
        self.focus_query = what.strip('"').strip("'")
        self.focus_project = ""
        return MnemeResult(
            True, "FOCUS", message=f"query={self.focus_query}", focus=self.focus_query
        )

    def softdrop_work(self, ref: str) -> MnemeResult:
        item = self._find_item(ref)
        if not item:
            return MnemeResult(False, "SOFTDROP", message="not found")
        if not item.is_work:
            return MnemeResult(False, "SOFTDROP", message="not work")
        item.is_work = False
        item.is_fact = True
        return MnemeResult(
            True, "SOFTDROP", hits=[self._hit(item, 1.0)], message="work→fact"
        )

    # —— parser / execute ——

    def execute(self, script: str) -> List[MnemeResult]:
        results: List[MnemeResult] = []
        for raw in (script or "").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            results.append(self._exec_line(line))
        return results

    def _exec_line(self, line: str) -> MnemeResult:
        u = line.strip()
        # HOLD kind "content" [PROJECT X]
        m = re.match(
            r'^HOLD\s+(fact|work|note|insight)\s+("([^"]*)"|\'([^\']*)\'|(.+?))'
            r'(?:\s+PROJECT\s+(\S+))?\s*$',
            u,
            re.I,
        )
        if m:
            kind = m.group(1).lower()
            content = m.group(3) or m.group(4) or (m.group(5) or "").strip()
            proj = (m.group(6) or "").strip().strip('"').strip("'")
            return self.hold(kind, content, project=proj)

        # RECALL "q" [TOP n] [PROJECT p] [KIND k] [SINCE 7d]
        m = re.match(
            r'^RECALL\s+("([^"]*)"|\'([^\']*)\'|(\S+))'
            r'(?:\s+TOP\s+(\d+))?'
            r'(?:\s+PROJECT\s+(\S+))?'
            r'(?:\s+KIND\s+(\w+))?'
            r'(?:\s+SINCE\s+(\S+))?'
            r'\s*$',
            u,
            re.I,
        )
        if m:
            q = m.group(2) or m.group(3) or m.group(4) or ""
            top = int(m.group(5) or 5)
            proj = (m.group(6) or "").strip().strip('"')
            kind = (m.group(7) or "any").lower()
            since = self._parse_duration_hours(m.group(8) or "")
            return self.recall(q, top=top, project=proj, kind=kind, since_h=since)

        # NEAR "q"|id [TOP n]
        m = re.match(
            r'^NEAR\s+("([^"]*)"|\'([^\']*)\'|(\S+))(?:\s+TOP\s+(\d+))?\s*$',
            u,
            re.I,
        )
        if m:
            ref = m.group(2) or m.group(3) or m.group(4) or ""
            top = int(m.group(5) or 5)
            return self.near(ref, top=top)

        # ALONG "q" AGO 3d [TOP n]
        m = re.match(
            r'^ALONG\s+("([^"]*)"|\'([^\']*)\'|(\S+))\s+AGO\s+(\S+)(?:\s+TOP\s+(\d+))?\s*$',
            u,
            re.I,
        )
        if m:
            q = m.group(2) or m.group(3) or m.group(4) or ""
            ago = self._parse_duration_hours(m.group(5))
            top = int(m.group(6) or 5)
            return self.along(q, hours_ago=ago, top=top)

        # LINK a -rel-> b
        m = re.match(
            r'^LINK\s+("([^"]*)"|\'([^\']*)\'|(\S+))\s+-'
            r'([A-Za-z_]+)->\s+("([^"]*)"|\'([^\']*)\'|(\S+))\s*$',
            u,
            re.I,
        )
        if m:
            src = m.group(2) or m.group(3) or m.group(4) or ""
            rel = m.group(5)
            dst = m.group(7) or m.group(8) or m.group(9) or ""
            return self.link(src, rel, dst)

        # UNLINK a -rel-> b
        m = re.match(
            r'^UNLINK\s+("([^"]*)"|\'([^\']*)\'|(\S+))\s+-'
            r'([A-Za-z_]*)->\s+("([^"]*)"|\'([^\']*)\'|(\S+))\s*$',
            u,
            re.I,
        )
        if m:
            src = m.group(2) or m.group(3) or m.group(4) or ""
            rel = m.group(5)
            dst = m.group(7) or m.group(8) or m.group(9) or ""
            return self.unlink(src, rel, dst)

        # TRACE ref [DEPTH n]
        m = re.match(
            r'^TRACE\s+("([^"]*)"|\'([^\']*)\'|(\S+))(?:\s+DEPTH\s+(\d+))?\s*$',
            u,
            re.I,
        )
        if m:
            ref = m.group(2) or m.group(3) or m.group(4) or ""
            depth = int(m.group(5) or 1)
            return self.trace(ref, depth=depth)

        # WALK ref VIA a,b DEPTH n [TOP n]
        m = re.match(
            r'^WALK\s+("([^"]*)"|\'([^\']*)\'|(\S+))'
            r'(?:\s+VIA\s+([A-Za-z_,]+))?'
            r'(?:\s+DEPTH\s+(\d+))?'
            r'(?:\s+TOP\s+(\d+))?\s*$',
            u,
            re.I,
        )
        if m:
            ref = m.group(2) or m.group(3) or m.group(4) or ""
            rels = [x.strip() for x in (m.group(5) or "").split(",") if x.strip()]
            depth = int(m.group(6) or 2)
            top = int(m.group(7) or 12)
            return self.walk(ref, rels, depth=depth, top=top)

        # DIGEST [PROJECT p]
        m = re.match(r'^DIGEST(?:\s+PROJECT\s+(\S+))?\s*$', u, re.I)
        if m:
            return self.digest(project=(m.group(1) or "").strip().strip('"'))

        # FOCUS …
        m = re.match(r'^FOCUS\s+(.+)\s*$', u, re.I)
        if m:
            return self.focus(m.group(1).strip())

        # SOFTDROP work ref
        m = re.match(
            r'^SOFTDROP\s+(?:work\s+)?("([^"]*)"|\'([^\']*)\'|(\S+))\s*$',
            u,
            re.I,
        )
        if m:
            ref = m.group(2) or m.group(3) or m.group(4) or ""
            return self.softdrop_work(ref)

        return MnemeResult(False, "?", message=f"unrecognized: {line[:80]}")


def open_mneme(
    memory_path: str = "holon_memory.json", profile: str = "agent"
) -> Mneme:
    am = AgentMemory.open(memory_path=memory_path, profile=profile)
    return Mneme(am)


def _print_result(r: MnemeResult, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
        if r.op == "DIGEST" and r.message:
            pass
        return
    status = "OK" if r.ok else "ERR"
    print(f"[{status}] {r.op}" + (f" — {r.message}" if r.message and r.op != "DIGEST" else ""))
    if r.op == "DIGEST" and r.message:
        print(r.message)
        return
    if r.focus:
        print(f"  focus={r.focus}")
    if r.graph:
        print(f"  graph nodes={r.graph.get('nodes')} edges={r.graph.get('edges')}")
    for h in r.hits:
        via = f" via={h['via']}" if h.get("via") else ""
        print(
            f"  · {h['score']:.3f} [{h['kind']}|{h['when']}] "
            f"{h['id'][:8]}… {h['content'][:120]}{via}"
        )


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Mneme-L — queryable SE memory on Holon")
    p.add_argument("script", nargs="?", default="", help="jedna linia Mneme-L")
    p.add_argument("-c", "--file", default="", help="plik ze skryptem")
    p.add_argument("--path", default="holon_memory.json")
    p.add_argument("--json", action="store_true")
    p.add_argument("--save", action="store_true", help="zapisz Holon + links po skrypcie")
    p.add_argument("--repl", action="store_true")
    args = p.parse_args(argv)

    m = open_mneme(memory_path=args.path)

    if args.repl or (not args.script and not args.file):
        print("Mneme-L REPL — puste / quit kończy. Docs: docs/MNEME.md")
        while True:
            try:
                line = input("mneme> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line or line.lower() in ("quit", "exit", "q"):
                break
            for r in m.execute(line):
                _print_result(r, as_json=args.json)
        if args.save:
            m.am.save()
            m.links.save()
        return 0

    script = args.script
    if args.file:
        script = Path(args.file).read_text(encoding="utf-8")
    for r in m.execute(script):
        _print_result(r, as_json=args.json)
        if not r.ok:
            return 1
    if args.save:
        m.am.save()
        m.links.save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
