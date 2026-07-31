# Roadmapa Holon (pamięć SE + silnik)

## Cel nadrzędny

Holon ma być **najlepszą lokalną pamięcią partnera SE** (Grok/CLI): trwałą, czasową, testowalną — nie „holograficznym SaaS”.

## Plan A — „żeby agentowi się lepiej pracowało” (wykonany 2026-07-31)

| # | Deliverable | Status |
|---|-------------|--------|
| A1 | Profile `Config.agent/chat/flat` + rozdział Session vs AgentMemory | ✅ |
| A2 | Cienkie `MemoryAPI` + `open_memory` | ✅ |
| A3 | Golden eval + CLI `eval` | ✅ |
| A4 | LLM slot (factory, URL, mock) | ✅ |
| A5 | Healthy temporal (pastness, baseline AII, timeline w digest/chat) | ✅ |
| A6 | **`handoff` JSON v1** — bootstrap sesji | ✅ |
| A7 | **`set-work` + demotion** — mniej work-spamu | ✅ |
| A8 | Prefiks / filtr `--project` | ✅ |
| A9 | **Docs zaawansowane** (`docs/*`, `AGENTS.md`) | ✅ |
| A10 | Seed v2 + szczery README kanon | ✅ |

## Plan B — backlog (priorytet SE)

| # | Deliverable | Status / po co |
|---|-------------|----------------|
| B1 | `handoff --since 24h` — tylko delty | 📋 mniej tokenów |
| B2 | Lekki indeks lexical (inverted) przy store>500 | 📋 szybszy recall |
| B3 | **Karmin_DB mirror** (**nie SQLite**) — `holon_backend_karmin` + CLI export/import | ✅ 2026-07-31 |
| B4 | Hook `on_remember` / file watch dla tooli zewnętrznych | 📋 IDE |
| B5 | CI: `python holon_agent_memory.py eval` na PR | 📋 |
| B6 | Golden ablation report (flat vs prism) 1 komenda | 📋 |
| B7 | Eksport handoff → `.md` | 📋 |
| B3b | Karmin RPC / świat `se_memory` (Cynober server) | 📋 po B3 lokalnym |
| B8 | **Mneme** — meta-język + jawny graf SE (`docs/MNEME.md`, `holon_mneme.py`) | ✅ design+M1–M3 |

## Plan C — research (nie blokuje SE)

- Ablacje HRR / Φ w paper-style  
- HSS / LSM — osobny tor `security/`  
- Chat UX EriAmo — poza MemoryAPI  

## Zasady rozwoju

1. **Najpierw kontrakt agenta**, potem ontologia Φ.  
2. Każda zmiana trwałości → nowy check w `holon_memory_eval`.  
3. Docs w `docs/` aktualizować w tym samym PR co API.  
4. Stan `holon_memory.json` nigdy w gicie.
