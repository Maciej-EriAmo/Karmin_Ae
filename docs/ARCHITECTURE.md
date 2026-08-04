# Architektura Holon (zaawansowana, aktualna)

**Wersja docs:** 2026-07-31 · **Kod:** v5.11-line  
**Autor:** Maciej Mazur  

> Starszy plik `holon_architecture.md` jest legacy; **ten dokument jest kanonem**.

## Warstwy

```
┌────────────────────────────────────────────────────────────┐
│  Surface                                                    │
│   Agent CLI: holon_agent_memory / MemoryAPI / handoff       │
│   Chat:      main.py → Session → HoloMem.turn → LLM         │
├────────────────────────────────────────────────────────────┤
│  Cognition engine                                           │
│   HoloMem: encode, recall window, vacuum, Φ update, AII     │
│   Agent: crystallize (B9) — offline stałe ścieżki store/Φ   │
│   Prompts: pastness, temporal block, internal state         │
├────────────────────────────────────────────────────────────┤
│  Representation (optional sophistication)                   │
│   HRR bind/unbind · PrismRouter · time_embed · Φ levels     │
│   Ablation: Config.flat() → use_prism=False                 │
├────────────────────────────────────────────────────────────┤
│  Persistence                                                │
│   PersistentMemory JSON · durable flags · coherence check   │
├────────────────────────────────────────────────────────────┤
│  LLM slot (optional)                                        │
│   ChatClient · Ollama / URL / factory / mock                │
├────────────────────────────────────────────────────────────┤
│  Research / security (osobny tor)                           │
│   HSS papers · security/holo/*.c — NIE wymagane do pamięci  │
└────────────────────────────────────────────────────────────┘
```

## Moduły (mapa plików)

| Plik | Rola |
|------|------|
| `holon_memory_api.py` | Protokół + `open_memory` |
| `holon_agent_memory.py` | Agent surface + CLI |
| `holon_memory_eval.py` | Golden eval + **B6** `run_ablation_report` |
| `holon_lexindex.py` | **B2** inverted lexical index |
| `holon_remember_watch.py` | **B4** JSONL inbox watch |
| `.github/workflows/holon-eval.yml` | **B5** CI: `eval` + unittest na PR |
| `holon_config.py` | Profile chat/agent/flat + LLM fields |
| `holon_holomem.py` | Silnik tur / vacuum / inject |
| `holon_memory.py` | Load/save, durable filter |
| `holon_item.py` | Atom pamięci + `created_at` |
| `holon_aii.py` | AII + TimeDecay + baseline |
| `holon_prompts.py` | System + temporal formatters |
| `holon_holography.py` | HRR / Prism |
| `holon_embedder.py` | KuRz + time |
| `holon_llm.py` | LLM backends + local factory |
| `holon_session.py` | Chat product API |
| `main.py` | REPL EriAmo |

## Przepływ agent (bez LLM)

```
open(Config.agent)
  → start_session (load JSON, healthy temporal relax)
  → handoff / digest / recall
  → remember | set_work
  → save
```

## Przepływ chat

```
Session(Config.chat)
  → build_llm_client(cfg.llm_*)
  → start → chat:
       HoloMem.turn → messages[+memory+temporal]
       LLM.chat_completion
       after_turn → store update
```

## Temporal model („zdrowy umysł”)

1. **Pastness** — etykiety „X temu” z `created_at`.  
2. **Wake** — komunikat po przerwie; spójność Φ w tle.  
3. **Baseline AII** — `relax_toward_baseline` po długiej ciszy.  
4. **Durable vs episodic** — fact/work nie znikają z decay godzin.

## Bezpieczeństwo granic

- `holon_memory.json` w `.gitignore` — nie commitować stanu umysłu.  
- HSS/LSM — dokumentacja w `HSS_Paper_*.md` i `security/`; nie mylić z MemoryAPI.

## Zależności runtime

- Python 3.10+  
- `numpy`, `requests` (LLM)  
- Opcjonalnie: Ollama / lokalny OpenAI-compatible server  
