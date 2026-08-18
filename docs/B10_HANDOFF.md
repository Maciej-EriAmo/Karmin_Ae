# B10 — Handoff projection (v5.13+)

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
| **`anchors` / `chronicle`** | Kotwice vs świeższy log; w **compact** chronicle=0, anchors nie dublują key_facts. |
| **`key_facts`** | full → anchors; delta/hybrid → tylko nowe w oknie (kompat B1). |
| **`recent_done`** | Tylko `--rich`; w compact puste. |
| **`recommended_actions`** | Max 3, ASCII, priorytet: 1 work → crystallize → close. |
| **`suggested_mneme`** | RECALL/NEAR/FOCUS (compact: max 2). |
| **`set-work` max_active=1** | Jeden wątek; boot woła `enforce_max_work`. |
| **`close`** | Atomowo work + fact + save + `last_project`. |
| **last project** | `holon_memory.meta.json` + env; boot bez `--project` → last. |
| **compact (domyślnie ON)** | 1 work, ≤3 facts, 0 chronicle, content≤280, krótki protocol. |
| **`--rich`** | Pełniejszy handoff (wyłącza compact). |
| **remember merge** | `Config.remember_merge_sim` (agent 0.88). |

## CLI

```bash
# hybrid re-boot (compact ON domyslnie)
python agent_boot.py --since 24h --project Holon

# czysta delta B1
python agent_boot.py --since 24h --strict-delta --project Holon

# pipe JSON
python agent_boot.py --no-banner

# pelniejszy handoff
python agent_boot.py --rich --project Holon

# last project (po set-work/close)
python agent_boot.py
python agent_boot.py --all-projects

# domkniecie sesji
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
  "compact": true,
  "active_work": [{"content": "...", "outside_window": true}],
  "recent_done": [],
  "key_facts": [],
  "anchors": [],
  "chronicle": [],
  "recommended_actions": [
    "python holon_agent_memory.py set-work \"...\" --max-active 1 --project Holon"
  ],
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
| `handoff_max_work` | **1** |
| `handoff_max_facts` | **4** |
| `handoff_max_chronicle` | **2** |
| `handoff_hybrid_since` | True |
| `remember_merge_sim` | 0.88 |

Preset `se` = te limity; `se-compact` = facts 3 (jeszcze ciaśniej); `--rich` w boot = pełniejsza projekcja.

## Testy

`python holon_agent_memory.py eval` — m.in.:

- `handoff_hybrid_fills_stale_work`
- `handoff_strict_delta_no_stale_work`
- `handoff_has_recommended_actions` / `handoff_has_anchors`
- `close_ok` / `close_max_active_one` / `last_project_meta`
- `remember_idempotent_same_id`

## B13 — komory (enter / leave)

Jedna żywa komora na projekt. Wejście ładuje podstawy, wyjście zapisuje stan, obrót nie kasuje innych komór.

```bash
python holon_agent_memory.py enter --project Holon
# praca…
python holon_agent_memory.py leave --work-text "…" --fact-text "…" --project Holon
python holon_agent_memory.py enter --project lore-game
python holon_agent_memory.py chambers
```

- `enter P` — snapshot poprzedniej komory (`last_project`), restore work jeśli został zdemotowany, `last_project=P`, handoff jak boot.
- `leave` / `close` — atomowo work+fact **i** zapis komory w `holon_memory.meta.json` (`chambers`).
- `enforce_max_work` bez projektu: 1 work **na komorę**, nie 1 work na cały store.
- Handoff: `chamber` (work + ≤3 facts) + `chambers` (nazwy bębna).
- **Separacja:** `_match_project` = wyłącznie prefiks `[Tag]` na czele (alias tylko pisowni tagu, np. `sheet`→`Karmin_Sheet`). Słowo w ciele („Holon”, „eriamo”) **nie** wciąga faktu do obcej komory. `remember --project P` stawia `[P]`. Merge nie przechodzi między tagami. Higiena zlepków: `separate [--dry-run]`.

## Czego B10 **nie** robi

- Nie zmienia silnika HRR/Φ.
- Nie wdraża B3b (Karmin RPC).
- Nie auto-generuje factów z LLM.
- Nie kasuje store — tylko projekcja + demotion jak wcześniej.
