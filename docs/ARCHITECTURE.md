# Architektura Holon (zaawansowana, aktualna)

**Wersja docs:** 2026-09-01 · **Kod:** v5.13+ (B10 · komory · Bridge→Prism · entangle)  
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
│   Agent: crystallize (B9) · chambers · entangle             │
│   Prompts: pastness, temporal, STAN WEWNĘTRZNY (tło)        │
├────────────────────────────────────────────────────────────┤
│  Representation                                             │
│   Embedder (KuRz|hash + time) → Item store                  │
│   Bridge Transformer (agent ON) — mixer tokenów+sondy       │
│     ↳ bez Embeddera.encode; wejście = gotowe wektory Item   │
│   PrismRouter — teleport na poziomy Φ (wagi + faza)         │
│   Ablation: Config.flat() → use_prism=False, use_bridge=False│
├────────────────────────────────────────────────────────────┤
│  Persistence                                                │
│   %LOCALAPPDATA%\Karmin_Ae\holon_memory.json (HOLON_DATA_HOME)│
│   durable flags · aii · meta last_project / chambers        │
├────────────────────────────────────────────────────────────┤
│  LLM slot (optional)                                        │
│   ChatClient · Ollama / URL / factory / mock                │
├────────────────────────────────────────────────────────────┤
│  Research (archiwum/ · Transformers/bridge_transformer)     │
│   HSS · źródło transform.py (HOLON_BRIDGE_PATH)             │
└────────────────────────────────────────────────────────────┘
```

## Jak działa pamięć (tor SE)

1. **Zapis (`remember`)** — treść dostaje prefiks komory `[P]`; Embedder → wektor; merge tylko **w tej samej komorze**; lekki szum+renorm po merge.  
2. **Store** — lista `Item` (fact/work/…) w JSON poza repo.  
3. **Recall** — cosine + lexical; obca komora vs kurek (`last_project`) dostaje **karę**, nie twarde odcięcie.  
4. **Update Φ (`_update_phi`)** — z aktywnego okna budowany jest pattern:  
   - klasycznie: ważona suma embeddingów;  
   - **agent + `use_bridge`**: Itemy jako tokeny + sonda (relevance/age) → **Bridge** (Lorentzian attention z `transform.py`) → wektor;  
   - **Prism** rozdziela ten wektor na `phi_levels` (miękkie wagi + przesunięcie fazy).  
5. **Handoff / boot** — projekcja komory: 1 work + facts z `[P]`, `recommended_actions`, surfaces agent/human.  
6. **Crystallize** — offline merge ścieżek (domyślnie **bez** cross-chamber; `--cross-project` tylko świadomie).  
7. **Entangle** — metryka fact↔work (pairwise poza przekątną).

Szczegóły Bridge: [BRIDGE.md](BRIDGE.md). Komory: [B10_HANDOFF.md](B10_HANDOFF.md) · [AGENTS.md](../AGENTS.md).

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
| `holon_bridge.py` | BridgeStack: `transform.py` → Prism teleport (bez Embeddera) |
| `holon_embedder.py` | KuRz + time (hash fallback) |
| `holon_llm.py` | LLM backends + local factory |
| `holon_session.py` | Chat product API |
| `scripts/bench_bridge_vs_prism.py` | bench Bridge vs Softmax + Prism vs flat |
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

## Profile a Bridge / Prism

| Profil | `use_prism` | `use_bridge` | Uwagi |
|--------|-------------|--------------|--------|
| `Config.agent()` | on | **on** | SE / Grok; Bridge wymaga torch + `transform.py` |
| `Config.chat()` | on | off | nie spowalnia czatu kalibracją |
| `Config.flat()` | **off** | **off** | ablacja |

`HOLON_USE_BRIDGE=0|1` nadpisuje. Brak Bridge → cichy fallback na klasyczny pattern (status `unavailable:…` w `stats()`).

## Zależności runtime

- Python 3.10+  
- `numpy`, `requests` (LLM)  
- Opcjonalnie: Ollama / lokalny OpenAI-compatible server  
- Opcjonalnie (Bridge): `torch` + plik `Transformers/bridge_transformer/transform.py` (lub `HOLON_BRIDGE_PATH`)  
