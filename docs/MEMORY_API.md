# Memory API — kontrakt zaawansowany

## Powierzchnia

```python
from holon_memory_api import open_memory, MemoryAPI

mem: MemoryAPI = open_memory("holon_memory.json", profile="agent")
```

| Metoda | Semantyka |
|--------|-----------|
| `remember(content, kind)` | `fact` \| `work` \| `note`; semantic merge / exact dedupe (`remember_merge_sim`) |
| `recall(query, top_k)` | cosine + lexical boost + bonus flag |
| `digest(..., project="")` | tekst SE z pastness + osią czasu |
| `handoff(..., project="", since=None, compact=…, hybrid_since=…)` | JSON bootstrap; **B1** delta + **B10** hybrid/anchors/actions |
| `handoff_md(..., out_path=None)` | **B7** ten sam handoff jako Markdown (+ opcjonalny plik) |
| `set_work(content, project, max_active=None)` | work + demotion; domyślnie **1** aktywny (B10) |
| `close(work=…, fact=…, project=…)` | **B10** atomowe domknięcie sesji + last_project |
| `crystallize(project, dry_run=…, cross_project_merge=False)` | **B9** offline: merge near-dup (domyślnie **nie** między komorami), promote, demote work, Φ |
| `entanglement_score(project)` | metryka fact↔work (pairwise poza przekątną) |
| `on_remember(cb)` | **B4** hook po remember (add/merge) |
| `save()` | JSON + embedder dict (KuRz albo hash fallback) |
| `stats()` | turns, store, facts, work, profile, lex_index, bridge_mode/status, … |

Implementacja referencyjna: `AgentMemory` (`holon_agent_memory.py`).

## Trwałość

| Typ | `store_decay` | Ranking age |
|-----|---------------|-------------|
| fact / work / insight / reminder | **nie wygasa** (`keep_*_forever`) | `durable_age_cap` (miękki, nie kasuje `created_at`) |
| epizod / note | `store_decay_hours` (agent ≈ 90d, chat ≈ 14d) | full age |

**Zasada:** `created_at` jest kalendarzem; `age` to waga rankingu.

## Profile (`holon_config.Config`)

| Fabryka | store_decay | prune max | prism | bridge | Użycie |
|---------|-------------|-----------|-------|--------|--------|
| `Config.chat()` | 336 h | 120 | on | off | `Session`, `main.py` |
| `Config.agent()` | 2160 h | 400 | on | **on** | AgentMemory / boot |
| `Config.flat()` | jak agent | … | **off** | **off** | ablacja / lab |
| `Config.from_env()` | `HOLON_PROFILE` · `HOLON_USE_BRIDGE` | | | | env override |
| `Config.from_settings()` | `holon_settings.json` + env | | | | **konfigurator** CLI/GUI |

Bridge (agent): mixer tokenów+sondy **bez** Embeddera, potem Prism → Φ. Doc: [BRIDGE.md](BRIDGE.md).

## CLI

```bash
python holon_agent_memory.py handoff [--project P] [--since 24h] [--no-digest] [--compact] [--strict-delta]
python holon_agent_memory.py handoff-md [--project P] [--since 24h] [--out handoff.md] [digest]
python agent_boot.py [--project P] [--since 24h] [--full] [--md] [--compact] [--strict-delta] [--all-projects]
python holon_agent_memory.py digest [--project P]
python holon_agent_memory.py remember "…" --fact|--work
python holon_agent_memory.py set-work "…" --project P [--max-active 1]
python holon_agent_memory.py close --work-text "…" --fact-text "…" --project P
python holon_agent_memory.py crystallize [--project P] [--dry-run] [--sim 0.88] [--max-active 1] [--cross-project]
python holon_agent_memory.py entangle [--project P]
python holon_agent_memory.py recall "…" [--project P]
python holon_agent_memory.py ablation
python scripts/bench_bridge_vs_prism.py [--steps 600]
python holon_agent_memory.py watch-remember --inbox remember_inbox.jsonl [--once]
python holon_agent_memory.py assist [--task orient|draft-close|hygiene] [--ask "…"] [--project P]
python -m holon_helper [--task …] [--project P]
python holon_agent_memory.py seed | stats | eval | collab-test | llm-slot
python holon_configure.py show | wizard | doctor | gui | use se-compact
python holon_agent_memory.py status [--project P]
python karmin_app.py --status
```

| Powierzchnia | Doc |
|--------------|-----|
| Control Center (człowiek) | [USER_GUIDE.md](USER_GUIDE.md) · `START.cmd` |
| Konfigurator | [CONFIGURE.md](CONFIGURE.md) |
| Agent boot | [AGENTS.md](../AGENTS.md) · `handoff.surfaces` |
| Helper SE (assist) | [LLM_SLOT.md](LLM_SLOT.md) · `holon_helper.py` |

