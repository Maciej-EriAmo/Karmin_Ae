# Architektura Holon (zaawansowana, aktualna)

**Wersja docs:** 2026-08-07 · **Kod:** v5.13+ (B10 handoff · B11/B12 surface · compact default)  
**Autor:** Maciej Mazur  

> Starszy plik `holon_architecture.md` jest legacy; **ten dokument jest kanonem**.

## Warstwy

```
┌────────────────────────────────────────────────────────────┐
│  Surface                                                    │
│   Agent:  agent_boot / MemoryAPI / handoff (compact)        │
│   Human:  START.cmd / karmin_app                            │
│   Chat:   main*.py → Session → HoloMem.turn → LLM           │
├────────────────────────────────────────────────────────────┤
│  Cognition engine                                           │
│   HoloMem: encode, recall, vacuum, Φ, AII (proto-emocje)    │
│   Agent: crystallize (B9) — stałe ścieżki store/Φ           │
│   Prompts: pastness, temporal, STAN WEWNĘTRZNY (tło)        │
├────────────────────────────────────────────────────────────┤
│  Representation (optional sophistication)                   │
│   HRR bind/unbind · PrismRouter · time_embed · Φ levels     │
│   Ablation: Config.flat() → use_prism=False                 │
├────────────────────────────────────────────────────────────┤
│  Persistence                                                │
│   PersistentMemory JSON · durable flags · aii dict          │
├────────────────────────────────────────────────────────────┤
│  LLM slot (optional)                                        │
│   ChatClient · Ollama / URL / factory / mock                │
├────────────────────────────────────────────────────────────┤
│  Research (archiwum/)                                       │
│   HSS papers · holon_fs · security/holo/*.c — poza SE       │
└────────────────────────────────────────────────────────────┘
```

### Proto-emocje (AII) — skrót architektoniczny

**Cel produktowy:** cichy reżim uwagi i tonu (często „nieuświadomiony”), nie teatr emocji.  
**Focus** ułatwia pracę w skupieniu; **baseline** gasi napięcie po przerwie; **neutral** = spokój bez afektu na pokaz.  
**Grupa docelowa:** partner SE + sesja EriAmo — milejsza ciągłość komunikacji; nie dashboard afektu.

Pełny opis (pola, update, inject, granice): **[AII_PROTO_EMOTIONS.md](AII_PROTO_EMOTIONS.md)**.

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
3. **Baseline AII** — `relax_toward_baseline` po długiej ciszy (habituation vacuum/focus).  
4. **Durable vs episodic** — fact/work nie znikają z decay godzin.  
5. **Proto-emocje w tle** — `AIIState.update` z treści tury; inject w chat, wagi w HoloMem; nie recytować w UI.

## Bezpieczeństwo granic

- `holon_memory.json` w `.gitignore` — nie commitować stanu umysłu.  
- HSS/LSM / HolonFS — w `archiwum/` (research); nie mylić z MemoryAPI.

## Zależności runtime

- Python 3.10+  
- `numpy`, `requests` (LLM)  
- Opcjonalnie: Ollama / lokalny OpenAI-compatible server  
