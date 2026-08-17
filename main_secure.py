#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_secure.py — EriAmo / HolonOS z pełną integracją

Zawiera:
- SecureSession (z PromptScanner)
- NotesManager
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

# Dodaj bieżący katalog do path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from holon_session_secure import SecureSession

# Opcjonalne moduły
try:
    from notes_manager import NotesManager, parse_note_command
    HAS_NOTES = True
except ImportError:
    HAS_NOTES = False

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


def main():
    print("=" * 60)
    print("  Karmin_Ae v5.13 SECURE — EriAmo")
    print("=" * 60)
    
    # Inicjalizacja
    session = SecureSession(memory_path="holon_memory.json")
    wake_msg = session.start()
    if wake_msg:
        print(f"\n{wake_msg}\n")
    
    # Opcjonalne moduły
    notes = NotesManager(notes_dir="notes") if HAS_NOTES else None
    tasks = TasksManager(tasks_dir="tasks") if HAS_TASKS else None
    knowledge = KnowledgeStore(md_dir="knowledge") if HAS_KNOWLEDGE else None
    
    modules = []
    if notes: modules.append(f"notes({notes.count})")
    if tasks: modules.append(f"tasks({tasks.count})")
    if knowledge: modules.append("knowledge")
    if modules:
        print(f"[Moduły] {', '.join(modules)}")
    
    print("\nKomendy: quit, stats, reset, ruminate, audit")
    if notes: print("         zanotuj: <tekst>, pokaż notatki")
    if tasks: print("         zadanie: <tekst>, pokaż zadania")
    print("-" * 60)

    try:
        while True:
            try:
                user = input("\nTy: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nDo widzenia.")
                break
            
            if not user:
                continue
            
            # Komendy systemowe
            cmd = user.lower()
            
            if cmd == "quit":
                break
            
            if cmd == "stats":
                print(f"\n[Stats] {session.stats()}")
                continue
            
            if cmd == "reset":
                session.reset()
                continue
            
            if cmd == "ruminate":
                session.holomem.ruminate(force=True)
                continue
            
            if cmd == "audit":
                events = session.security_audit()
                if not events:
                    print("[Audit] Brak zdarzeń bezpieczeństwa.")
                else:
                    print(f"[Audit] {len(events)} zdarzeń:")
                    for e in events[-5:]:  # ostatnie 5
                        print(f"  [{e['risk_level']}] {e['input_preview'][:40]}... "
                              f"blocked={e['blocked']}")
                continue
            
            # Komendy notatek
            if notes:
                note_response = parse_note_command(user, notes, session.holomem)
                if note_response:
                    print(f"\n{note_response}")
                    continue
            
            # Komendy zadań
            if tasks:
                task_response = parse_task_command(user, tasks)
                if task_response:
                    print(f"\n{task_response}")
                    continue
            
            extra = ""
            if knowledge and len(user) > 20:
                knowledge_keywords = ["co to jest", "wyjaśnij", "jak działa",
                                      "what is", "explain", "how does"]
                if any(kw in user.lower() for kw in knowledge_keywords):
                    results = knowledge.recall(user, top_k=1)
                    if results and results[0].get("score", 0) > 0.3:
                        extra = format_knowledge_for_prompt(results[0])
                        if extra:
                            print(f"  [Knowledge] wstrzyknięto: {results[0].get('filename')}")

            print("\nAsystent: ", end="", flush=True)
            response = session.chat(user, extra_context=extra)
            print(response)
    
    finally:
        session.stop_watcher()
        if notes:
            print(f"[Notes] {notes.count} notatek")
        if tasks:
            tasks._save()  # Zapisz zadania
            print(f"[Tasks] {tasks.count} zadań")
        print("[Holon] Sesja zakończona.")


if __name__ == "__main__":
    main()
