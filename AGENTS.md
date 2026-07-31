# AGENTS.md — Holon jako pamięć dla agenta (Grok / CLI)

Ten plik jest **kontraktem startowym** dla agenta pracującego w tym repo lub używającego Holona jako store SE.

## Rola Holona

| Jest | Nie jest |
|------|----------|
| Trwała pamięć współpracy (fact / work / pastness) | Kanoniczny produkt czatu EriAmo (to `main.py` + `Config.chat()`) |
| Bootstrap kontekstu między sesjami | Silnik KarmazynOs (osobne repo `C:/Users/drwis/KarmazynOs`) |
| Cienkie API bez LLM | Wymaganie GPU / chmury |

## Bootstrap sesji (obowiązkowy rytuał)

```bash
# z katalogu holonOs
python holon_agent_memory.py handoff --no-digest
# albo z pełnym tekstem:
python holon_agent_memory.py handoff
# filtr projektu:
python holon_agent_memory.py handoff --project Karmazyn --no-digest
python holon_agent_memory.py digest --project Holon
```

**Po handoff:** nie zakładaj „wiecznego teraz” — etykiety czasu w store to **przeszłość**.

## Zapis

```bash
python holon_agent_memory.py remember --fact "[Holon] Ustalenie: ..."
python holon_agent_memory.py remember --work "[Karmazyn] Następny krok: ..."
# preferowane dla aktywnego wątku (demotuje stare work → fact):
python holon_agent_memory.py set-work "R6 freestanding po golden" --project Karmazyn
```

## Testy / regregresja

```bash
python holon_agent_memory.py eval          # golden, temp store
python -m unittest tests.test_holon_agent tests.test_memory_eval -q
```

## Zakazy

1. **Nie** `reset` / kasowanie `holon_memory.json` bez wyraźnej prośby użytkownika.  
2. **Nie** mylić workspace `holonOs` z `KarmazynOs` — kod runtime jest w Karmazyn.  
3. **Nie** mnożyć work bez `set-work` / demotion.  
4. **Nie** traktować README-benchmarków jako public leaderboard.

## Dokumentacja

| Doc | Treść |
|------|--------|
| [docs/README.md](docs/README.md) | Indeks |
| [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) | Pełny workflow SE |
| [docs/MEMORY_API.md](docs/MEMORY_API.md) | Kontrakt API |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Warstwy systemu |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Plan rozwoju |
| [docs/LLM_SLOT.md](docs/LLM_SLOT.md) | Lokalny model |

## Profile Config

- Agent CLI: `Config.agent()` (domyślne w `AgentMemory.open`)
- Chat EriAmo: `Config.chat()` (`Session` / `main.py`)
- Ablacja: `Config.flat()` — `use_prism=False`
- Env: `HOLON_PROFILE=agent|chat|flat`
