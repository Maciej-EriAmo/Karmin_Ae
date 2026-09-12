# -*- coding: utf-8 -*-
"""holon/session.py — Session: publiczne API dla użytkownika

Bazowa klasa dla SecureSession (holon_session_secure.py) i AwareSession
(holon_session_aware.py). Współdzielona logika (parser przypomnień, wywołanie
LLM, pętla chat/start) żyje tutaj; podklasy dopinają się przez metody-hooki
(`_pre_chat_guard`, `_maybe_handle_command`, `_extra_system_context`,
`_on_reminder_set`, `_start_banner`, `_create_watcher`) zamiast kopiować całość.
"""

import re
import datetime
import time
from typing import Optional, List, Dict, Tuple

from holon_config import Config
from holon_embedder import Embedder
from holon_holomem import HoloMem
from holon_watcher import ReminderWatcher
from holon_llm import build_llm_client, ChatClient
from holon_prompts import DEFAULT_SYSTEM as HOLON_DEFAULT_SYSTEM

from notes_manager import NotesManager, parse_note_command

try:
    from dateutil import parser as date_parser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


class Session:
    DEFAULT_SYSTEM = HOLON_DEFAULT_SYSTEM

    def __init__(self, memory_path: str = "holon_memory.json",
                 cfg=None, system: str = None,
                 model: str = None, api_key: str = None,
                 llm_client: Optional["ChatClient"] = None):
        self.system = system or self.DEFAULT_SYSTEM
        # Profil produktowy (chat), nie agent — jawny rozdział
        cfg_ = cfg or Config.from_settings(default_profile="chat")
        self._client = llm_client or build_llm_client(
            api_key=api_key if api_key is not None else (cfg_.llm_api_key or None),
            model=model or (cfg_.llm_model or None),
            backend=cfg_.llm_backend or "auto",
            base_url=cfg_.llm_base_url or None,
            timeout_s=cfg_.llm_timeout_s,
        )

        emb = Embedder(dim=cfg_.dim,
                       dict_path=memory_path.replace(".json", "_kurz.json"),
                       time_dim=cfg_.time_dim)
        self.holomem = HoloMem(emb, cfg_, memory_path)
        self._watcher: Optional[ReminderWatcher] = None

        self.notes_manager = NotesManager(notes_dir="notes")

        def _insight_cb(prompt_text: str) -> str:
            if not self._client:
                return ""
            return self._call_llm([{"role": "system", "content": prompt_text}])

        self.holomem.set_insight_callback(_insight_cb)

    def set_llm_client(self, client: Optional["ChatClient"]) -> None:
        """Wszczep / podmień LLM w bieżącej sesji (lokalny model na kiedyś)."""
        self._client = client

    # ── Start ──────────────────────────────────────────────────────────────

    def _start_banner(self, s: dict, aii: dict) -> str:
        return (f"\n[Karmin_Ae v5.13] tur={s['turns']} store={s['store']} "
                f"delta={s['delta_hours']}h "
                f"aii={aii['emotion']}(focus:{aii['focus']})")

    def _create_watcher(self) -> ReminderWatcher:
        return ReminderWatcher(self.holomem)

    def _on_watcher_started(self) -> None:
        print(f"[ReminderWatcher] Uruchomiony "
              f"(sprawdzanie co {ReminderWatcher.CHECK_INTERVAL}s)")

    def start(self) -> str:
        res = self.holomem.start_session()
        s = self.holomem.stats()
        aii = s["aii"]
        print(self._start_banner(s, aii))
        self._watcher = self._create_watcher()
        self._watcher.start()
        self._on_watcher_started()
        return res.get("wake", "")

    # ── Reminder parsing (współdzielone) ─────────────────────────────────────

    def _parse_reminder(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        reminder_pattern = re.compile(r'(?:przypomnij|remind)(?:\s+m(?:i|e))?', re.IGNORECASE)
        kw_match = reminder_pattern.search(text)
        if not kw_match:
            return None, None
        after_kw = text[kw_match.end():].strip()
        if not after_kw:
            return None, None

        def _clean(s: str) -> str:
            s = re.sub(r'jutro\s+o\s+\d{1,2}:\d{2}\b', '', s, flags=re.IGNORECASE)
            s = re.sub(r'o\s+\d{1,2}:\d{2}\b', '', s, flags=re.IGNORECASE)
            s = re.sub(r'za\s+\d+\s+(?:godzin|godziny|godzinę)\b', '', s, flags=re.IGNORECASE)
            s = re.sub(r'za\s+\d+\s+(?:minut|minuty|minutę)\b', '', s, flags=re.IGNORECASE)
            return re.sub(r'\s{2,}', ' ', s).strip()

        m = re.search(r'jutro\s+o\s+(\d{1,2}):(\d{2})\b', after_kw, re.IGNORECASE)
        if m:
            h, mi = map(int, m.groups())
            dt = (datetime.datetime.now() + datetime.timedelta(days=1)).replace(hour=h, minute=mi, second=0, microsecond=0)
            return _clean(after_kw), dt.timestamp()

        m = re.search(r'o\s+(\d{1,2}):(\d{2})\b', after_kw, re.IGNORECASE)
        if m:
            h, mi = map(int, m.groups())
            now = datetime.datetime.now()
            dt = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if dt < now:
                dt += datetime.timedelta(days=1)
            return _clean(after_kw), dt.timestamp()

        m = re.search(r'za\s+(\d+)\s+(?:godzin|godziny|godzinę)\b', after_kw, re.IGNORECASE)
        if m:
            dt = datetime.datetime.now() + datetime.timedelta(hours=int(m.group(1)))
            return _clean(after_kw), dt.timestamp()

        m = re.search(r'za\s+(\d+)\s+(?:minut|minuty|minutę)\b', after_kw, re.IGNORECASE)
        if m:
            dt = datetime.datetime.now() + datetime.timedelta(minutes=int(m.group(1)))
            return _clean(after_kw), dt.timestamp()

        if HAS_DATEUTIL:
            if not any(kw in after_kw.lower() for kw in ['o ', 'jutro', 'za ', 'godzin', 'minut']):
                try:
                    dt = date_parser.parse(after_kw, fuzzy=True)
                    if dt.year == 1900:
                        dt = dt.replace(year=datetime.datetime.now().year)
                    ts = dt.timestamp()
                    if ts < time.time():
                        dt += datetime.timedelta(days=1)
                        ts = dt.timestamp()
                    return _clean(after_kw), ts
                except Exception:
                    pass
        return None, None

    # ── Hooki dla podklas ─────────────────────────────────────────────────

    def _handle_note_command(self, user_input: str) -> Optional[str]:
        """Zwróć odpowiedź gdy input to komenda notatek; None gdy nie."""
        cmd_response = parse_note_command(user_input, self.notes_manager, holomem=self.holomem)
        if not cmd_response:
            return None

        if cmd_response.startswith("__SEARCH_AND_SAVE__"):
            parts = cmd_response.split('|')
            if len(parts) == 3:
                _, query, filename = parts
                prompt = (f"Odpowiedz szczegółowo na pytanie: {query}. "
                          f"Odpowiedź ma być treścią notatki. Udziel informacji "
                          f"w formie ciągłego tekstu, bez zbędnych komentarzy.")
                messages = [
                    {"role": "system", "content": "Jesteś asystentem. Podaj konkretne, rzeczowe informacje."},
                    {"role": "user", "content": prompt}
                ]
                answer = self._call_llm(messages)
                if answer.startswith("[Błąd") or answer.startswith("[Mock]"):
                    return f"⚠️ Nie udało się wyszukać: {answer}"
                title = filename.replace('.md', '').replace('_', ' ')
                note = self.notes_manager.create(title=title, content=answer)
                self.notes_manager.inject_note(self.holomem, note)
                if hasattr(self.holomem, 'conversation_history'):
                    self.holomem.conversation_history.append({
                        "role": "assistant",
                        "content": f"Wyszukano i zapisano notatkę: {note.title}"
                    })
                return (f"📝 Wyszukano i zapisano notatkę: **{note.title}**\n"
                        f"Plik: {note.path.name}")
            return "⚠️ Błąd formatowania komendy."

        if hasattr(self.holomem, 'conversation_history'):
            self.holomem.conversation_history.append({"role": "assistant", "content": cmd_response})
        return cmd_response

    def _pre_chat_guard(self, user_input: str) -> Optional[str]:
        """Zwróć non-None by przerwać chat() przed normalnym przebiegiem (np. skaner)."""
        return None

    def _maybe_handle_command(self, user_input: str) -> Optional[str]:
        """Zwróć non-None (w tym "") gdy komenda jest w pełni obsłużona bez LLM."""
        return None

    def _extra_system_context(self, user_input: str) -> str:
        """Dodatkowy kontekst do system-promptu (np. świadomość notatek/zadań)."""
        return ""

    def _on_reminder_set(self, reminder_text: str, reminder_time: float) -> None:
        """Hook wywoływany po zapisaniu przypomnienia (po udanym wywołaniu LLM)."""
        return None

    # ── Chat ───────────────────────────────────────────────────────────────

    def chat(self, user_input: str, extra_context: str = "") -> str:
        note_response = self._handle_note_command(user_input)
        if note_response is not None:
            return note_response

        guard_msg = self._pre_chat_guard(user_input)
        if guard_msg is not None:
            return guard_msg

        cmd_result = self._maybe_handle_command(user_input)
        if cmd_result is not None:
            return cmd_result

        current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_context = f"Aktualna data i godzina: {current_time_str}"

        # Parsowanie przypomnień - bez natychmiastowego modyfikowania user_input
        # aby uniknąć systemowych dopisków w pamięci długotrwałej (Item.content)
        rem_data = None
        if len(user_input) > 5:
            reminder_text, reminder_time = self._parse_reminder(user_input)
            if reminder_text and reminder_time:
                rem_data = (reminder_text, reminder_time)

        upcoming = self.holomem.get_upcoming_reminders(within_seconds=3600)
        reminder_msg = ""
        if upcoming:
            lines = [f"- {r.content} (za {int((r.created_at - time.time()) // 60)} minut)" for r in upcoming]
            reminder_msg = "[PRZYPOMNIENIA] Nadchodzące wydarzenia:\n" + "\n".join(lines) + "\n"

        awareness = self._extra_system_context(user_input)

        sys_extra_parts = [time_context]
        if reminder_msg:
            sys_extra_parts.append(reminder_msg)
        if rem_data:
            sys_extra_parts.append(
                f"[SYSTEM: Ustawiono przypomnienie: {rem_data[0]} na "
                f"{datetime.datetime.fromtimestamp(rem_data[1])}]"
            )
        if awareness:
            sys_extra_parts.append(awareness)
        if (extra_context or "").strip():
            sys_extra_parts.append(extra_context.strip())
        sys_extra = "\n\n".join(sys_extra_parts)

        # Generowanie wiadomości dla LLM
        messages = self.holomem.turn(user_input, self.system)

        if messages and messages[0]["role"] == "system":
            messages[0]["content"] += "\n\n" + sys_extra
        else:
            messages.insert(0, {"role": "system", "content": sys_extra})

        response = self._call_llm(messages)

        # Sprawdzenie błędów LLM przed zapisem do pamięci
        if response.startswith("[Błąd") or response.startswith("[Mock]"):
            print("[System] Błąd API — przerywam zapis do pamięci.")
            return response

        # Dopiero po udanym wywołaniu LLM dodajemy przypomnienie i zapisujemy turę
        if rem_data:
            self.holomem.add_reminder(rem_data[0], rem_data[1])
            self._on_reminder_set(rem_data[0], rem_data[1])

        self.holomem.after_turn(user_input, response)

        s = self.holomem.stats()
        aii = s["aii"]
        print(f"  [store={s['store']} aii={aii['emotion']}(focus:{aii['focus']}) "
              f"vac={aii['vacuum_signal']:+.2f} lr={s['lr_current']:.5f}]", flush=True)
        return response

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        if not self._client:
            return (
                "[Mock] Brak backendu LLM. "
                "Ollama: ollama serve · Gemini: GEMINI_API_KEY · "
                "albo HOLON_LLM_BACKEND + model w holon_settings.json."
            )
        try:
            return self._client.chat_completion(messages, temperature=0.7, max_tokens=1024)
        except Exception as e:
            print(f"[Session] Błąd LLM: {e}")
            return f"[Błąd LLM: {e}]"

    def stats(self) -> dict:
        return self.holomem.stats()

    def reset(self):
        self.holomem.reset()
        print("[Holon] Pamięć wyczyszczona.")

    def stop_watcher(self) -> None:
        if self._watcher:
            self._watcher.stop()
