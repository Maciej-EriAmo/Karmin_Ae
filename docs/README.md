# Karmin_Ae / Holon — dokumentacja (indeks)

Dokumentacja jest **warstwowa**: najpierw **kto startuje jak**, potem kontrakt agenta i API, potem architektura.

```
docs/
  README.md              ← tu jesteś
  USER_GUIDE.md          ← instrukcja CZŁOWIEKA (GUI / START.cmd)
  CONFIGURE.md           ← Control Center + konfigurator + język
  AGENT_WORKFLOW.md      ← jak AGENT ma pracować z pamięcią
  MEMORY_API.md          ← remember / recall / digest / handoff / set-work / close
  B10_HANDOFF.md         ← B10 projection (hybrid since, anchors, close)
  ARCHITECTURE.md        ← moduły, przepływ, profile
  ROADMAP.md             ← plan rozwoju (wykonany + backlog)
  LLM_SLOT.md            ← wszczep lokalnego modelu
  KARMIN_BRIDGE.md       ← Karmin_DB mirror (nie SQLite)
  MNEME.md               ← mała baza SE + meta-język (Mneme-L)
AGENTS.md                ← kontrakt startowy AGENTA (root)
README.md                ← landing
START.cmd                ← dwuklik → Control Center (człowiek)
```

## KANON startu

| Kto | Komenda |
|-----|---------|
| **Człowiek** | `START.cmd` → [USER_GUIDE.md](USER_GUIDE.md) |
| **Chat / brainstorm** | `START_CHAT.cmd` |
| **Agent SE** | `python agent_boot.py` → [AGENTS.md](../AGENTS.md) |

## Szybki start

```bat
pip install -r requirements.txt
START.cmd
```

### Advanced

```bat
python agent_boot.py --since 24h --compact --no-banner
python karmin_app.py --status
python holon_agent_memory.py crystallize --project Holon
python holon_agent_memory.py eval
python holon_configure.py help
python -m holon_mneme --repl
```

Workflow agenta: [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md) · configure: [CONFIGURE.md](CONFIGURE.md).

## Plan B / B+ (SE surface) — status

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
| B10 | handoff projection | [B10_HANDOFF.md](B10_HANDOFF.md) |
| B11 | konfigurator + doctor + PL/EN | [CONFIGURE.md](CONFIGURE.md) |
| B12 | Control Center + `surfaces` | [USER_GUIDE.md](USER_GUIDE.md) · `START.cmd` |
| B3b | Karmin RPC | 📋 backlog |

## Produkty w repo

| Produkt | Wejście | Config |
|---------|---------|--------|
| **Pamięć SE / Grok** | `agent_boot`, `holon_agent_memory`, MemoryAPI | `Config.agent()` / settings |
| **Panel człowieka** | `START.cmd`, `karmin_app.py` | GUI |
| **Chat EriAmo** | `main.py`, `Session` | `Config.chat()` |

Silnik (`HoloMem`, Φ, HRR) jest wspólny; **kontrakty użytkownika są rozdzielone**.