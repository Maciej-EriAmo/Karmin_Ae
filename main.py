#!/usr/bin/env python3
# main.py — EriAmo / HolonOS
from holon_repl import run_repl
from holon_session import Session

session = Session(memory_path="holon_memory.json")
run_repl(
    session,
    title="Karmin_Ae v5.13 — EriAmo chat",
    subtitle_lines=["Komendy: quit, stats, reset, ruminate"],
)
