# Holon — dokumentacja (indeks)

Dokumentacja jest **warstwowa**: najpierw kontrakt agenta i API, potem architektura, potem badania (HRR/HSS).

```
docs/
  README.md              ← tu jesteś
  AGENT_WORKFLOW.md      ← jak agent ma pracować z pamięcią
  MEMORY_API.md          ← remember / recall / digest / handoff / set-work / close
  B10_HANDOFF.md         ← B10 projection (hybrid since, anchors, close)
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
python agent_boot.py
python holon_agent_memory.py seed
python holon_agent_memory.py handoff --no-digest
python holon_agent_memory.py handoff --since 24h          # B1+B10 hybrid
python agent_boot.py --compact --no-banner
python holon_agent_memory.py handoff-md --out handoff.md  # B7
python holon_agent_memory.py close --work-text "…" --fact-text "…" --project Holon
python holon_agent_memory.py crystallize --dry-run        # B9
python holon_agent_memory.py ablation                     # B6
python holon_agent_memory.py eval
```

## Plan B (SE surface) — status

| # | Temat | Doc / komenda |
|---|--------|----------------|
| B1 | handoff delty | `--since 24h` · MEMORY_API |
| B2 | lexical index | `holon_lexindex.py` · store≥500 |
| B3 | Karmin mirror | KARMIN_BRIDGE |
| B4 | hooks + inbox | `on_remember` · `watch-remember` |
| B5 | CI eval | `.github/workflows/holon-eval.yml` |
| B6 | ablation | `ablation` |
| B7 | handoff → md | `handoff-md` · `agent_boot --md` |
| B8 | Mneme | MNEME.md |
| B9 | krystalizacja | `crystallize` |
| B10 | handoff projection | [B10_HANDOFF.md](B10_HANDOFF.md) · hybrid · close · compact |
| B3b | Karmin RPC | 📋 backlog |

## Dwa produkty w jednym repo

| Produkt | Wejście | Config |
|---------|---------|--------|
| **Pamięć SE / Grok** | `holon_agent_memory.py`, `holon_memory_api` | `Config.agent()` |
| **Chat EriAmo** | `main.py`, `Session` | `Config.chat()` |

Silnik (`HoloMem`, Φ, HRR) jest wspólny; **kontrakty użytkownika są rozdzielone**.
