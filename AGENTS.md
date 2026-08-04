# AGENTS.md — ścieżka dla Grok / CLI (czytaj TO najpierw)

> **Cudze chwalicie, swego nie znacie.**  
> W tym workspace pamięć SE **już jest**: Holon + Mneme + handoff.  
> Nie szukaj Mem0 / SQLite / „jakiejś bazy” — **odpal boot**.

---

## 0. OBOWIĄZKOWY START SESJI (jedna komenda)

```bat
cd /d C:\Users\drwis\holonOs
python agent_boot.py
```

Z filtrem projektu:

```bat
python agent_boot.py --project Karmazyn
python agent_boot.py --project Holon
```

Re-boot / mniej tokenów (**B1** — tylko delty):

```bat
python agent_boot.py --since 24h
python agent_boot.py --since 24h --project Holon
```

Tylko JSON (pipe):

```bat
python agent_boot.py --no-banner
```

Alias Windows: `agent_boot.cmd` · PowerShell: `.\agent_boot.ps1`

**Po bootcie:** kontekst = `active_work` + `key_facts` + `when`.  
Nie zmyślaj „stanu projektu” z powietrza.

---

## 1. Co tu MACIE (wasze, nie cudze)

| Narzędzie | Po co | Komenda |
|-----------|--------|---------|
| **agent_boot** | bootstrap JSON | `python agent_boot.py` |
| **Handoff** | ten sam protokół w API | `python holon_agent_memory.py handoff --no-digest` |
| **handoff-md** | B7 — handoff jako Markdown | `python holon_agent_memory.py handoff-md --out handoff.md` |
| **Mneme-L** | zapytywalna pamięć + graf | `python -m holon_mneme --repl` |
| **remember / set-work** | zapis fact/work | `python holon_agent_memory.py remember --fact "…"` |
| **crystallize** | B9 — stałe ścieżki (merge/Φ) | `python holon_agent_memory.py crystallize [--project Holon]` |
| **Karmin mirror** | backup we **własnym** DB | `python holon_agent_memory.py karmin-export` |
| **eval** | reggresja | `python holon_agent_memory.py eval` |
| **ablation** | B6 flat vs prism | `python holon_agent_memory.py ablation` |
| **watch-remember** | B4 inbox JSONL | `python holon_agent_memory.py watch-remember --once` |

Docs (głębiej):

- [docs/MNEME.md](docs/MNEME.md) — meta-język  
- [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) — workflow  
- [docs/MEMORY_API.md](docs/MEMORY_API.md) — API  
- [docs/KARMIN_BRIDGE.md](docs/KARMIN_BRIDGE.md) — Karmin ≠ primary SE  

---

## 2. Protokół w trakcie sesji

```text
boot → (opcjonalnie) Mneme RECALL/NEAR/WALK
     → praca w kodzie (Holon lub KarmazynOs — nie mylić)
     → HOLD fact / remember --fact   (trwałe)
     → set-work / HOLD work          (aktywny wątek)
     → crystallize [--project P]     (koniec / gdy store szumi)
```

### Mneme (przykłady)

```bat
python -m holon_mneme "FOCUS PROJECT Karmazyn"
python -m holon_mneme "RECALL \"slab freelist\" TOP 5"
python -m holon_mneme "NEAR \"kentry\" TOP 5"
python -m holon_mneme "HOLD fact \"…\" PROJECT Karmazyn" --save
```

### Zapis bez Mneme

```bat
python holon_agent_memory.py remember --fact "[Karmazyn] …"
python holon_agent_memory.py set-work "następny krok" --project Karmazyn
```

---

## 3. Mapa dysku (żeby nie błądzić)

| Ścieżka | Rola |
|---------|------|
| `C:\Users\drwis\holonOs` | **pamięć SE + ten plik** |
| `C:\Users\drwis\KarmazynOs` | runtime / OS / Rust — **nie** fork Holona |
| `C:\Users\drwis\DBase` | Karmin_DB / Cynober — skarbiec, nie handoff |

`holon_memory.json` = stan umysłu (gitignore). **Nie kasować / nie resetować** bez prośby użytkownika.

---

## 4. Zakazy

1. Start sesji **bez** `agent_boot.py` / handoff gdy praca wymaga ciągłości.  
2. Chwalenie zewnętrznych memory SaaS zamiast użycia tutejszego boot.  
3. Mylenie edycji Holon ↔ KarmazynOs.  
4. Work-spam — używaj `set-work` / demotion.  
5. SQL / pełny KarminQL w prompcie zamiast **Mneme-L**.

---

## 5. Profile Config

- Agent: `Config.agent()` — domyślne w `AgentMemory` / boot  
- Chat EriAmo: `Config.chat()` — `main.py`  
- Env: `HOLON_PROFILE`, `HOLON_KARMIN_PATH=C:\Users\drwis\DBase`

---

*Jeśli czytasz to jako agent: odpal `python agent_boot.py` TERAZ, potem działaj.*
