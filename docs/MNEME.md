# Mneme — mała baza SE pod Holon (meta-język pamięci)

**Status:** design + szkielet wykonywalny (`holon_mneme.py`)  
**Rola:** język i graf **dla modelu AI**, nie zastępnik Karmin_DB ani SQL.

---

## 1. Po co (i czemu nie KarminQL / SQL)

| Potrzeba AI | SQL / KarminQL | Mneme |
|-------------|----------------|-------|
| Krótki, trudny do zhalucynowania DSL | bogata składnia | ~12 form |
| Wynik = kotwice z **kiedy** | tabele | hit + `when` + kind |
| Eksploracja „wokół myśli” | JOIN ręczne | `NEAR` / `WALK` / `ALONG` |
| Ciągłość SE | osobny serwer | siedzi na Holon store |

**Karmin** zostaje skarbcem świata.  
**Mneme** jest **orężem myśli** na wierzchu Holona.

---

## 2. Co Holon już ma (graf „ukryty”)

Holon **nie** trzymał klasycznej listy krawędzi `A→B`, ale **eksplorowalną przestrzeń**:

```
        Φ² (identity attractors k=…)
              ▲
              │ score
   item ──────┼────── query  (+ lexical)
              │
        time_embed  →  ALONG (recall_at)
        HRR bind    →  holograficzne wiązanie wzorca
        Prism L0–L2 →  warstwy retencji
```

| Mechanizm dziś | Znaczenie w Mneme |
|----------------|-------------------|
| hybrid recall (cosine + lex + fact/work) | `RECALL` |
| Φ attractor w `_recall` | `FOCUS` / część rankingu |
| `recall_at` + time_embed | `ALONG` |
| `cluster_size`, semantic merge | przyszłe `MERGE` |
| prefiks `[Projekt]` | `PROJECT` |
| pastness / `created_at` | każde `HIT.when` |

**Luka:** brak **jawnego grafu znaczeń** (A *about* B, A *follows* B, A *in* Project).  
Model dobrze chodzi po podobieństwie, źle po „co wynika z czego” bez krawędzi.

Mneme dodaje **cienki graf jawny** obok przestrzeni wektorowej — dwa tryby eksploracji:

1. **Ciągły** — `NEAR` / `RECALL` / `ALONG` (Holon jak dziś)  
2. **Dyskretny** — `WALK` / `LINK` / `TRACE` (nowe krawędzie)

---

## 3. Model danych (mała baza)

```
┌─────────────────────────────────────────┐
│  MnemeStore                             │
│                                         │
│  nodes[]  = Holon Item (bez kopii)      │
│             + opcjonalnie project tag   │
│                                         │
│  edges[]  = { id, src, dst, rel,        │
│               w, created_at }           │
│                                         │
│  focus    = opcjonalny kontekst sesji   │
│             (project | query emb)       │
│                                         │
│  primary persistence:                   │
│    holon_memory.json  → nodes (jak dziś)│
│    holon_links.json   → edges (Mneme)   │
└─────────────────────────────────────────┘
```

### Węzeł (node)

To **ten sam** `Item` Holona:

| Pole | Rola |
|------|------|
| `id` | stabilny UUID |
| `content` | treść |
| `kind` | fact \| work \| insight \| reminder \| episode |
| `created_at` | kalendarz (pastness) |
| `project` | wyciąg z `[Tag]` lub prop |
| `embedding` | NEAR / RECALL |

### Krawędź (edge)

| Pole | Opis |
|------|------|
| `src`, `dst` | id węzłów |
| `rel` | typ relacji (słownik zamknięty + custom) |
| `w` | waga 0..1 (domyślnie 1) |
| `created_at` | kiedy powiązano |

**Słownik `rel` (kanon SE):**

| rel | Znaczenie dla AI |
|-----|------------------|
| `in` | należy do projektu / wątku |
| `about` | dotyczy tematu / faktu |
| `follows` | następstwo pracy (work→work) |
| `supports` | fakt wspiera inny |
| `conflicts` | sprzeczność (do ręcznego review) |
| `see` | luźne „zobacz też” |

Zamknięty zestaw = model nie wymyśla `JOIN INNER LEFT`.

---

## 4. Meta-język (Mneme-L)

### 4.1 Zasady ducha maszyny

1. **Jedna linia = jedna intencja.**  
2. **Wynik zawsze strukturalny:** lista `HIT` lub `OK` / `ERR`.  
3. **Każdy HIT ma `when`** — zero wiecznego teraz.  
4. **Brak DELETE trwałego fact** w DSL bez `PURGE` (osobna, świadoma forma).  
5. **Wielkość odpowiedzi domyślna mała** (`TOP 5`) — pod budżet tokenów.

### 4.2 Formy

```text
# zapis
HOLD fact "treść…" [PROJECT Name]
HOLD work "treść…" [PROJECT Name]
HOLD note "epizod…" 

# graf jawny
LINK <id|QUOTE> -rel-> <id|QUOTE>
UNLINK <id> -rel-> <id>
TRACE <id|QUOTE> [DEPTH 1..3]

# eksploracja ciągła (Holon-native)
RECALL "fraza" [TOP n] [PROJECT P] [KIND fact|work|any] [SINCE 7d|24h]
NEAR "fraza"|<id> [TOP n]
ALONG "fraza" AGO 3d|AT <unix> [TOP n]
FOCUS PROJECT Name | FOCUS "fraza" | FOCUS CLEAR

# sesja / widok
DIGEST [PROJECT P]
WALK "start"|<id> VIA rel[,rel] DEPTH d [TOP n]

# utrzymanie
SOFTDROP work "stary wątek"     # work → fact (jak set-work demotion)
# PURGE id                     # tylko jawne, nie w domyślnym prompcie modelu
```

