# -*- coding: utf-8 -*-
"""holon_repl.py — wspólna pętla interaktywna dla main.py / main_secure.py / main_aware.py.

Te trzy skrypty różnią się modułami (scanner/notes/tasks/knowledge) i
bannerem, ale mają identyczny szkielet: banner -> start() -> input loop
(quit/stats/reset/ruminate + chat) -> finally. Ten plik trzyma ten szkielet
w jednym miejscu; różnice wpina się przez parametry.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Sequence


def run_repl(
    session,
    *,
    title: str,
    subtitle_lines: Sequence[str] = (),
    prompt_label: str = "Ty",
    response_label: str = "Asystent",
    exact_commands: Optional[Dict[str, Callable[[], None]]] = None,
    pre_chat_handlers: Sequence[Callable[[str], Optional[str]]] = (),
    extra_context_provider: Optional[Callable[[str], str]] = None,
    on_finally: Optional[Callable[[], None]] = None,
) -> None:
    """Odpal pętlę czatu w terminalu wokół dowolnej Session/SecureSession/AwareSession.

    ``exact_commands``: mapowanie dokładnego tekstu (już .lower()) na handler
    bez argumentów (np. main_secure.py "audit"). Sprawdzane po wbudowanych
    quit/stats/reset/ruminate, przed przekazaniem do chat().

    ``pre_chat_handlers``: funkcje ``str -> Optional[str]`` wywoływane po
    kolei; pierwsza, która zwróci nie-None, wygrywa (wypisywana, chat()
    pomijany) — np. main_secure.py parse_task_command (SecureSession sama
    nie ma zadań, w przeciwieństwie do AwareSession).

    ``extra_context_provider``: ``str -> str`` — dodatkowy kontekst do
    ``session.chat(user, extra_context=...)`` (np. lookup w KnowledgeStore).

    ``on_finally``: sprzątanie na wyjściu; domyślnie ``session.stop_watcher``.
    """
    print("=" * 60)
    print(title)
    print("=" * 60)

    wake_msg = session.start()
    if wake_msg:
        print(f"\n{wake_msg}\n")

    for line in subtitle_lines:
        print(line)
    print("-" * 60)

    exact_commands = exact_commands or {}
    finalize = on_finally or session.stop_watcher

    try:
        while True:
            try:
                user = input(f"\n{prompt_label}: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nDo widzenia.")
                break

            if not user:
                continue
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
            if cmd in exact_commands:
                exact_commands[cmd]()
                continue

            handled_response: Optional[str] = None
            for handler in pre_chat_handlers:
                handled_response = handler(user)
                if handled_response:
                    break
            if handled_response:
                print(f"\n{handled_response}")
                continue

            extra = extra_context_provider(user) if extra_context_provider else ""
            print(f"\n{response_label}: ", end="", flush=True)
            response = session.chat(user, extra_context=extra)
            if response:
                print(response)
    finally:
        finalize()
