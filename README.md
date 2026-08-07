# Karmin_Ae (Agent Edition)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-advanced-blue.svg)](docs/README.md)

**Trwała, lokalna pamięć SE dla agenta (Grok/CLI) i sesji czatu EriAmo.**  
**Widzialna marka:** **Karmin_Ae** — *Agent Edition* (nie mylić z **Karmin_DB** / skarbcem).  
**Silnik w kodzie:** Holon (`holon_*.py`) — nazwy plików bez wymuszonego rename.  
**Wersja:** **v5.13+** — Plan B + B10 handoff · B11 configure · **B12 Control Center** (GUI dla człowieka).

> Dawniej workspace/repo: *holonOs* (kolizja nazwy zewnętrznej).  
> Katalog i repo: **Karmin_Ae**. Pliki `holon_*` mogą zostać.

HRR / macierz Φ / HSS to warstwy badawcze w tym samym monorepo.  
**Wartość codzienna:** fact · work · pastness · handoff · inject do promptu — bez GPU.  
**W tle:** proto-emocje AII (focus, vacuum, spokój) — cichy boost tonu i skupienia, nie teatr; [docs/AII_PROTO_EMOTIONS.md](docs/AII_PROTO_EMOTIONS.md).

---

## KANON startu (tylko to na co dzień)

| Kto | Komenda |
|-----|---------|
| **Człowiek** | `START.cmd` |
| **Chat / brainstorm** | `START_CHAT.cmd` (albo przycisk w panelu) |
| **Agent SE** | `python agent_boot.py` |

Reszta (configure, Mneme, eval, power CLI) = **advanced** — niżej i w [docs/](docs/README.md).

---

## Kanon (warstwy)

| Warstwa | Wejście | Status |
|---------|---------|--------|
| **Pamięć agenta** | `holon_agent_memory.py`, `MemoryAPI` | **Produkt SE** — `Config.agent()` |
| **Chat EriAmo** | `main.py` → `Session` | **Produkt chat** — `Config.chat()` |
| **Silnik Holon** | `HoloMem`, embedder, vacuum | wspólny (wewnętrzna nazwa) |
| **HRR / Prism / Φ** | `holon_holography.py` | opcjonalna złożoność; ablacja `Config.flat()` |
| **HSS / LSM / HolonFS** | `archiwum/` | research / martwe dema — **nie** część MemoryAPI |

Szczegóły: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** · Agent: **[AGENTS.md](AGENTS.md)**

**Karmin_DB** (skarbiec, mirror) ≠ **Karmin_Ae** (pamięć agenta). Patrz [docs/KARMIN_BRIDGE.md](docs/KARMIN_BRIDGE.md).

---

## Quick start

```bat
cd C:\Users\drwis\Karmin_Ae
pip install -r requirements.txt
START.cmd
```

- Panel: Start · Sesja · Pamięć · Konsola · Ustawienia · linia poleceń na dole.  
- Pełna instrukcja człowieka: **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**.  
- Agent: **[AGENTS.md](AGENTS.md)**.

### Advanced (power-user / agent)

```bat
python agent_boot.py --project Karmazyn
python agent_boot.py --since 24h --compact --no-banner
python karmin_app.py --status
python karmin_app.py -c "help"
python holon_agent_memory.py crystallize --project Holon
python holon_agent_memory.py eval
python holon_configure.py help
python -m holon_mneme --repl
```

`holon_configure` = **advanced** settings (presety/doctor/env); codzienność = Control Center (`START.cmd`).

```python
from holon_memory_api import open_memory

mem = open_memory()  # Config.agent()
print(mem.handoff(project="Karmazyn", include_digest=False, since="24h"))
mem.remember("[Karmazyn] ...", kind="fact")
mem.set_work("...", project="Karmazyn")
mem.close(work="next ...", fact="summary ...", project="Karmazyn")  # B10
mem.on_remember(lambda item, **kw: None)  # B4
mem.crystallize(project="Holon")          # B9
mem.save()
```

Patrz też: [AGENTS.md](AGENTS.md) (kontrakt startowy).

---

## Konfigurator i panel — krótka instrukcja

Lokalny setup pamięci SE (nie SaaS). **`holon_settings.json`** = preferencje (gitignore); **`holon_memory.json`** = stan umysłu.

| Krok | Człowiek (GUI) | CLI |
|------|----------------|-----|
| 1. Start | **`START.cmd`** | `python karmin_app.py` |
| 2. Setup | zakładka Ustawienia | `python holon_configure.py wizard` |
| 3. Doctor | przycisk Doctor | `python holon_configure.py doctor` |
| 4. Agent | (nie musi) | `python agent_boot.py` |
| Help | zakładka Pomoc | `python holon_configure.py help` |

**Presety:** `se` (ciągłość) · `se-compact` (mniej tokenów) · `se-long` · `chat` · `lab-flat`

```bat
python holon_configure.py use se-compact
python holon_configure.py set default_project Karmazyn
python holon_configure.py set-override handoff_max_facts 4
```

### Język PL / EN

| Sposób | Przykład |
|--------|----------|
| Jednorazowo (CLI) | `python holon_configure.py --lang en help` |
| Trwale w settings | `python holon_configure.py set ui_lang en` |
| Skrót | `python holon_configure.py lang en` |
| Env | `set HOLON_UI_LANG=en` |
| GUI | przełącznik **Język / Language** |

Kolejność: `--lang` → `HOLON_UI_LANG` → `ui_lang` w pliku → **pl**.

Pełny opis: [docs/CONFIGURE.md](docs/CONFIGURE.md) · instrukcja człowieka: [docs/USER_GUIDE.md](docs/USER_GUIDE.md) · w programie: `python holon_configure.py help`.

---

## Dokumentacja

| Doc | Opis |
|------|------|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | **Instrukcja obsługi (człowiek / GUI)** |
| [docs/AII_PROTO_EMOTIONS.md](docs/AII_PROTO_EMOTIONS.md) | Proto-emocje AII — kod + grupa docelowa |
| [docs/CONFIGURE.md](docs/CONFIGURE.md) | Control Center + konfigurator + język PL/EN |
| [docs/README.md](docs/README.md) | Indeks docs |
| [AGENTS.md](AGENTS.md) | Kontrakt startowy **agenta** |
| [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) | Workflow SE end-to-end |
| [docs/MEMORY_API.md](docs/MEMORY_API.md) | API + CLI + handoff schema |
| [docs/B10_HANDOFF.md](docs/B10_HANDOFF.md) | B10 projection (hybrid · close · anchors) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architektura zaawansowana |
| [docs/LLM_SLOT.md](docs/LLM_SLOT.md) | Lokalny model / Ollama / URL |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Plan A/B + B11/B12 |
| [docs/KARMIN_BRIDGE.md](docs/KARMIN_BRIDGE.md) | **Karmin_DB** mirror/backup (**nie** Karmin_Ae) |
| [docs/MNEME.md](docs/MNEME.md) | Mneme-L (meta-język SE) |

---

## Repo

- **GitHub:** `https://github.com/Maciej-EriAmo/Karmin_Ae`  
- **Katalog lokalny:** `C:\Users\drwis\Karmin_Ae`  
- **Silnik (pliki):** nadal `holon_*.py` — rename opcjonalny, nie wymagany  

---

## License

MIT — zob. [LICENSE](LICENSE).