### 4.3 Semantyka skrócona

| Forma | Backend |
|-------|---------|
| `HOLD` | `AgentMemory.remember` + opcjonalnie auto-`LINK … -in-> project_hub` |
| `RECALL` | hybrid recall + filtry project/kind/since |
| `NEAR` | top-k cosine w store (sąsiedztwo wektorowe = stary „graf” Holona) |
| `ALONG` | `HoloMem.recall_at` |
| `WALK` | BFS po `edges` (+ opcjonalnie soft `in` z project) |
| `TRACE` | węzeł + 1-hop edges + skrót content |
| `FOCUS` | filtr sesji + lekki bias rankingu |
| `DIGEST` | `AgentMemory.digest(project=)` |
| `LINK` | zapis do `holon_links.json` |

### 4.4 Wynik (kontrakt dla modelu)

```json
{
  "ok": true,
  "op": "RECALL",
  "hits": [
    {
      "id": "…",
      "kind": "fact",
      "when": "3 d temu",
      "score": 0.82,
      "project": "Karmazyn",
      "content": "…",
      "via": null
    }
  ],
  "graph": { "nodes": 12, "edges": 4 },
  "focus": "Karmazyn"
}
```

Model w prompcie dostaje **to**, nie surowy SQL.

---

## 5. Eksploracja: dwa grafy, jeden język

```
                 RECALL / NEAR
                      │
              ┌───────┴───────┐
              ▼               ▼
     przestrzeń Φ/emb     jawne edges
     (ciągła, stara        (WALK/TRACE,
      holonowa)             nowe)
              │               │
              └───────┬───────┘
                      ▼
                   HIT + when
```

**Przykład sesji AI:**

```text
FOCUS PROJECT Karmazyn
RECALL "slab freelist" TOP 5
TRACE <id_z_hita>
WALK <id> VIA about,follows DEPTH 2
ALONG "kentry" AGO 2d
HOLD work "[Karmazyn] next: QEMU SF.2" PROJECT Karmazyn
LINK <new> -follows-> <prev_work_id>
DIGEST PROJECT Karmazyn
```

To jest **ścieżka eksploracji pamięci**, nie raport SQL.

---

## 6. Auto-graf (żeby nie linkować ręcznie wszystkiego)

Przy `HOLD` z `PROJECT P`:

1. Istnieje/utwórz hub-node fact: `[P] · project hub` (jednorazowo).  
2. `LINK new -in-> hub`.  
3. Jeśli `HOLD work` i jest poprzedni work w P → opcjonalnie `LINK new -follows-> prev` (konfigurowalne).

Przy wysokim similarity (`remember` merge) — **nie** twórz drugiego węzła; krawędzie przełącz na ocalały id.

---

## 7. Persystencja

| Artefakt | Plik | Git |
|----------|------|-----|
| nodes | `holon_memory.json` | ignore |
| edges | `holon_links.json` | ignore |
| snapshot edges+ids | opcjonalnie w `*.holon-karmin.json` później | ignore |

Format `holon_links.json`:

```json
{
  "format": "holon-mneme-links-v1",
  "edges": [
    {"id": "e1", "src": "…", "dst": "…", "rel": "in", "w": 1.0, "created_at": 0.0}
  ]
}
```

---

## 8. Warstwy względem reszty stacku

```
LLM / Grok
    │  Mneme-L (meta-język)
    ▼
MnemeStore  ──► AgentMemory / MemoryAPI  ──► holon_memory.json
    │                    │
    │ edges              │ Φ, HRR, vacuum
    ▼                    ▼
holon_links.json    HoloMem (bez zmian prawa)
    │
    └── opcjonalnie mirror durable → Karmin_DB (B3)
```

---

## 9. Czego Mneme **nie** robi

- JOIN-ów relacyjnych, widoków SQL, CSV ETL → **Karmin**  
- Sieci HSS / światów → **Cynober**  
- Zastępowania Φ → Φ zostaje w HoloMem  
- „Drugiego Holona” z pełnym GC → vacuum zostaje

---

## 10. Implementacja (fazy)

| Faza | Zakres |
|------|--------|
| **M0** | Design (ten doc) |
| **M1** | Parser + `HOLD/RECALL/DIGEST/FOCUS` na AgentMemory |
| **M2** | `holon_links.json` + `LINK/TRACE/WALK` |
| **M3** | `NEAR` + `ALONG` (HoloMem) |
| **M4** | Auto-hub project + follows |
| **M5** | Prompt block: „wolno tylko Mneme-L” w agent workflow |

Szkielet M1–M3: moduł `holon_mneme.py`, CLI `python -m holon_mneme`.

---

## 11. Prompt dla modelu (kontrakt)

```text
Pamięć SE: używaj wyłącznie Mneme-L (HOLD, RECALL, NEAR, ALONG, WALK, TRACE,
LINK, DIGEST, FOCUS, SOFTDROP). Nie wymyślaj SQL/KarminQL.
Każdy HIT ma pole when — traktuj jako przeszłość.
Przed domknięciem sesji: HOLD fact/work dla trwałych ustaleń.
```

---

## 12. Nazwa

**Mneme** — w mitologii: pamięć; tu: *Queryable SE Memory* na Holonie.  
Meta-język: **Mneme-L**.

---

*Design 2026-07-31 — spójny z MemoryAPI, pastness, Karmin mirror (osobna warstwa).*
