# -*- coding: utf-8 -*-
"""holon_lexindex.py — B2: lekki inverted index lexical (token → item ids).

Przy dużym store (domyślnie >500) recall najpierw zbiera kandydatów z indeksu,
potem liczy pełny score tylko na podzbiorze — mniej O(n) skanów.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from holon_item import Item

_TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9_]{2,}", re.UNICODE)


def tokenize(text: str, min_len: int = 3) -> Set[str]:
    """Tokeny do indeksu (lower); min_len jak hybrid_min_token_len."""
    if not text:
        return set()
    out: Set[str] = set()
    for m in _TOKEN_RE.finditer(text.lower()):
        t = m.group(0)
        if len(t) >= min_len:
            out.add(t)
    return out


class LexicalIndex:
    """Inverted index: token → set(item_id)."""

    def __init__(self, min_token_len: int = 3):
        self.min_token_len = int(min_token_len)
        self.postings: Dict[str, Set[str]] = {}
        self.doc_tokens: Dict[str, Set[str]] = {}  # id → tokens
        self.version: int = 0
        self._dirty: bool = True

    def clear(self) -> None:
        self.postings.clear()
        self.doc_tokens.clear()
        self.version += 1
        self._dirty = False

    def rebuild(self, store: Iterable["Item"]) -> int:
        self.clear()
        n = 0
        for it in store:
            self.add_item(it, bump=False)
            n += 1
        self.version += 1
        self._dirty = False
        return n

    def mark_dirty(self) -> None:
        self._dirty = True

    @property
    def dirty(self) -> bool:
        return self._dirty

    def ensure(self, store: List["Item"]) -> None:
        if self._dirty or len(self.doc_tokens) != len(store):
            # szybki sanity: jeśli liczba docs ≠ store → rebuild
            if self._dirty or len(self.doc_tokens) != len(
                [i for i in store if getattr(i, "id", None)]
            ):
                self.rebuild(store)

    def add_item(self, item: "Item", bump: bool = True) -> None:
        iid = getattr(item, "id", None) or ""
        if not iid:
            return
        if iid in self.doc_tokens:
            self.remove_id(iid, bump=False)
        toks = tokenize(item.content or "", self.min_token_len)
        self.doc_tokens[iid] = toks
        for t in toks:
            bucket = self.postings.get(t)
            if bucket is None:
                bucket = set()
                self.postings[t] = bucket
            bucket.add(iid)
        if bump:
            self.version += 1

    def remove_id(self, item_id: str, bump: bool = True) -> None:
        toks = self.doc_tokens.pop(item_id, None)
        if not toks:
            return
        for t in toks:
            bucket = self.postings.get(t)
            if not bucket:
                continue
            bucket.discard(item_id)
            if not bucket:
                self.postings.pop(t, None)
        if bump:
            self.version += 1

    def update_item(self, item: "Item") -> None:
        self.add_item(item, bump=True)

    def query_ids(self, query: str) -> Set[str]:
        q_toks = tokenize(query, self.min_token_len)
        if not q_toks:
            return set()
        # unia postingów (OR) — recall hybrydowy i tak rankuje
        hits: Set[str] = set()
        for t in q_toks:
            bucket = self.postings.get(t)
            if bucket:
                hits |= bucket
        return hits

    def candidates(
        self,
        query: str,
        store: List["Item"],
        *,
        always_durable: bool = True,
        max_candidates: int = 256,
    ) -> List["Item"]:
        """Kandydaci do scoringu: hit leksykalny ∪ (opcjonalnie durable)."""
        self.ensure(store)
        id_hits = self.query_ids(query)
        by_id = {i.id: i for i in store if getattr(i, "id", None)}
        picked: List["Item"] = []
        seen: Set[str] = set()

        for iid in id_hits:
            it = by_id.get(iid)
            if it is not None and iid not in seen:
                picked.append(it)
                seen.add(iid)

        if always_durable:
            for it in store:
                if it.id in seen:
                    continue
                if it.is_fact or it.is_work or it.is_insight or it.is_reminder:
                    # durable zawsze w grze przy małej liczbie; przy dużej — tylko top age=0
                    if len(picked) < max_candidates or it.age <= 2:
                        picked.append(it)
                        seen.add(it.id)

        if len(picked) > max_candidates:
            # preferuj durable + świeże
            picked.sort(
                key=lambda x: (
                    0 if (x.is_fact or x.is_work) else 1,
                    x.age,
                    -(x.relevance or 0),
                )
            )
            picked = picked[:max_candidates]

        if not picked:
            return list(store)
        return picked

    def stats(self) -> dict:
        return {
            "docs": len(self.doc_tokens),
            "tokens": len(self.postings),
            "version": self.version,
            "dirty": self._dirty,
            "min_token_len": self.min_token_len,
        }
