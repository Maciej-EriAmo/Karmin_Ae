# B10 — Handoff projection (v5.13)

**Cel:** ostrzejsza **projekcja** tego, co już jest w `holon_memory.json` — mniej szumu w bootcie, bez nowej bazy i bez zmyślania treści.

## Problem (z użycia SE)

1. `active_work` trzymało stos snapshotów „next optional…”.
2. `key_facts` = log sesji (nakładające się changelogi), nie kotwice.
3. `--since 24h` dawał pusty work przy starym, wciąż ważnym wątku (fałszywa amnezja).
4. Koniec sesji wymagał ręcznego `set-work` + `remember` (łatwo o lukę).
5. Boot głośny tokenowo; brak podpowiedzi Mneme / akcji z Φ/work count.

## Deliverable

| Element | Zachowanie |
|---------|------------|
| **Hybrid `--since`** | Facts nadal tylko w oknie. `active_work` dopełnia last work **spoza** okna (`outside_window: true`). `mode=hybrid` gdy dopełniono. |
| **`--strict-delta`** | Wyłącza hybrid (czyste B1). |
| **`anchors` / `chronicle`** | Kotwice (relevance×cluster×długość, dedupe) vs świeższy log. |
| **`key_facts`** | full → anchors; delta/hybrid → tylko nowe w oknie (kompat B1). |
| **`recent_done`** | Inne aktywne work poza top projection (max 2). |
| **`recommended_actions`** | np. crystallize gdy work>1, close na koniec, full boot po Δ≥48h. |
| **`suggested_mneme`** | `RECALL` / `NEAR` / `FOCUS` z active work. |
| **`set-work` max_active=1** | Domyślnie jeden wątek na projekt (Config). |
| **`close`** | Atomowo work + fact + save + `last_project`. |
| **last project** | `holon_memory.meta.json` + env `HOLON_DEFAULT_PROJECT`; boot bez `--project` podstawia last. |
| **`--compact`** | Mniej tokenów: krótkie limity, krótki protocol, bez listy commands w bannerze. |
| **remember merge** | Próg z `Config.remember_merge_sim` (agent 0.88); exact/prefix bez zmian. |

## CLI

```bash
# hybrid re-boot (domyślnie)
python agent_boot.py --since 24h --project Holon

# czysta delta B1
python agent_boot.py --since 24h --strict-delta --project Holon

# mało tokenów
python agent_boot.py --compact --no-banner

# last project (po set-work/close)
python agent_boot.py
python agent_boot.py --all-projects   # wymuś brak filtra

# domknięcie sesji
python holon_agent_memory.py close \
  --work-text "next: type-unify" \
  --fact-text "kcc 0.3 TB.2e saved; gate verify_kcc OK" \
  --project Karmazyn
```

## JSON (pola B10)

```json
{
  "protocol": "holon-agent-handoff-v1",
  "mode": "full | delta | hybrid",
  "active_work": [{"content": "…", "outside_window": true}],
  "recent_done": [],
  "key_facts": [],
  "anchors": [],
  "chronicle": [],
  "recommended_actions": ["crystallize --project Holon  # work=3>1"],
  "suggested_mneme": ["RECALL \"kcc 0.3\" TOP 5"],
  "since": {
    "hours": 24.0,
    "hybrid": true,
    "hybrid_filled": true,
    "work_in_window": 0,
    "facts_in_window": 0
  }
}
```

## Config (`Config.agent`)

| Pole | Domyślnie |
|------|-----------|
| `set_work_max_active` | 1 |
| `crystallize_max_active_work` | 1 |
| `handoff_max_work` | 2 |
| `handoff_max_facts` | 6 |
| `handoff_max_chronicle` | 4 |
| `handoff_hybrid_since` | True |
| `remember_merge_sim` | 0.88 |

## Testy

`python holon_agent_memory.py eval` — m.in.:

- `handoff_hybrid_fills_stale_work`
- `handoff_strict_delta_no_stale_work`
- `handoff_has_recommended_actions` / `handoff_has_anchors`
- `close_ok` / `close_max_active_one` / `last_project_meta`
- `remember_idempotent_same_id`

## Czego B10 **nie** robi

- Nie zmienia silnika HRR/Φ.
- Nie wdraża B3b (Karmin RPC).
- Nie auto-generuje factów z LLM.
- Nie kasuje store — tylko projekcja + demotion jak wcześniej.
