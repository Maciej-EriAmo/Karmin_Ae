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
# re-boot / mało tokenów (B1 — tylko delty z okna):
python agent_boot.py --since 24h --project Holon
# czytelny Markdown (B7):
python agent_boot.py --md --project Holon
python agent_boot.py --md --out handoff.md --since 24h
# pipe JSON:
python agent_boot.py --no-banner
```

To jest **kanoniczna** ścieżka agenta (AGENTS.md §0). `handoff` zostaje w API.  
`--since 24h|7d|90m` → `mode=delta` (tylko wpisy z `created_at` w oknie).

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
- Gdy store „szumi” (duplikaty factów, za dużo work): **krystalizacja ścieżek**

```bash
python holon_agent_memory.py crystallize --dry-run --project Holon   # podgląd
python holon_agent_memory.py crystallize --project Holon             # merge + Φ + save
```

B9: `crystallize` nie zmyśla treści — scala near-dup, promuje stabilne klastry, demotuje nadmiar work, wzmacnia Φ.

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
python holon_agent_memory.py ablation   # B6 flat vs prism
```

## Inbox z IDE (B4)

```bash
# {"content":"[Holon] …", "kind":"fact"}
python holon_agent_memory.py watch-remember --inbox remember_inbox.jsonl --once
```

Hook w kodzie: `am.on_remember(callback)`.
