#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_aware.py — EriAmo z pełną świadomością kontekstową

LLM wie o:
- Notatkach (ostatnie + relevantne do zapytania)
- Zadaniach (aktywne)
- Wykonanych komendach (zapisz, przypomnij)
- Odpalonych przypomnieniach

Komendy:
  quit, stats, reset, ruminate
  zapisz: <tekst>       — notatka
  zapisz rozmowę        — zapisz ostatnią rozmowę
  pokaż notatki
  zadanie: <tekst>      — nowe zadanie
  pokaż zadania
  przypomnij mi o X za Y minut/godzin
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from holon_repl import run_repl
from holon_session_aware import AwareSession


def main():
    session = AwareSession(
        memory_path="holon_memory.json",
        notes_dir="notes",
        tasks_dir="tasks",
    )
    run_repl(
        session,
        title="  Karmin_Ae v5.13 AWARE — EriAmo z pełną świadomością",
        subtitle_lines=[
            "Komendy: quit, stats, reset, ruminate",
            "         zapisz: <tekst>, pokaż notatki",
            "         zadanie: <tekst>, pokaż zadania",
            "         przypomnij mi [treść] za/o [czas]",
        ],
        response_label="EriAmo",
        on_finally=session.stop,
    )


if __name__ == "__main__":
    main()
