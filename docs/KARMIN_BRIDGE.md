# Holon × Karmin_DB (zamiast SQLite)

## Decyzja planistyczna

W roadmapie **B3** było: *„opcjonalny SQLite backend za MemoryAPI”*.

**Odrzucamy SQLite.** Zastępujemy własnym **Karmin_DB / Cynober** (`DBase`, `cynober-db`):

| | SQLite (stary plan) | Karmin_DB (kanon) |
|--|---------------------|-------------------|
| Właściciel | obcy silnik | Twój stack |
| Prawo GC | brak T×reach | ten sam Karmazyn Store |
| Zapytania | SQL | KarminQL |
| Spójność z lore / grą / światami | zero | jeden DB_karmin |
| Sieć / HSS | osobno | Cynober-Secure (gdy RPC) |

## Architektura mostu

```
MemoryAPI / AgentMemory          primary: holon_memory.json + Φ
        │
        │  karmin-sync / export / import
        ▼
KarminMirror (holon_backend_karmin.py)
        │
        ▼
KarminEngine + kernel.Store      (DBase / pip cynober-db)
        │
        ▼
snapshot JSON  holon-karmin-snapshot-v1   ← rola „backup / multi-session”
```

- **Primary SE runtime** zostaje Holon JSON (handoff, pastness, AII).  
- **Karmin** = durable mirror + backup + przyszła wspólna baza z lore/GameStore.  
- **Nie** mieszamy HSS w MemoryAPI.

## Mapowanie

| Holon Item | Karmin |
|------------|--------|
| `id` | bubble `h_<hex>` + prop `holon_id` |
| `content` | prop `content` |
| fact/work/… | prop `kind` + `is_fact` / `is_work` |
| `created_at` | prop `created_at` (kalendarz) |
| embedding | `emb_head` (pierwsze 64 wymiary JSON) |

## CLI

```bash
# diagnostyka
python holon_agent_memory.py karmin-slot

# mirror fact/work do silnika in-process
python holon_agent_memory.py karmin-sync

# backup (zastępuje „zrzut SQLite”)
python holon_agent_memory.py karmin-export --snapshot backup.holon-karmin.json

# przywróć / scal do Holona
python holon_agent_memory.py karmin-import --snapshot backup.holon-karmin.json
```

Env:

```text
HOLON_KARMIN_PATH=C:\Users\drwis\DBase
# lub: pip install cynober-db  + importowalny cynober_query_engine
```

## Kod

```python
from holon_backend_karmin import KarminMirror, karmin_available

if karmin_available():
    m = KarminMirror.open()
    m.sync_items(am.hm.store)
    m.export_snapshot("se.holon-karmin.json")
```

## Świadome granice (MVP)

1. In-process Engine — bez wymogu `cynober-server` (RPC światy = faza później).  
2. Snapshot = JSON w formacie Karmin-rows, nie surowy multi-GB KAFD media.  
3. Φ / AII nie jadą do Karmina w MVP — tylko itemy SE.  
4. Import **scala** `remember()` (dedupe), nie kasuje lokalnego store.

## Test

```bash
python -m unittest tests.test_karmin_bridge -q
# skip jeśli brak DBase na HOLON_KARMIN_PATH
```
