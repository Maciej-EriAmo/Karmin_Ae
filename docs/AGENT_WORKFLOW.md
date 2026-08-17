# Agent workflow — Holon jako pamięć SE

## Cel

Utrzymać **ciągłość między sesjami** Grok/CLI bez wklejania całej historii czatu i bez amnezji po przerwie.

## Kto jest kim

| Rola | Start | Doc |
|------|--------|-----|
| **Agent (Ty)** | `python agent_boot.py` | ten plik + [AGENTS.md](../AGENTS.md) |
| **Człowiek** | `START.cmd` / `karmin_app.py` | [USER_GUIDE.md](USER_GUIDE.md) |

**Nie** zastępuj bootu otwarciem GUI. GUI jest dla operatora; Ty konsumujesz **handoff JSON**.  
Szybki stan: `python karmin_app.py --status` lub `python holon_agent_memory.py status`.

### Proto-emocje (AII) — tło, nie treść handoffu

Stan `aii` (emotion / vacuum / focus) żyje w silniku i w `holon_memory.json`.  
W torze SE **pierwszeństwo ma** active_work + facts + `recommended_actions` (compact).  
AII reguluje w tle wagi i — w chat — ton (`format_internal_state`); **nie recytuj emocji**, chyba że user pyta.  
Gdy focus jest aktywny: trzymaj **1 work**, nie rozjeżdżaj wątku.  
Opis: [AII_PROTO_EMOTIONS.md](AII_PROTO_EMOTIONS.md).

## Protokół sesji

```
┌─────────────┐     handoff JSON      ┌──────────────┐
│  Agent start │ ───────────────────► │  Kontekst SE │
│ agent_boot   │                      └──────┬───────┘
└─────────────┘                              │
        │                                    │
        ▼                                    │
  assist (Ollama gemma3:4b)                  │
  orient / draft-close / ask                 │
                                             ▼
                                      remember / set-work
                                             │
                                             ▼
                                      leave / close (zapis komory)
                                      enter Q | koniec
```

B13: `enter P` ładuje komorę, `leave`/`close` zapisuje stan, obrót nie ścina innych projektów. `chambers` = bęben. Szczegóły: [B10_HANDOFF.md](B10_HANDOFF.md#b13--komory-enter--leave).

**Pomocnik agenta** (nie chat człowieka) — moduł [`holon_helper.py`](../holon_helper.py):

```bash
python holon_agent_memory.py assist --project Holon
python holon_agent_memory.py assist --task draft-close --project Holon
python holon_agent_memory.py assist --task hygiene --project Holon
python holon_agent_memory.py assist --ask "co dalej?" --project Holon
python -m holon_helper --project Holon
```

| Task | Po co |
|------|--------|
| `orient` | po bootcie: stan, luki, komendy |
| `draft-close` | draft WORK/FACT przed `close` |
| `hygiene` | crystallize / work-spam |
| `ask` | pytanie ad hoc |

Wymaga `ollama serve` + model z `helper_llm_model` (domyślnie `gemma3:4b`).  
Config: `helper_llm_backend` / `helper_llm_model` w `holon_settings.json`.  
Szczegóły slotu LLM: [LLM_SLOT.md](LLM_SLOT.md).

### 1. Start

```bash
cd C:\Users\drwis\Karmin_Ae
python agent_boot.py
# albo:
python agent_boot.py --project Karmazyn
# re-boot / mało tokenów (B1+B10 hybrid — facts w oknie, work może spoza):
python agent_boot.py --since 24h --project Holon
python agent_boot.py --compact --no-banner
# czysta delta bez hybrid:
python agent_boot.py --since 24h --strict-delta --project Holon
# czytelny Markdown (B7):
python agent_boot.py --md --project Holon
python agent_boot.py --md --out handoff.md --since 24h
# pipe JSON:
python agent_boot.py --no-banner
```

To jest **kanoniczna** ścieżka agenta (AGENTS.md §0). `handoff` zostaje w API.  
`--since 24h|7d|90m` → `mode=delta` lub **`hybrid`** (B10: last work spoza okna w `active_work`).

Pola kluczowe w JSON:

- `active_work` — bieżący wątek (domyślnie max 2; hybrid może oznaczyć `outside_window`)
- `key_facts` — w full=anchors; w delta=nowe w oknie
- `anchors` / `chronicle` — kotwice vs log sesji (B10)
- `recommended_actions` / `suggested_mneme` — co zrobić dalej
- `agent_protocol` — reguły (nie resetuj store, prefiksy projektów)
- `surfaces` — **B12** komendy `agent` vs `human` (nie myl torów)
- `stats.delta_hours` — jak długa przerwa

### 2. Podczas pracy

| Zdarzenie | Akcja |
|-----------|--------|
| Ustalenie trwałe („zawsze prawdziwe”) | `remember --fact "[Projekt] …"` |
| Zmiana aktywnego celu | `set-work "…" --project X` (domyślnie **1** aktywny) |
| Domknięcie sesji (preferowane) | `close --work-text "…" --fact-text "…" --project X` |
| Szybkie wyszukanie | `recall "hasło"` / `suggested_mneme` z handoff |
| Pełny tekst do wklejenia | `digest --project X` |

### 3. Koniec sesji

- Preferuj **`close`** (atomowo work + fact + save + last_project).
- Albo osobno `remember` / `set-work` (domyślnie zapis).
- Nie zostawiaj 10× work o tym samym — `set-work` demotuje nadmiar do fact (max 1).
- Gdy store „szumi” (duplikaty factów, za dużo work): **krystalizacja ścieżek**
- Patrz też handoff `recommended_actions`.

```bash
python holon_agent_memory.py close --work-text "next …" --fact-text "…" --project Holon
python holon_agent_memory.py crystallize --dry-run --project Holon   # podgląd
python holon_agent_memory.py crystallize --project Holon             # merge + Φ + save
```

B9: `crystallize` nie zmyśla treści — scala near-dup, promuje stabilne klastry, demotuje nadmiar work, wzmacnia Φ.  
B10: projekcja handoff — [B10_HANDOFF.md](B10_HANDOFF.md).

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
