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

| # | Deliverable | Po co agentowi |
|---|-------------|----------------|
| B1 | `handoff --since 24h` — tylko delty | mniej tokenów przy długim store |
| B2 | Lekki indeks lexical (inverted) przy store>500 | szybszy recall |
| B3 | Opcjonalny SQLite backend za tym samym API | multi-session / backup |
| B4 | Hook `on_remember` / file watch dla tooli zewnętrznych | integracja IDE |
| B5 | CI: `python holon_agent_memory.py eval` na PR | nie psuć golden |
| B6 | Golden ablation report (flat vs prism) 1 komenda | świadome HRR |
| B7 | Eksport handoff → `.md` do wklejenia w inne tooli | Grok/Cursor bridge |

## Plan C — research (nie blokuje SE)

- Ablacje HRR / Φ w paper-style  
- HSS / LSM — osobny tor `security/`  
- Chat UX EriAmo — poza MemoryAPI  

## Zasady rozwoju

1. **Najpierw kontrakt agenta**, potem ontologia Φ.  
2. Każda zmiana trwałości → nowy check w `holon_memory_eval`.  
3. Docs w `docs/` aktualizować w tym samym PR co API.  
4. Stan `holon_memory.json` nigdy w gicie.
