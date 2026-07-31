# Agent workflow — Holon jako pamięć SE

## Cel

Utrzymać **ciągłość między sesjami** Grok/CLI bez wklejania całej historii czatu i bez amnezji po przerwie.

## Protokół sesji

```
┌─────────────┐     handoff JSON      ┌──────────────┐
│  Agent start │ ───────────────────► │  Kontekst SE │
└─────────────┘                       └──────┬───────┘
                                             │ praca w Karmazyn/Holon/…
                                             ▼
                                      remember / set-work
                                             │
                                             ▼
                                      save (holon_memory.json)
```

### 1. Start

```bash
cd C:\Users\drwis\holonOs
python agent_boot.py
# albo:
python agent_boot.py --project Karmazyn
# pipe JSON:
python agent_boot.py --no-banner
```

To jest **kanoniczna** ścieżka agenta (AGENTS.md §0). `handoff` zostaje w API.

Pola kluczowe w JSON:

- `active_work` — co jest otwarte (max kilka)
- `key_facts` — kotwice z pastness (`when`)
- `agent_protocol` — reguły (nie resetuj store, prefiksy projektów)
- `stats.delta_hours` — jak długa przerwa

### 2. Podczas pracy

| Zdarzenie | Akcja |
|-----------|--------|
| Ustalenie trwałe („zawsze prawdziwe”) | `remember --fact "[Projekt] …"` |
| Zmiana aktywnego celu | `set-work "…" --project X` |
| Szybkie wyszukanie | `recall "hasło"` |
| Pełny tekst do wklejenia | `digest --project X` |

### 3. Koniec sesji

- Upewnij się, że ostatnie `remember`/`set-work` poszły z zapisem (domyślnie tak).
- Nie zostawiaj 10× work o tym samym — `set-work` demotuje nadmiar do fact.

## Prefiksy multi-projekt

```
[Holon] …        — ten repo / pamięć / API
[Karmazyn] …     — C:/Users/drwis/KarmazynOs
```

Filtr: `--project Holon` | `--project Karmazyn` (aliasy w kodzie: slab, kentry → Karmazyn).

## Czego unikać (antywzorca)

1. **Wieczne teraz** — fact bez kontekstu czasu w narracji; digesty mają etykiety „X temu”.  
2. **Work-spam** — każdy mikro-krok jako work.  
3. **Fork myślenia** — edycja Holona gdy zadanie jest w Karmazyn (i odwrotnie), bez aktualizacji work.  
4. **Reset „dla czystości”** — niszczy ciągłość SE.

## Integracja z toolami (Grok Build)

1. Na początku turnu agent (lub orchestration): uruchom `handoff`.  
2. Trwałe wnioski sesji → `remember` / `set-work`.  
3. Przed domknięciem PR/commit w Karmazyn: opcjonalnie fact ze skrótem commita.

## Test zdrowia

```bash
python holon_agent_memory.py eval
# oczekuj: GOLDEN_EVAL: OK
```
