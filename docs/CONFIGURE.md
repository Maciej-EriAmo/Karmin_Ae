# Konfigurator Karmin_Ae

**Cel:** 30-sekundowy setup lokalnej pamięci SE — profile, handoff, LLM, doctor.  
**Nie** mylić z `holon_memory.json` (stan umysłu).

## Pliki

| Plik | Rola |
|------|------|
| `holon_settings.json` | lokalne preferencje (**gitignore**; może mieć API key) |
| `holon_settings.example.json` | szablon w repo |
| `holon_settings.py` | load/save, presetty, `load_config`, doctor |
| `holon_configure.py` | CLI + GUI (tkinter) |

## CLI

```bat
python holon_configure.py show
python holon_configure.py presets
python holon_configure.py use se-compact
python holon_configure.py set default_project Karmazyn
python holon_configure.py set-override handoff_max_facts 4
python holon_configure.py wizard
python holon_configure.py doctor
python holon_configure.py export-env
python holon_configure.py gui
```

## Presety

| Id | Profil | Po co |
|----|--------|--------|
| `se` | agent | domyślna ciągłość Grok/CLI |
| `se-compact` | agent | mniej tokenów w handoff |
| `se-long` | agent | większy store / long-horizon |
| `chat` | chat | EriAmo rozmowa |
| `lab-flat` | flat | ablacja bez Prism |

## Łańcuch Config

```
Config.agent()|chat()|flat()
  → holon_settings.json overrides
  → env HOLON_* (wygrywa LLM / CI)
```

`AgentMemory.open` i `agent_boot` wczytują settings automatycznie.

**default_project:** `HOLON_DEFAULT_PROJECT` → `*.meta.json` last → settings.

## Doctor (positioning)

`python holon_configure.py doctor` sprawdza gotowość SE i wypisuje macierz:

lokalność · durable fact/work · handoff · hybrid since · crystallize · Mneme · golden eval · agent_boot  

— cechy, których typowa chmurowa „agent memory” zwykle nie daje w pakiecie.

## GUI

```bat
python holon_configure.py gui
```

Stdlib **tkinter** — bez dodatkowych pipów. Zapisz / Doctor / podpowiedź boot.
