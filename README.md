# Holon

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-advanced-blue.svg)](docs/README.md)

**Trwała, czasowa pamięć lokalna dla agenta SE (Grok/CLI) i sesji czatu EriAmo.**

HRR / macierz Φ / HSS to warstwy badawcze w tym samym monorepo.  
**Wartość codzienna:** fact · work · pastness · handoff · inject do promptu — bez GPU.

---

## Kanon (warstwy)

| Warstwa | Wejście | Status |
|---------|---------|--------|
| **Pamięć agenta** | `holon_agent_memory.py`, `MemoryAPI` | **Produkt SE** — `Config.agent()` |
| **Chat EriAmo** | `main.py` → `Session` | **Produkt chat** — `Config.chat()` |
| **Silnik** | `HoloMem`, embedder, vacuum | wspólny |
| **HRR / Prism / Φ** | `holon_holography.py` | opcjonalna złożoność; ablacja `Config.flat()` |
| **HSS / LSM** | `HSS_Paper_*.md`, `security/` | research security — **nie** część MemoryAPI |

Szczegóły: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** · Agent: **[AGENTS.md](AGENTS.md)**

---

## Quick start (pamięć SE)

```bash
pip install -r requirements.txt

# bootstrap store + kotwice
python holon_agent_memory.py seed

# start sesji agenta (JSON)
python holon_agent_memory.py handoff --no-digest

# zapis
python holon_agent_memory.py remember --fact "[Holon] …"
python holon_agent_memory.py set-work "Następny wątek" --project Karmazyn

# reggresja
python holon_agent_memory.py eval
```

```python
from holon_memory_api import open_memory

mem = open_memory()  # Config.agent()
print(mem.handoff(project="Karmazyn", include_digest=False))
mem.remember("[Karmazyn] …", kind="fact")
mem.set_work("…", project="Karmazyn")
mem.save()
```

---

## Dokumentacja

| Doc | Opis |
|------|------|
| [docs/README.md](docs/README.md) | Indeks |
| [AGENTS.md](AGENTS.md) | Kontrakt startowy agenta |
| [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) | Workflow SE end-to-end |
| [docs/MEMORY_API.md](docs/MEMORY_API.md) | API + CLI + handoff schema |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architektura zaawansowana |
| [docs/LLM_SLOT.md](docs/LLM_SLOT.md) | Lokalny model / Ollama / URL |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Plan A (done) + backlog B/C |
| [docs/KARMIN_BRIDGE.md](docs/KARMIN_BRIDGE.md) | **Karmin_DB** mirror/backup (**nie SQLite**) |
| [docs/MNEME.md](docs/MNEME.md) | **Mneme** — mała baza SE + meta-język (graf + RECALL) |

---

## Profile i env

```text
Config.chat()    # main.py / Session
Config.agent()   # AgentMemory (domyślnie)
Config.flat()    # bez Prism

HOLON_PROFILE=agent|chat|flat
HOLON_LLM_BACKEND=auto|local|ollama|openai|mock
HOLON_LLM_BASE_URL=http://127.0.0.1:8080/v1
```

---

## Chat (EriAmo)

```bash
python main.py
```

Wymaga backendu LLM (Ollama / klucz API / local URL) — patrz [docs/LLM_SLOT.md](docs/LLM_SLOT.md).  
Bez LLM pamięć agentowa nadal działa.

---

## HSS (research)

Osobny tor: paper `HSS_Paper_v2.5.0.md` (+ PL), kod `security/holo/`, demo `hss_demo.py`.  
**Nie jest wymagany** do `remember` / `handoff`.

---

## Metryki

| Źródło | Znaczenie |
|--------|-----------|
| `python holon_agent_memory.py eval` | **Kanoniczna** reggresja pamięci (golden) |
| Wewnętrzne demo recall / HSS 20/20 | Lab / paper — nie public leaderboard vs Mem0 |

---

## Licencja

MIT — [LICENSE](LICENSE)

**Stan umysłu** (`holon_memory.json`, `*_kurz.json`) jest w `.gitignore` i nie trafia do repo.
