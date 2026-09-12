#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_secure.py — EriAmo / HolonOS z pełną integracją

Zawiera:
- SecureSession (z PromptScanner)
- Notatki (wbudowane w SecureSession przez dziedziczenie — session.notes_manager)
- TasksManager
- KnowledgeStore (opcjonalnie)

Komendy:
  quit, stats, reset, ruminate
  zanotuj: <tekst>
  zadanie: <tekst>
  pokaż notatki / pokaż zadania
  audit — pokaż log bezpieczeństwa
"""

import sys
import os
from typing import Optional

# Dodaj bieżący katalog do path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from holon_repl import run_repl
from holon_session_secure import SecureSession

# Opcjonalne moduły
try:
    from tasks import TasksManager, parse_task_command
    HAS_TASKS = True
except ImportError:
    HAS_TASKS = False

try:
    from knowledge_store import KnowledgeStore, format_knowledge_for_prompt
    HAS_KNOWLEDGE = True
except ImportError:
    HAS_KNOWLEDGE = False

KNOWLEDGE_KEYWORDS = ("co to jest", "wyjaśnij", "jak działa", "what is", "explain", "how does")


def main():
    session = SecureSession(memory_path="holon_memory.json")
    tasks = TasksManager(tasks_dir="tasks") if HAS_TASKS else None
    knowledge = KnowledgeStore(md_dir="knowledge") if HAS_KNOWLEDGE else None
    notes = session.notes_manager  # dziedziczone z Session — ta sama "notes/"

    modules = []
    if notes:
        modules.append(f"notes({notes.count})")
    if tasks:
        modules.append(f"tasks({tasks.count})")
    if knowledge:
        modules.append("knowledge")

    subtitle = []
    if modules:
        subtitle.append(f"[Moduły] {', '.join(modules)}")
    subtitle.append("\nKomendy: quit, stats, reset, ruminate, audit")
    if notes:
        subtitle.append("         zanotuj: <tekst>, pokaż notatki")
    if tasks:
        subtitle.append("         zadanie: <tekst>, pokaż zadania")

    def do_audit() -> None:
        events = session.security_audit()
        if not events:
            print("[Audit] Brak zdarzeń bezpieczeństwa.")
            return
        print(f"[Audit] {len(events)} zdarzeń:")
        for e in events[-5:]:  # ostatnie 5
            print(f"  [{e['risk_level']}] {e['input_preview'][:40]}... "
                  f"blocked={e['blocked']}")

    def task_handler(user: str) -> Optional[str]:
        if not tasks:
            return None
        return parse_task_command(user, tasks)

    def extra_context(user: str) -> str:
        if not (knowledge and len(user) > 20):
            return ""
        if not any(kw in user.lower() for kw in KNOWLEDGE_KEYWORDS):
            return ""
        results = knowledge.recall(user, top_k=1)
        if results and results[0].get("score", 0) > 0.3:
            text = format_knowledge_for_prompt(results[0])
            if text:
                print(f"  [Knowledge] wstrzyknięto: {results[0].get('filename')}")
                return text
        return ""

    def on_finally() -> None:
        session.stop_watcher()
        if notes:
            print(f"[Notes] {notes.count} notatek")
        if tasks:
            tasks._save()  # Zapisz zadania
            print(f"[Tasks] {tasks.count} zadań")
        print("[Holon] Sesja zakończona.")

    run_repl(
        session,
        title="  Karmin_Ae v5.13 SECURE — EriAmo",
        subtitle_lines=subtitle,
        exact_commands={"audit": do_audit},
        pre_chat_handlers=[task_handler],
        extra_context_provider=extra_context,
        on_finally=on_finally,
    )


if __name__ == "__main__":
    main()
