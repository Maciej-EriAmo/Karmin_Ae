# Memory API — kontrakt zaawansowany

## Powierzchnia

```python
from holon_memory_api import open_memory, MemoryAPI

mem: MemoryAPI = open_memory("holon_memory.json", profile="agent")
```

| Metoda | Semantyka |
|--------|-----------|
| `remember(content, kind)` | `fact` \| `work` \| `note`; semantic merge / exact dedupe |
| `recall(query, top_k)` | cosine + lexical boost + bonus flag |
| `digest(..., project="")` | tekst SE z pastness + osią czasu |
| `handoff(..., project="")` | JSON bootstrap (`holon-agent-handoff-v1`) |
| `set_work(content, project, max_active)` | work + demotion starych work→fact |
| `save()` | JSON + KuRz dict |
| `stats()` | turns, store, facts, work, profile, … |

Implementacja referencyjna: `AgentMemory` (`holon_agent_memory.py`).

## Trwałość

| Typ | `store_decay` | Ranking age |
|-----|---------------|-------------|
| fact / work / insight / reminder | **nie wygasa** (`keep_*_forever`) | `durable_age_cap` (miękki, nie kasuje `created_at`) |
| epizod / note | `store_decay_hours` (agent ≈ 90d, chat ≈ 14d) | full age |

**Zasada:** `created_at` jest kalendarzem; `age` to waga rankingu.

## Profile (`holon_config.Config`)

| Fabryka | store_decay | prune max | prism | Użycie |
|---------|-------------|-----------|-------|--------|
| `Config.chat()` | 336 h | 120 | on | `Session`, `main.py` |
| `Config.agent()` | 2160 h | 400 | on | AgentMemory |
| `Config.flat()` | jak agent | … | **off** | ablacja / lab |
| `Config.from_env()` | `HOLON_PROFILE` | | | env override |

## CLI

```bash
python holon_agent_memory.py handoff [--project P] [--no-digest]
python holon_agent_memory.py digest [--project P]
python holon_agent_memory.py remember "…" --fact|--work
python holon_agent_memory.py set-work "…" --project P [--max-active 3]
python holon_agent_memory.py recall "…" [--project P]
python holon_agent_memory.py seed | stats | eval | collab-test | llm-slot
```

## Handoff schema (v1)

```json
{
  "protocol": "holon-agent-handoff-v1",
  "profile": "agent",
  "project_filter": "Karmazyn",
  "stats": { "turns": 0, "store": 0, "delta_hours": 0.0, "facts": 0, "work": 0 },
  "wake": "…",
  "active_work": [ { "when": "…", "content": "…", "flags": {} } ],
  "key_facts": [ … ],
  "agent_protocol": [ "1. …", "2. …" ],
  "paths": { "memory": "…", "docs": "docs/" },
  "digest": "opcjonalnie pełny tekst"
}
```

## Ewal

`holon_memory_eval.run_golden_eval()` — temp store, bez sieci:

- profile agent vs chat  
- fact/work po ~200d, ephemeral znika  
- recall  
- handoff protocol  
- set_work demotion  
- LLM mock + local factory slot  

```bash
python holon_agent_memory.py eval
```

## Granice (świadome)

- Brak multi-writer / lock na JSON.  
- Skala: setki itemów OK; tysiące → plan indeksu (roadmap).  
- HRR/Φ nie są częścią cienkiego API — opcjonalny tor silnika.
