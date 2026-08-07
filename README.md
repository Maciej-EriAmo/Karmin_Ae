# Karmin_Ae (Agent Edition)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-advanced-blue.svg)](docs/README.md)

**Trwała, lokalna pamięć SE dla agenta (Grok/CLI) i sesji czatu EriAmo.**  
**Widzialna marka:** **Karmin_Ae** — *Agent Edition* (nie mylić z **Karmin_DB** / skarbcem).  
**Silnik w kodzie:** Holon (`holon_*.py`) — nazwy plików bez wymuszonego rename.  
**Wersja:** **v5.13.0** — Plan B + B10 handoff projection (hybrid since · close · anchors).

> Dawniej workspace/repo: *holonOs* (kolizja nazwy zewnętrznej).  
> Katalog i repo: **Karmin_Ae**. Pliki `holon_*` mogą zostać.

HRR / macierz Φ / HSS to warstwy badawcze w tym samym monorepo.  
**Wartość codzienna:** fact · work · pastness · handoff · inject do promptu — bez GPU.

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

## Quick start (pamięć SE)

```bash
cd C:\Users\drwis\Karmin_Ae
pip install -r requirements.txt

# === START DLA AGENTA (jedna komenda) ===
python agent_boot.py
# python agent_boot.py --project Karmazyn
# python agent_boot.py --no-banner

python holon_agent_memory.py seed          # raz / odswiezenie kotwic
python -m holon_mneme --repl               # meta-jezyk + graf
python holon_agent_memory.py remember --fact "[Holon] ..."
python holon_agent_memory.py set-work "..." --project Karmazyn
python holon_agent_memory.py close --work-text "..." --fact-text "..." --project Karmazyn
python holon_agent_memory.py crystallize --project Holon   # B9 sciezki
python agent_boot.py --since 24h                             # B1+B10 hybrid
python agent_boot.py --compact --no-banner
python agent_boot.py --md --out handoff.md                   # B7 markdown
python holon_agent_memory.py eval
python holon_agent_memory.py ablation                       # B6 flat vs prism

# === KONFIGURATOR (profile / handoff / LLM / doctor) ===
python holon_configure.py wizard
python holon_configure.py doctor
python holon_configure.py gui                               # okienko tkinter
```

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

Patrz tez: [AGENTS.md](AGENTS.md) (kontrakt startowy).

---

## Dokumentacja

| Doc | Opis |
|------|------|
| [docs/README.md](docs/README.md) | Indeks |
| [AGENTS.md](AGENTS.md) | Kontrakt startowy agenta |
| [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) | Workflow SE end-to-end |
| [docs/MEMORY_API.md](docs/MEMORY_API.md) | API + CLI + handoff schema |
| [docs/B10_HANDOFF.md](docs/B10_HANDOFF.md) | B10 projection (hybrid · close · anchors) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architektura zaawansowana |
| [docs/LLM_SLOT.md](docs/LLM_SLOT.md) | Lokalny model / Ollama / URL |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Plan A (done) + backlog B/C |
| [docs/KARMIN_BRIDGE.md](docs/KARMIN_BRIDGE.md) | **Karmin_DB** mirror/backup (**nie** Karmin_Ae) |
| [docs/MNEME.md](docs/MNEME.md) | Mneme-L (meta-język SE) |
| [docs/CONFIGURE.md](docs/CONFIGURE.md) | Konfigurator CLI + GUI + doctor |

---

## Repo

- **GitHub:** `https://github.com/Maciej-EriAmo/Karmin_Ae`  
- **Katalog lokalny:** `C:\Users\drwis\Karmin_Ae`  
- **Silnik (pliki):** nadal `holon_*.py` — rename opcjonalny, nie wymagany  

---

## License

MIT — zob. [LICENSE](LICENSE).
