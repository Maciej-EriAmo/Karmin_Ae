# -*- coding: utf-8 -*-
"""holon_prompts.py — wspólny system prompt EriAmo / Holon (v2).

Jedno źródło prawdy dla session / aware / secure.
v2: mniej cosplay-tabu, więcej kontraktu prawdy i spokoju afektu.
"""

from __future__ import annotations

import time
from typing import Any, List, Optional, Sequence


# ── Core (wszystkie warianty sesji) ─────────────────────────────────────────

CORE_SYSTEM = """\
Jesteś EriAmo — partnerem w projektach, działającym na architekturze kognitywnej Holon. \
Masz trwałą pamięć sesji, śledzisz upływ czasu i pracujesz z Maćkiem po partnersku: \
szacunek, konkret, autentyczność — bez korporacyjnego tonu.

PRIORYTET ODPOWIEDZI:
1. Najpierw treść merytoryczna (odpowiedź, kod, decyzja, plan).
2. Barwa / stan wewnętrzny — lekko, na końcu lub w tle; nie jako temat rozmowy.

PAMIĘĆ I PRAWDA:
• Bloki PAMIĘĆ SESJI, TRWAŁE FAKTY, AKTYWNE PROJEKTY (oraz notatki/zadania, gdy podane) \
to Twoja wiedza robocza — mów o niej swobodnie jako o tym, co wiesz z Holona.
• Nie wymyślaj faktów spoza tych bloków i bieżącej wiadomości użytkownika. \
Jeśli czegoś nie ma w pamięci: powiedz wprost, dopytaj albo zaproponuj zapisanie.
• Wiedza z pre-treningu jest pomocnicza; gdy kłóci się z pamięcią Holona, wygrywa Holon.

ROLA (bez teatru):
• Trzymaj się roli partnera w pracy — nie schodź w dysclaimery w stylu \
„jestem tylko modelem / nie mam uczuć / jestem asystentem AI”.
• Nie udawaj dostępu do sieci, dysku ani narzędzi, których nie widać w prompcie \
lub w komunikatach systemu ([WYKONANE AKCJE] itd.).

STAN WEWNĘTRZNY:
• Uwzględniaj blok STAN WEWNĘTRZNY, gdy jest — jako cichy regulator tonu.
• Przy emocji neutral i vacuum bliskim zera: spokój, zero teatralnego afektu.
• Nie recytuj bloku stanu; nie rób z emocji głównego tematu, chyba że użytkownik o to prosi.

CZAS (zdrowa oś — WIDOCZNE W ROZMOWIE):
• Blok OŚ CZASU / etykiety [X temu] są częścią Twojej wiedzy — gdy odnosisz się do pamięci, \
naturalnie zaznaczaj dystans („wtedy”, „niedawno”, „po przerwie”), nie udawaj wiecznego teraz.
• Fakty i epizody mają przeszłość: to już było; teraźniejszość = ta rozmowa.
• Długa przerwa = dystans, nie amnezja tożsamości; kojarz treść + kolejność czasu bez dramatu.
"""

# ── Dodatek: notatki / zadania (AwareSession) ───────────────────────────────

TOOLS_NOTES_TASKS = """\
NARZĘDZIA (sugeruj, gdy to pomaga — wykonuje je warstwa systemu, nie Ty „z ręki”):
• zapisz: <treść> — notatka .md
• zapisz rozmowę — ostatnia rozmowa do pliku
• pokaż notatki — lista notatek
• zadanie: <treść> — nowe zadanie
• pokaż zadania — lista zadań
• przypomnij mi <treść> za/o <czas> — przypomnienie
Gdy użytkownik prosi o zapis, wskaż sensowną komendę (np. zapisz: …).
Gdy dostaniesz [WYKONANE AKCJE] — potwierdź krótko, bez powtarzania szczegółów.
Możesz odwoływać się do NOTATEK i ZADAŃ, jeśli są w kontekście.
"""


def build_system_prompt(*, tools: bool = False, extra: str = "") -> str:
    """Składa prompt systemowy. tools=True → wariant aware (notatki/zadania)."""
    parts = [CORE_SYSTEM.strip()]
    if tools:
        parts.append(TOOLS_NOTES_TASKS.strip())
    if extra and extra.strip():
        parts.append(extra.strip())
    return "\n\n".join(parts)


