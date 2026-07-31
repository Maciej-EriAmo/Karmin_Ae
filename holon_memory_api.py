# -*- coding: utf-8 -*-
"""
holon_memory_api.py — cienki kontrakt pamięci (remember / recall / digest / save).

Implementacja domyślna: ``AgentMemory`` (``holon_agent_memory``).
Silnik (HRR/Φ) jest za szwem — da się podmienić implementację bez zmiany CLI/agentów.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, Sequence, Tuple, runtime_checkable

from holon_item import Item


@runtime_checkable
class MemoryAPI(Protocol):
    """Publiczny kontrakt pamięci Holona (bez LLM)."""

    def remember(
        self, content: str, kind: str = "fact", relevance: float = 1.5
    ) -> Item: ...

    def recall(
        self, query: str, top_k: int = 8
    ) -> List[Tuple[float, Item]]: ...

    def digest(
        self,
        max_facts: int = 12,
        max_work: int = 8,
        max_recent: int = 6,
        project: str = "",
    ) -> str: ...

    def save(self) -> bool: ...

    def stats(self) -> dict: ...

    def handoff(
        self,
        project: str = "",
        max_work: int = 4,
        max_facts: int = 8,
        include_digest: bool = True,
    ) -> dict: ...

    def set_work(
        self, content: str, project: str = "", max_active: int = 3
    ) -> Item: ...


def open_memory(
    memory_path: str = "holon_memory.json",
    *,
    profile: str = "agent",
    kurz_path: Optional[str] = None,
) -> MemoryAPI:
    """Fabryka: domyślnie AgentMemory + Config.agent()|chat()|flat()."""
    from holon_agent_memory import AgentMemory

    return AgentMemory.open(
        memory_path=memory_path, kurz_path=kurz_path, profile=profile
    )
