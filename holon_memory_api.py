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
        max_work: Optional[int] = None,
        max_facts: Optional[int] = None,
        include_digest: bool = True,
        since=None,
        *,
        compact: bool = False,
        hybrid_since: Optional[bool] = None,
        max_chronicle: Optional[int] = None,
    ) -> dict: ...

    def handoff_md(
        self,
        project: str = "",
        max_work: Optional[int] = None,
        max_facts: Optional[int] = None,
        include_digest: bool = False,
        since=None,
        out_path: Optional[str] = None,
        *,
        compact: bool = False,
        hybrid_since: Optional[bool] = None,
    ) -> str: ...

    def set_work(
        self,
        content: str,
        project: str = "",
        max_active: Optional[int] = None,
    ) -> Item: ...

    def close(
        self,
        *,
        work: str = "",
        fact: str = "",
        project: str = "",
        max_active: Optional[int] = None,
        save: bool = True,
    ) -> dict: ...

    def crystallize(
        self,
        project: str = "",
        *,
        dry_run: bool = False,
        sim_threshold: Optional[float] = None,
        promote_cluster_min: Optional[int] = None,
        max_active_work: Optional[int] = None,
        reinforce_phi: bool = True,
    ) -> dict: ...

    def on_remember(self, callback=None): ...


def open_memory(
    memory_path: str = "holon_memory.json",
    *,
    profile: str = "agent",
    kurz_path: Optional[str] = None,
    use_settings: bool = True,
) -> MemoryAPI:
    """Fabryka: AgentMemory + Config z settings/env (profil agent|chat|flat)."""
    from holon_agent_memory import AgentMemory

    return AgentMemory.open(
        memory_path=memory_path,
        kurz_path=kurz_path,
        profile=profile,
        use_settings=use_settings,
    )