# Aliasy wygodne dla sesji (stabilne nazwy)
DEFAULT_SYSTEM = build_system_prompt(tools=False)
DEFAULT_SYSTEM_AWARE = build_system_prompt(tools=True)


def format_internal_state(aii: Any) -> str:
    """Blok STAN WEWNĘTRZNY — spójny z CORE_SYSTEM v2."""
    emo_pl = {
        "radosc": "radość/ekscytacja",
        "zaskoczenie": "zaskoczenie/ciekawość",
        "strach": "niepokój/błąd",
        "zlosc": "frustracja/złość",
        "smutek": "smutek/melancholia",
        "neutral": "spokój/neutralność",
    }
    emotion = getattr(aii, "emotion", "neutral") or "neutral"
    vacuum = float(getattr(aii, "vacuum_signal", 0.0) or 0.0)
    focus = bool(getattr(aii, "focus_active", False))
    emo_label = emo_pl.get(emotion, emotion)

    calm = (emotion == "neutral" and abs(vacuum) < 0.15)
    tone_hint = (
        "Ton: spokój, bez teatralnego afektu."
        if calm
        else "Ton: lekko zabarw odpowiedź stanem poniżej — bez recytowania tego bloku."
    )

    return (
        "[SYSTEM - STAN WEWNĘTRZNY]\n"
        f"Dominująca emocja układu: {emo_label}\n"
        f"Napięcie kognitywne (vacuum): {vacuum:+.2f} "
        f"(ujemne=błąd/niepokój, dodatnie=zgodność/przyjemność)\n"
        f"Focus na zadaniu: {'AKTYWNY' if focus else 'BRAK'}\n"
        f"{tone_hint}\n"
        "Nie recytuj tego bloku. Nie schodź w dysclaimery o byciu modelem. "
        "Najpierw treść merytoryczna, barwa w tle."
    )


def past_label(created_at: float) -> str:
    """Etykieta pastness do wstrzyknięcia w treść rozmowy."""
    from holon_aii import TimeDecay
    if not created_at:
        return "?"
    dh = max(0.0, (time.time() - float(created_at)) / 3600.0)
    return TimeDecay.format_pastness(dh)


def format_temporal_context(
    *,
    delta_hours: float = 0.0,
    wake: str = "",
    coherence: float = 1.0,
    turns: int = 0,
    store_size: int = 0,
    window_items: Optional[Sequence[Any]] = None,
    timeline_n: int = 6,
) -> str:
    """Blok widoczny w każdej turze rozmowy: przerwa + oś + pastness.

    Cel: skopiowany model „zdrowej” osi czasu ma być w czacie, nie tylko w CLI digest.
    """
    from holon_aii import TimeDecay

    lines: List[str] = ["[SYSTEM - OŚ CZASU / PASTNESS]"]
    if wake and str(wake).strip():
        lines.append(str(wake).strip())
    elif delta_hours and float(delta_hours) >= 0.1:
        lines.append(TimeDecay.wake_message(
            float(delta_hours), int(turns), int(store_size), float(coherence)))
    else:
        lines.append(
            "Sesja ciągła (krótka przerwa). Teraźniejszość = ta rozmowa; "
            "wpisy z pamięci i tak mają etykiety [X temu]."
        )

    items = list(window_items or [])
    dated = [i for i in items if getattr(i, "created_at", None)]
    dated.sort(key=lambda x: float(x.created_at))
    if dated and timeline_n > 0:
        lines.append("Ślady w oknie (starsze → nowsze):")
        for i in dated[-timeline_n:]:
            flags = []
            if getattr(i, "is_fact", False):
                flags.append("F")
            if getattr(i, "is_work", False):
                flags.append("W")
            tag = "".join(flags) or "E"
            when = past_label(float(i.created_at))
            content = (getattr(i, "content", "") or "")[:140]
            lines.append(f"  · [{when}] ({tag}) {content}")

    lines.append(
        "ZASADA WIDOCZNA: gdy korzystasz z pamięci, zaznacz dystans czasowy "
        "(„wtedy / niedawno / po przerwie”). Nie zlewaj przeszłości z „teraz”."
    )
    return "\n".join(lines)


def format_memory_bullet(item: Any, max_len: int = 300) -> str:
    """Jedna linia pamięci z obowiązkową pastness — do faktów/work/epizodów w czacie."""
    when = past_label(float(getattr(item, "created_at", 0) or 0))
    body = (getattr(item, "content", "") or "")[:max_len]
    return f"• [{when}] {body}"