### `surfaces` w handoff (B12)

```json
"surfaces": {
  "agent": { "boot": "python agent_boot.py", "status_json": "python karmin_app.py --status" },
  "human": { "gui": "START.cmd  OR  python karmin_app.py" }
}
```

### B10 — handoff projection

Pełny opis: [B10_HANDOFF.md](B10_HANDOFF.md).

- **Hybrid since:** `active_work` może zawierać work spoza okna (`outside_window`); `key_facts` nadal tylko w oknie.
- **Warstwy:** `anchors` (stabilne), `chronicle` (log), `recommended_actions`, `suggested_mneme`.
- **close:** jeden work + jeden fact summary + zapis meta `last_project`.
- **Boot:** bez `--project` → `HOLON_DEFAULT_PROJECT` lub `*.meta.json`; `--compact` tnie tokeny.

### B2 — inverted lexical index

Przy `store >= lexical_index_min_store` (agent: 500) lub `lexical_index_force=True`:
recall scoringuje **kandydatów** z `holon_lexindex` (token → ids), nie cały store.
Moduł: `holon_lexindex.py`. Stats: `stats()["lex_index"]`.

### B4 — hooks + inbox

```python
am.on_remember(lambda item, kind, action, memory: ...)
```

Inbox JSONL (IDE / narzędzia zewnętrzne):

```bash
echo {"content":"[Holon] fact","kind":"fact"} >> remember_inbox.jsonl
python holon_agent_memory.py watch-remember --inbox remember_inbox.jsonl --once
```

### B6 — ablacja flat vs prism

```bash
python holon_agent_memory.py ablation
```

Raport JSON: `profiles.prism` / `profiles.flat` (use_prism, recall hits, ms).

### Krystalizacja (B9)

**Cel:** utrwalenie **stałych ścieżek** pamięci SE (nie inventowanie treści).

| Krok | Efekt |
|------|--------|
| Merge near-dup | cosine + lexical ≥ próg → jedna ścieżka, `cluster_size↑`, `created_at` = początek |
| Promote | epizod z `cluster_size ≥ min` → `fact` |
| Demote work | nadmiar work → fact (jak `set-work`) |
| Φ reinforce | `_update_phi` na top durable + floor relevance |

Profil `Config.agent()`: `crystallize_sim_threshold=0.88`, `crystallize_reinforce_top=32`.  
CLI domyślnie **zapisuje** po passie; `--dry-run` tylko raport.

## Handoff schema (v1)

```json
{
  "protocol": "holon-agent-handoff-v1",
  "profile": "agent",
  "project_filter": "Karmazyn",
  "mode": "full | delta",
  "stats": { "turns": 0, "store": 0, "delta_hours": 0.0, "facts": 0, "work": 0 },
  "wake": "…",
  "active_work": [ { "when": "…", "content": "…", "flags": {} } ],
  "key_facts": [ … ],
  "since": { "raw": "24h", "hours": 24, "cutoff": 0, "work_in_window": 0, "facts_in_window": 0 },
  "agent_protocol": [ "1. …", "2. …" ],
  "paths": { "memory": "…", "docs": "docs/" },
  "digest": "opcjonalnie pełny tekst lub DIGEST (DELTA)"
}
```

### B1 — delty (`--since`)

| Forma | Godziny |
|-------|---------|
| `24h` / `12` | 24 / 12 |
| `7d` | 168 |
| `90m` | 1.5 |
| `3600s` | 1 |

Filtr: `created_at >= now - since`. Bez starych factów/work poza oknem.  
Start dnia: pełny boot; **re-boot / mid-session**: `--since 24h`.

## Ewal

`holon_memory_eval.run_golden_eval()` — temp store, bez sieci:

- profile agent vs chat  
- fact/work po ~200d, ephemeral znika  
- recall  
- handoff protocol + B1 `--since` delta + B7 markdown  
- set_work demotion  
- crystallize (dry-run, merge/promote/demote, Φ)  
- LLM mock + local factory slot  

```bash
python holon_agent_memory.py eval
```

## Backend trwałości: Karmin_DB (nie SQLite)

Plan B3: **własny Karmin_DB** zamiast SQLite — patrz [KARMIN_BRIDGE.md](KARMIN_BRIDGE.md).

```bash
python holon_agent_memory.py karmin-slot
python holon_agent_memory.py karmin-sync
python holon_agent_memory.py karmin-export --snapshot se.holon-karmin.json
```

Primary runtime: nadal `holon_memory.json`. Karmin = mirror + backup + most do DB_karmin.

## Granice (świadome)

- Brak multi-writer / lock na JSON.  
- Skala: setki itemów OK; tysiące → plan indeksu (roadmap).  
- HRR/Φ nie są częścią cienkiego API — opcjonalny tor silnika.
