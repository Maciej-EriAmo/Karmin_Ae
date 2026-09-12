# -*- coding: utf-8 -*-
"""
holon_session_aware.py — Session z pełną świadomością kontekstową

Rozszerza SecureSession (dziedziczenie) o:
- Świadomość notatek (lista + zawartość relevantnych)
- Świadomość wykonanych komend (LLM wie że zapisano notatkę)
- Świadomość przypomnień (gdy się odpalają)
- Świadomość zadań

Autor: Maciej Mazur
"""

import datetime
from typing import List, Optional

from holon_watcher import ReminderWatcher
from holon_prompts import DEFAULT_SYSTEM_AWARE as HOLON_DEFAULT_SYSTEM_AWARE
from holon_session_secure import SecureSession

# Notes
try:
    from notes_manager import NotesManager, parse_note_command
    HAS_NOTES = True
except ImportError:
    HAS_NOTES = False

# Tasks
try:
    from tasks import TasksManager, parse_task_command
    HAS_TASKS = True
except ImportError:
    HAS_TASKS = False


class AwareSession(SecureSession):
    """
    Session z pełną świadomością kontekstową.

    LLM wie o:
    - Notatkach użytkownika (ostatnie + relevantne)
    - Zadaniach (aktywne)
    - Wykonanych komendach systemowych
    - Odpalonych przypomnieniach
    """

    DEFAULT_SYSTEM = HOLON_DEFAULT_SYSTEM_AWARE

    def __init__(self, memory_path: str = "holon_memory.json",
                 notes_dir: str = "notes",
                 tasks_dir: str = "tasks",
                 cfg=None, system: str = None,
                 model: str = None, api_key: str = None,
                 enable_scanner: bool = True):
        super().__init__(memory_path=memory_path, cfg=cfg, system=system,
                          model=model, api_key=api_key,
                          enable_scanner=enable_scanner)

        # Notes & Tasks (świadomość — osobne od base Session.notes_manager)
        self.notes = NotesManager(notes_dir=notes_dir) if HAS_NOTES else None
        self.tasks = TasksManager(tasks_dir=tasks_dir) if HAS_TASKS else None

        # Context injection buffer
        self._context_injections: List[str] = []

        # Fired reminders tracking
        self._fired_reminders: List[str] = []

    # ── Start ──────────────────────────────────────────────────────────────

    def _start_banner(self, s: dict, aii: dict) -> str:
        modules = []
        if self._enable_scanner:
            modules.append("scanner")
        if self.notes:
            modules.append(f"notes({self.notes.count})")
        if self.tasks:
            modules.append(f"tasks({self.tasks.count})")

        return (f"\n[Karmin_Ae v5.13 AWARE] tur={s['turns']} store={s['store']} "
                f"delta={s['delta_hours']}h [{', '.join(modules)}]")

    def _create_watcher(self) -> ReminderWatcher:
        return ReminderWatcher(self.holomem, on_fire=self._on_reminder_fired)

    def _on_reminder_fired(self, item):
        """Callback gdy przypomnienie się odpala."""
        self._fired_reminders.append(item.content)

    # ── Context building ───────────────────────────────────────────────────

    def _build_awareness_context(self, user_input: str) -> str:
        """Buduje kontekst świadomości dla LLM."""
        parts = []

        # 1. Fired reminders (najwyższy priorytet)
        if self._fired_reminders:
            reminders_text = "\n".join(f"• {r}" for r in self._fired_reminders)
            parts.append(f"[🔔 PRZYPOMNIENIA WŁAŚNIE SIĘ ODPALIŁY]\n{reminders_text}")
            self._fired_reminders.clear()

        # 2. Context injections (wykonane komendy)
        if self._context_injections:
            parts.append("[WYKONANE AKCJE]\n" + "\n".join(self._context_injections))
            self._context_injections.clear()

        # 3. Notes awareness
        if self.notes and self.notes.count > 0:
            # Ostatnie 3 notatki (tytuły)
            recent = self.notes.recent(3)
            if recent:
                notes_list = ", ".join(f'"{n.title}"' for n in recent)
                parts.append(f"[NOTATKI] Ostatnie: {notes_list} (łącznie {self.notes.count})")

            # Relevantne do zapytania (jeśli query > 10 znaków)
            if len(user_input) > 10:
                relevant = self.notes.search(user_input, top_k=2)
                if relevant:
                    rel_text = "\n".join(
                        f"• {n.title}: {n.summary[:100]}..."
                        for n in relevant
                    )
                    parts.append(f"[RELEVANTNE NOTATKI]\n{rel_text}")

        # 4. Tasks awareness
        if self.tasks and self.tasks.count > 0:
            active = self.tasks.list_active()
            if active:
                tasks_text = ", ".join(f'"{t.title}"' for t in active[:5])
                parts.append(f"[ZADANIA] Aktywne: {tasks_text}")

        return "\n\n".join(parts) if parts else ""

    def _extra_system_context(self, user_input: str) -> str:
        return self._build_awareness_context(user_input)

    def _on_reminder_set(self, reminder_text: str, reminder_time: float) -> None:
        dt_str = datetime.datetime.fromtimestamp(reminder_time).strftime("%H:%M %d.%m")
        injection = f"✓ Ustawiono przypomnienie na {dt_str}: {reminder_text}"
        self._context_injections.append(injection)
        print(f"\n⏰ {injection}")

    # ── Command processing ─────────────────────────────────────────────────

    def _handle_note_command(self, user_input: str) -> Optional[str]:
        # Notatki obsługiwane niżej w _maybe_handle_command (self.notes,
        # z injection zamiast twardego short-circuit) — base Session.notes_manager
        # nie jest tu używany.
        return None

    def _maybe_handle_command(self, user_input: str) -> Optional[str]:
        """
        Przetwarza komendy systemowe.

        Zwraca:
          ""    → komenda systemowa obsłużona bez odpowiedzi LLM
          None  → nie obsłużono (albo obsłużono z injection — LLM ma odpowiedzieć)
        """
        cmd = user_input.lower().strip()

        # Komendy czysto systemowe (bez LLM)
        if cmd == "quit":
            return ""
        if cmd == "stats":
            print(f"\n[Stats] {self.stats()}")
            return ""
        if cmd == "reset":
            self.reset()
            return ""
        if cmd == "ruminate":
            self.holomem.ruminate(force=True)
            return ""
        if cmd == "pokaż notatki" and self.notes:
            notes = self.notes.recent(8)
            print(f"\n📋 Twoje notatki:\n\n{self.notes.format_list(notes)}")
            return ""
        if cmd == "pokaż zadania" and self.tasks:
            print(f"\n📋 Twoje zadania:\n\n{self.tasks.format_list()}")
            return ""

        # Komendy notatek (z informacją dla LLM)
        if self.notes:
            note_cmd = parse_note_command(user_input, self.notes, self.holomem)
            if note_cmd:
                print(f"\n{note_cmd}")
                self._context_injections.append(f"✓ {note_cmd}")
                # NIE zwracaj "" — pozwól LLM potwierdzić
                return None

        # Komendy zadań (z informacją dla LLM)
        if self.tasks:
            task_cmd = parse_task_command(user_input, self.tasks)
            if task_cmd:
                print(f"\n{task_cmd}")
                self._context_injections.append(f"✓ {task_cmd}")
                return None

        return None

    # ── Utils ──────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        base = super().stats()
        base["notes_count"] = self.notes.count if self.notes else 0
        base["tasks_count"] = self.tasks.count if self.tasks else 0
        return base

    def stop(self):
        self.stop_watcher()
        if self.tasks:
            self.tasks._save()
