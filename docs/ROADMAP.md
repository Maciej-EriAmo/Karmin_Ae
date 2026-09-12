# Roadmapa Holon (pamięć SE + silnik)

**Wersja produktu:** **v5.13.0** (2026-08) — Plan B + **B10** handoff projection.  
Poprzednia: v5.12.0 (B1–B9); linia chat/silnik: v5.11.

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
| B1 | `handoff --since 24h` — tylko delty | ✅ 2026-08 (mniej tokenów) |
| B2 | Lekki indeks lexical (inverted) przy store>500 | ✅ 2026-08 (`holon_lexindex`) |
| B3 | **Karmin_DB mirror** (**nie SQLite**) — `holon_backend_karmin` + CLI export/import | ✅ 2026-07-31 |
| B4 | Hook `on_remember` / file watch dla tooli zewnętrznych | ✅ 2026-08 (hooks + `watch-remember`) |
| B5 | CI: `python holon_agent_memory.py eval` na PR | ✅ 2026-08 (`.github/workflows/holon-eval.yml`) |
| B6 | Golden ablation report (flat vs prism) 1 komenda | ✅ 2026-08 (`ablation`) |
| B7 | Eksport handoff → `.md` | ✅ 2026-08 (`handoff-md` / `agent_boot --md`) |
| B3b | Karmin RPC / świat `se_memory` (Cynober server) | 📋 po B3 lokalnym |
| B8 | **Mneme** — meta-język + jawny graf SE (`docs/MNEME.md`, `holon_mneme.py`) | ✅ design+M1–M3 |
| B9 | **Krystalizacja** — offline utrwalanie stałych ścieżek (`crystallize`) | ✅ v1 2026-08 |
| B10 | **Handoff projection** — hybrid since, anchors/chronicle, close, compact, last-project | ✅ v5.13 2026-08 |

### Plan B — domknięcie (2026-08)

Surface SE pod Grok/CLI: **B1–B10** (bez B3b).  
Start: `agent_boot` · hybrid delty · md · close · crystallize · lex · hooks · CI · ablation · Mneme · Karmin mirror.

Otwarte w Plan B: tylko **B3b** (Karmin RPC / `se_memory`).  
Doc B10: [B10_HANDOFF.md](B10_HANDOFF.md).

## Plan B+ — product surface (2026-08)

| # | Deliverable | Status |
|---|-------------|--------|
| B11 | **Konfigurator** CLI + GUI + doctor (presety SE, `holon_settings.json`) | ✅ 2026-08 |
| B12 | **Control Center** `karmin_app` / `START.cmd` — norma UX dla człowieka; `surfaces` w handoff | ✅ 2026-08 |
| B13 | **Komory** enter/leave — 1 work na projekt, bęben w meta, `--all-projects` nie ścina globalnie | ✅ 2026-08 |
| B14 | **Bridge→Prism** — `transform.py` mixer (bez Embeddera) w `_update_phi`; entangle; docs/BRIDGE.md | ✅ 2026-09 |
| B14b | **energia→routing** — `bridge_energy_importance(tracer)` → Prism `p[lv]` (wielowymiarowy tor); ablacja flagą | ✅ 2026-09-03 |

## Utrzymanie / refaktor (2026-09-12)

Sesja porządkowa — audyt repo + dogfooding (boot jako agent inny niż Grok, żeby
sprawdzić że silnik jest agent-agnostyczny) ujawniły kilka realnych driftów;
poprawione po kolei, każde z pełnym test suite + golden eval + CI:

| # | Zmiana | Commit |
|---|--------|--------|
| M1 | `Session`/`SecureSession`/`AwareSession` — realne dziedziczenie (`AwareSession(SecureSession(Session))`) zamiast trzech kopii pętli chat | `0c77b66` |
| M2 | `AGENT_SEED` — opis agenta CLI neutralny (nie tylko Grok) | `0c77b66` |
| M3 | `doctor` / `karmin_app --status` realnie sondują `bridge_status` (tania sonda, `bridge_calibrate_steps=0`) zamiast pokazywać wieczny `pending` | `01270b1` |
| M4 | `agent_boot.py` handoff niesie `bridge_status` / `bridge_energy` (agent widzi od razu czy Bridge→Prism działa) | `711a243` |
| M5 | Wspólna pętla REPL (`holon_repl.py`) dla `main.py` / `main_secure.py` / `main_aware.py` | `f6fc931` |
| M6 | CLI-dispatch wydzielony z `holon_agent_memory.py` do `holon_agent_cli.py` (2691→2206 linii biblioteki) | `107e5a6` |
| — | CI: `actions/checkout` + `actions/setup-python` → v7 (koniec ostrzeżenia Node.js 20) | `71dd5dc` |

Przy okazji M1 wyszły na jaw dwa realne driftowe błędy w `AwareSession` (dziedziczyła
kopiuj-wklej, nie klasę): słabszy log audytu bezpieczeństwa (brakowało `matches`/
`intent_score`) i parser przypomnień bez fallbacku `dateutil`. Naprawione samym
dziedziczeniem.

## Plan C — research (nie blokuje SE)

- Ablacje HRR / Φ w paper-style (smoke B6 już w CLI)  
- HSS / LSM / HolonFS — `archiwum/` (research, poza SE)
- Chat UX EriAmo — poza MemoryAPI  
- Mneme M4–M5 (auto-hub, prompt-only)
- Bridge: checkpoint wag na dysk / tied attention jako opcja vs `transform.py`; dłuższy trening na realnych Itemach Holona

## Zasady rozwoju

1. **Najpierw kontrakt agenta**, potem ontologia Φ.  
2. Każda zmiana trwałości → nowy check w `holon_memory_eval`.  
3. Docs w `docs/` aktualizować w tym samym PR co API.  
4. Stan `holon_memory.json` nigdy w gicie.
