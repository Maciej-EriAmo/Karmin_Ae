# AGENTS.md — ścieżka dla Grok / CLI (czytaj TO najpierw)

> **Karmin_Ae (Agent Edition)** — widzialna marka · silnik Holon v5.13 w plikach `holon_*`.  
> Plan B + B10 (boot · hybrid since · close · anchors · crystallize · handoff-md · Mneme-L).  
> **Cudze chwalicie, swego nie znacie.**  
> W tym workspace pamięć SE **już jest**: Karmin_Ae / Holon engine + handoff.  
> Nie szukaj Mem0 / SQLite / „jakiejś bazy” — **odpal boot**.  
> **Karmin_Ae ≠ Karmin_DB** (skarbiec).  
> **AII / proto-emocje** działają w tle (focus, vacuum, spokój) — nie recytuj ich; treść SE = work/facts.  
> Docs: [docs/AII_PROTO_EMOTIONS.md](docs/AII_PROTO_EMOTIONS.md).

### KANON (nie myl torów)

| Kto | Start | Nie rób |
|-----|--------|---------|
| **Ty (agent)** | `python agent_boot.py` | Nie otwieraj GUI zamiast boot |
| **Człowiek** | `START.cmd` | Nie musi znać CLI |
| **Chat / brainstorm** | `START_CHAT.cmd` / panel | To nie jest boot SE |

Handoff JSON zawiera pole **`surfaces`**: `agent` vs `human`.  
Szybki stan: `python karmin_app.py --status` albo `python holon_agent_memory.py status`.

---

## 0. OBOWIĄZKOWY START SESJI (jedna komenda)

```bat
cd /d C:\Users\drwis\Karmin_Ae
python agent_boot.py
```

**Domyślnie compact** (1 work, ≤3 facts, silne `recommended_actions`, bez chronicle).  
Pełniejszy handoff: `python agent_boot.py --rich`.  
Boot **egzekwuje max 1 work** na projekt (nadmiar → fact).

Z filtrem projektu:

```bat
python agent_boot.py --project Karmazyn
python agent_boot.py --project Holon
```

Re-boot / delty (**B1+B10** hybrid work spoza okna):

```bat
python agent_boot.py --since 24h
python agent_boot.py --since 24h --project Holon
python agent_boot.py --no-banner
python agent_boot.py --rich --project Holon
```

Alias Windows: `agent_boot.cmd` · PowerShell: `.\agent_boot.ps1`

**Po bootcie:** kontekst = `active_work` + `anchors`/`key_facts` + `recommended_actions` + `when`.  
Bez `--project`: last project z meta / `HOLON_DEFAULT_PROJECT`.  
Nie zmyślaj „stanu projektu” z powietrza.

---

## 1. Co tu MACIE (wasze, nie cudze)

| Narzędzie | Po co | Komenda |
|-----------|--------|---------|
| **karmin_app** | panel człowieka (GUI) | `START.cmd` / `python karmin_app.py` · [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| **status** | stan JSON (agent+human) | `python karmin_app.py --status` |
| **agent_boot** | bootstrap JSON | `python agent_boot.py` |
| **assist (helper)** | **pomocnik SE dla agenta** (orient / draft-close / ask) | `python holon_agent_memory.py assist` · lokalnie Ollama `gemma3:4b` · opc. cloud Gemini |
| **karmin_session** | prosty rytuał (alias) | `python karmin_session.py start\|work\|fact\|done` |
| **Handoff** | ten sam protokół w API | `python holon_agent_memory.py handoff --no-digest` |
| **handoff-md** | B7 — handoff jako Markdown | `python holon_agent_memory.py handoff-md --out handoff.md` |
| **Mneme-L** | zapytywalna pamięć + graf | `python -m holon_mneme --repl` |
| **remember / set-work** | zapis fact/work (1 work domyślnie) | `python holon_agent_memory.py remember --fact "…"` |
| **close** | B10 — koniec sesji work+fact | `python holon_agent_memory.py close --work-text "…" --fact-text "…" --project P` |
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
boot → assist (Ollama gemma3:4b)   (python holon_agent_memory.py assist)
     → (opcjonalnie) suggested_mneme / RECALL/NEAR/WALK
     → praca w kodzie (Holon lub KarmazynOs — nie mylić)
     → HOLD fact / remember --fact   (trwałe)
     → set-work / HOLD work          (1 aktywny wątek)
     → assist --task draft-close     (draft WORK/FACT; agent zatwierdza)
     → close --work-text --fact-text (preferowane domknięcie)
     → crystallize [--project P]     (gdy store szumi)
```

**Pomocnik agenta** = `helper_llm_*` (domyślnie **Ollama / gemma3:4b**). Chat człowieka = `llm_*` (też może być Ollama).

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
| `C:\Users\drwis\Karmin_Ae` | **pamięć SE (Karmin_Ae) + ten plik** · dawniej holonOs |
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

- Agent: `Config.agent()` / `Config.from_settings()` — `AgentMemory` / boot  
- Chat EriAmo: `Config.chat()` — `main.py`  
- **Konfigurator:** `python holon_configure.py help` · `wizard` · `doctor` · `gui`  
  → `holon_settings.json` (gitignore); język: `--lang en` / `set ui_lang en` / `HOLON_UI_LANG`  
  docs: [docs/CONFIGURE.md](docs/CONFIGURE.md)  
- Env: `HOLON_PROFILE`, `HOLON_DEFAULT_PROJECT`, `HOLON_LLM_*`, `HOLON_UI_LANG`, `HOLON_KARMIN_PATH`

---

*Jeśli czytasz to jako agent: odpal `python agent_boot.py` TERAZ, potem działaj.*
