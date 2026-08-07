# Konfigurator Karmin_Ae + Control Center

**Cel:** setup i codzienna praca z pamięcią SE.  
**Nie** mylić z `holon_memory.json` (stan umysłu).

Pełna instrukcja człowieka: **[USER_GUIDE.md](USER_GUIDE.md)**.

---

## Norma UX

| Rola | Start | Po co |
|------|--------|--------|
| **Człowiek** | `START.cmd` → `karmin_app.py` | Control Center (norma) |
| **Agent** | `python agent_boot.py` | handoff JSON · [AGENTS.md](../AGENTS.md) |
| **Power-user** | CLI | configure, memory, Mneme, eval |

```
człowiek ──► START.cmd / karmin_app.py
agent    ──► agent_boot.py  (+ surfaces w JSON)
power    ──► holon_configure / holon_agent_memory / holon_mneme
```

---

## Control Center (`karmin_app.py`)

```bat
START.cmd
python karmin_app.py
python karmin_app.py --lang en
python karmin_app.py --status
python karmin_app.py --status --project Holon
```

| Zakładka | Funkcje |
|----------|---------|
| Start | status store, work, facts, doctor, surfaces |
| Sesja SE | handoff JSON, filtr projektu / since, zapis `handoff.md`, podgląd boot |
| Pamięć | remember fact, set-work, close, crystallize |
| Ustawienia | preset, default_project, ui_lang; link do configure GUI |
| Konsola | log poleceń |
| Pomoc | skrót torów |

**Linia poleceń** na dole okna: `help` · `fact …` · `work …` · `boot` · `status` · …  
Jednorazowo: `python karmin_app.py -c "status Holon"`.

Entry point setuptools: `karmin-ae` → `karmin_app:main`.

Alias status (JSON):

```bat
python holon_agent_memory.py status [--project P]
```

---

## Pliki

| Plik | Rola |
|------|------|
| `START.cmd` | dwuklik → Control Center |
| `karmin_app.py` | panel człowieka + `--status` |
| `holon_settings.json` | preferencje lokalne (**gitignore**) |
| `holon_settings.example.json` | szablon w repo |
| `holon_settings.py` | load/save, presetty, `load_config`, doctor, `ui_lang` |
| `holon_configure.py` | CLI + małe GUI configure + `help` |

---

## Konfigurator CLI (`holon_configure.py`)

### Instrukcja w programie

```bat
python holon_configure.py help
python holon_configure.py --lang en help
python holon_configure.py          # bez komendy = help
```

### Komendy

```bat
python holon_configure.py show
python holon_configure.py presets
python holon_configure.py use se-compact
python holon_configure.py set default_project Karmazyn
python holon_configure.py set ui_lang en
python holon_configure.py lang en
python holon_configure.py set-override handoff_max_facts 4
python holon_configure.py set-override handoff_max_facts --clear
python holon_configure.py wizard
python holon_configure.py doctor
python holon_configure.py doctor --json
python holon_configure.py export-env
python holon_configure.py export-env --out holon.env
python holon_configure.py keys
python holon_configure.py gui
```

---

## Język (PL / EN)

| Priorytet | Źródło |
|-----------|--------|
| 1 | `--lang pl\|en` |
| 2 | env `HOLON_UI_LANG` (alias `HOLON_LANG`) |
| 3 | `ui_lang` w `holon_settings.json` |
| 4 | domyślnie **pl** |

- Control Center: combobox w **Ustawieniach** (+ Zapisz).  
- Configure GUI: combobox Language.  
- `export-env` dopisuje `HOLON_UI_LANG=…`.

---

## Presety

| Id | Profil | Po co |
|----|--------|--------|
| `se` | agent | domyślna ciągłość Grok/CLI |
| `se-compact` | agent | mniej tokenów w handoff |
| `se-long` | agent | większy store / long-horizon |
| `chat` | chat | EriAmo rozmowa |
| `lab-flat` | flat | ablacja bez Prism |

---

## Łańcuch Config

```
Config.agent()|chat()|flat()
  → holon_settings.json overrides
  → env HOLON_* (wygrywa LLM / CI)
```

`AgentMemory.open` i `agent_boot` wczytują settings automatycznie.

**default_project:** `HOLON_DEFAULT_PROJECT` → `*.meta.json` last → settings `default_project`.

---

## Doctor (positioning)

```bat
python holon_configure.py doctor
```

Sprawdza gotowość SE i wypisuje macierz vs typowa chmurowa agent-memory:

local-first · durable fact/work · handoff · hybrid since · crystallize · Mneme · golden eval · agent_boot  

W Control Center: przycisk **Doctor** na zakładce Start.

---

## Configure-only GUI

```bat
python holon_configure.py gui
```

Węższe okienko (presety / LLM / doctor) — bez pełnego panelu Pamięć/Sesja.  
Pełna codzienna praca: **`karmin_app.py`**.

---

## Surfaces w handoff

Po `python agent_boot.py --no-banner` JSON zawiera m.in.:

```json
"surfaces": {
  "agent": { "boot": "…", "status_json": "python karmin_app.py --status", … },
  "human": { "gui": "START.cmd  OR  python karmin_app.py", … }
}
```

Agent ma używać `surfaces.agent`; człowiek — `surfaces.human`.
