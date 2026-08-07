# Proto-emocje (AII) — kod i grupa docelowa

**Warstwa:** tło poznawcze Holona, nie główna treść handoffu SE.  
**Pliki:** `holon_aii.py` (`AIIState`, `TimeDecay`) · `holon_prompts.py` (`format_internal_state`) · `holon_holomem.py` (update / inject / wagi).

---

## 1. Po co to jest (nie marketing)

Karmin_Ae / Holon trzyma nie tylko **fakty i work**, ale też **lekki stan układu**:

| Co | Rola |
|----|------|
| **fact / work / handoff** | jawna treść SE — *co* robimy |
| **AII (proto-emocje)** | cichy reżim — *w jakim trybie* brzmieć i ważyć uwagę |

**Proto-** znaczy: to nie teatr emocji w UI i nie „agent udaje, że czuje”.  
To **sygnały tła** (często „nieuświadomione” w sensie: nie są tematem rozmowy), które:

- regulują **ton** (spokój vs lekkie zabarwienie),
- wzmacniają **focus**, gdy rozmowa idzie w kod/debug,
- wygaszają fałszywy **alarm** po długiej przerwie (healthy temporal).

Efekt dla użytkownika: **milej i płynniej się rozmawia i pracuje** — lekki boost komunikacji, bez nachalnego afektu.

---

## 2. Grupa docelowa

| Kto | Jak AII mu służy |
|-----|------------------|
| **Partner SE / operator** (Ty) | Spójniejszy klimat z agentem; focus przy kodzie; mniej „zimnego API”, mniej dramatu po przerwie. |
| **Agent (Grok / CLI)** | W torze boot dominują fact/work; AII jest w tle silnika i w `stats`. Pełny inject stanu — w **sesji chat** (EriAmo). |
| **Chat / brainstorm** (`main*.py`, `START_CHAT`) | Główny odbiorca bloku STAN WEWNĘTRZNY w prompcie — ton i focus bez recytowania emocji. |
| **Nie dla** | Dashboardu „emocja dnia”, social chatbota, scoreboardu afektu dla marketingu. |

**KANON:**  
- Treść SE → boot / panel / fact-work.  
- Klimat i focus → AII w tle (+ chat inject).  
Nie mylić z Mem0-style „extract fact from message” — to **inna warstwa**.

---

## 3. Model w kodzie (`AIIState`)

### 3.1 Pola stanu

```text
emotion        — etykieta: neutral | radosc | zaskoczenie | strach | zlosc | smutek
vacuum_signal  — float, wygładzone napięcie (ujemne ≈ błąd/niepokój, dodatnie ≈ zgodność)
focus_active   — bool: tryb skupienia na zadaniu (kod/debug/…), osobno od emotion
```

Persistowane w `holon_memory.json` jako `aii: { emotion, vacuum_signal, focus }`  
(wraz ze `stats()` / `to_dict()`).

### 3.2 Aktualizacja (`AIIState.update`)

1. Wejście: tekst tury (+ opcjonalnie embedding).  
2. **Focus:** podobieństwo do ref „implementacja kod architektura debug…” **lub** słowa kluczowe (`debug`, `kod`, `refaktor`, …) → `focus_active`.  
3. **Emotion:** najlepsze dopasowanie do pozostałych ref/keywords (bez etykiety `focus` jako emocji).  
4. **Vacuum:** EMA  
   `vacuum = 0.7 * vacuum + 0.3 * VACUUM_SIGNALS[emotion]`  
   (np. strach/złość → ujemne, radość → dodatnie, neutral → 0).

### 3.3 Healthy baseline (`relax_toward_baseline`)

Po dłuższej nieobecności (`delta_hours`, half-life domyślnie ~72 h z `Config.aii_baseline_half_life_h`):

- vacuum **zanika** (habituation — nie trzyma alarmu w nieskończoność),
- przy długiej ciszy emotion → `neutral`, focus → off.

To spina się z pastness / wake (oś czasu) — **zdrowy umysł**, nie wieczny panic mode.

### 3.4 Wpływ na silnik (`HoloMem`)

| Mechanizm | Gdzie |
|-----------|--------|
| Waga emocji przy zapisie / relevance | `get_emotion_weight()` |
| Adaptacja progu recall | `get_threshold_multiplier(aii_adapt_range)` |
| Boost przy focus | silniejsza waga gdy `focus_active` |
| Preferencja work vs epizod | focus sprzyja trzymaniu wątku zadaniowego |
| Inject do LLM | `format_internal_state(aii)` w ścieżce chat |

### 3.5 Prompt (`format_internal_state`)

Blok **nie do recytacji**:

- dominująca emocja (PL etykieta),
- vacuum,
- focus AKTYWNY / BRAK,
- hint tonu: przy neutral + |vacuum|≈0 → **spokój, zero teatralnego afektu**.

CORE_SYSTEM: partner w pracy, bez disclaimerów „jestem tylko modelem”; barwa **w tle**, treść merytoryczna pierwsza.

---

## 4. Dwa tory produktu a AII

| Tor | AII widoczność |
|-----|----------------|
| **Agent SE** (`agent_boot`, compact handoff) | Głównie w `stats.aii` / pliku; handoff stawia na work/facts/actions (krótki bootstrap). |
| **Chat EriAmo** | Pełny STAN WEWNĘTRZNY w kontekście LLM co turę. |
| **Panel** (`START.cmd`) | Operator zarządza treść SE; AII nie wymaga ręcznej edycji. |

Świadomie: **emocje działają w tle**.  
Operator nie „ustawia smutku suwakiem” — system aktualizuje stan z rozmowy i czasu.

---

## 5. Focus = łatwiej w skupieniu

Gdy układ łapie **focus** (kod, debug, implementacja):

- wagi i preferencje idą w stronę zadania, nie dygresji,
- w torze SE to naturalnie współgra z **1 aktywnym work** i **compact handoff**,
- w torze chat — ton „przy robocie”, bez rozpraszania na meta-emocje.

To jest ten „lekki boost”: nie głośniejszy agent, tylko **łatwiej nie rozjechać sesji**.

---

## 6. Czego AII **nie** robi

- Nie zastępuje fact/work/handoff.  
- Nie jest API emocji dla third-party.  
- Nie generuje treści „z uczucia” zamiast z pamięci.  
- Nie trzyma strachu po 3 dniach ciszy bez bodźca (baseline).  
- Nie jest HSS/security (to `archiwum/`).

---

## 7. Szybki odczyt stanu (advanced)

```bat
python -c "import json; d=json.load(open('holon_memory.json',encoding='utf-8')); print(d.get('aii'))"
python holon_agent_memory.py stats
```

W `stats` / payload pamięci szukaj klucza `aii`.

Eval: m.in. `aii_baseline_after_gap` w golden (`holon_agent_memory.py eval`).

---

## 8. Powiązane docs

| Doc | Temat |
|------|--------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | warstwy, healthy temporal |
| [USER_GUIDE.md](USER_GUIDE.md) | instrukcja człowieka (AII w skrócie) |
| [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md) | agent: treść SE pierwsza; AII tło |
| [B10_HANDOFF.md](B10_HANDOFF.md) | projekcja work/facts (osobno od AII) |
