# Holon — dokumentacja (indeks)

Dokumentacja jest **warstwowa**: najpierw kontrakt agenta i API, potem architektura, potem badania (HRR/HSS).

```
docs/
  README.md              ← tu jesteś
  AGENT_WORKFLOW.md      ← jak agent ma pracować z pamięcią
  MEMORY_API.md          ← remember / recall / digest / handoff / set-work
  ARCHITECTURE.md        ← moduły, przepływ, profile
  ROADMAP.md             ← plan rozwoju (wykonany + backlog)
  LLM_SLOT.md            ← wszczep lokalnego modelu
  KARMIN_BRIDGE.md       ← Karmin_DB mirror (nie SQLite)
  MNEME.md               ← mała baza SE + meta-język (Mneme-L)
AGENTS.md                ← skrót kontraktu (root, dla tooli)
README.md                ← landing + szczery kanon
holon_architecture.md    ← legacy pointer → docs/ARCHITECTURE.md
```

## Szybki start

```bash
pip install -r requirements.txt
python holon_agent_memory.py seed
python holon_agent_memory.py handoff --no-digest
python holon_agent_memory.py eval
```

## Dwa produkty w jednym repo

| Produkt | Wejście | Config |
|---------|---------|--------|
| **Pamięć SE / Grok** | `holon_agent_memory.py`, `holon_memory_api` | `Config.agent()` |
| **Chat EriAmo** | `main.py`, `Session` | `Config.chat()` |

Silnik (`HoloMem`, Φ, HRR) jest wspólny; **kontrakty użytkownika są rozdzielone**.
