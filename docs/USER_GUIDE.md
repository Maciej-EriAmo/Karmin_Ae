# Karmin_Ae — instrukcja obsługi (człowiek)

**Dla kogo:** Ty przy biurku (nie agent).  
**Norma:** panel graficzny, nie terminal.  
**Agent (Grok):** osobny tor — [AGENTS.md](../AGENTS.md) · [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md).

---

## 1. Co to jest (30 sekund)

**Karmin_Ae** = lokalna pamięć partnera SE (coding agent):

- **fact** — trwałe ustalenia (nie wygasają z „decay godzin”),
- **work** — aktywny wątek (domyślnie 1),
- **handoff** — JSON/MD z kontekstem na start sesji agenta,
- **bez chmury** — pliki u Ciebie; nie Mem0/SaaS.

| Plik | Znaczenie |
|------|-----------|
| `holon_memory.json` | **stan umysłu** (fakty, work) — nie commituj |
| `holon_settings.json` | **preferencje** (profil, projekt, język, LLM) — nie commituj |
| `AGENTS.md` | kontrakt **dla agenta** |

---

## 2. Pierwszy start

```bat
cd C:\Users\drwis\Karmin_Ae
pip install -r requirements.txt
START.cmd
```

Albo: `python karmin_app.py`

Jeśli brak okienka (tkinter):  
`python holon_configure.py wizard` (terminal) → potem agent: `python agent_boot.py`.

---

## 3. Control Center (`karmin_app.py`)

| Zakładka | Co robisz |
|----------|-----------|
| **Start** | Stan store, aktywny work, top facts, doctor score, podpowiedzi. **Odśwież** / **Doctor** / **Pokaż boot (agent)**. |
| **Sesja SE** | Podgląd **handoff** (to samo, co agent po bootcie). Projekt, `--since` (np. 24h). **Załaduj handoff** / **Zapisz handoff.md**. |
| **Pamięć** | Bez CLI: **fact**, **work**, **close** (summary + next work), **krystalizuj**. |
| **Ustawienia** | Preset (`se` / `se-compact` / …), domyślny projekt, język PL/EN. **Zapisz**. Zaawansowane: „CLI configure…”. |
| **Pomoc** | Skrót torów człowiek vs agent. |

### Typowy dzień (człowiek)

1. `START.cmd`  
2. Zakładka **Start** → czy work/fakty mają sens  
3. Po pracy w agentcie (lub ręcznie): **Pamięć** → close / fact  
4. Gdy store „szumi”: **Krystalizuj**  
5. Od czasu do czasu: **Doctor**

### Czego nie robić w GUI zamiast agenta

- Agent **sam** ma odpalić `python agent_boot.py` na start sesji Grok.  
- Ty **nie musisz** wklejać handoff ręcznie agentowi, jeśli pracuje w tym repo z AGENTS.md.

---

## 4. Dwa tory (nie mylić)

```
  CZŁOWIEK                         AGENT SE
  ────────                         ────────
  START.cmd                        python agent_boot.py
  karmin_app.py                    holon_agent_memory remember/set-work/close
  holon_configure.py gui           Mneme / crystallize / eval
```

Handoff JSON zawiera pole **`surfaces`**:

- `surfaces.agent` — komendy CLI  
- `surfaces.human` — GUI / START.cmd  

Szybki stan (JSON, obie role):

```bat
python karmin_app.py --status
python holon_agent_memory.py status --project Holon
```

---

## 5. Presety i ustawienia

| Preset | Kiedy |
|--------|--------|
| `se` | domyślna ciągłość Grok/CLI |
| `se-compact` | mniej tokenów w handoff |
| `se-long` | duże projekty, większy store |
| `chat` | EriAmo rozmowa |
| `lab-flat` | lab bez Prism |

W GUI: **Ustawienia** → preset → Zapisz.  
CLI: `python holon_configure.py use se-compact`  
Szczegóły: [CONFIGURE.md](CONFIGURE.md).

---

## 6. Język PL / EN

| Sposób | Jak |
|--------|-----|
| GUI | combobox Język / Language (+ Zapisz w Ustawieniach) |
| CLI | `python holon_configure.py lang en` |
| Jednorazowo | `python holon_configure.py --lang en help` |
| Env | `set HOLON_UI_LANG=en` |

Kolejność: `--lang` → `HOLON_UI_LANG` → `ui_lang` w settings → **pl**.

---

## 7. FAQ

**Q: Gdzie jest moja pamięć?**  
A: `holon_memory.json` w katalogu repo. Backup = kopia pliku (nie gita).

**Q: Zepsułem settings — co resetować?**  
A: Usuń `holon_settings.json` albo skopiuj `holon_settings.example.json`. **Nie** kasuj `holon_memory.json` bez prośby.

**Q: Agent „nie pamięta”?**  
A: Czy odpalono `agent_boot.py`? Czy fact ma prefiks `[Projekt]`? Czy filtr `--project` jest ten sam?

**Q: CLI jest zepsute?**  
A: Nie — CLI jest tor power-user + agent. Ty możesz żyć na `START.cmd`.

**Q: Co z Karmin_DB / DBase?**  
A: To **skarbiec / mirror**, nie primary SE. [KARMIN_BRIDGE.md](KARMIN_BRIDGE.md).

---

## 8. Mapa dokumentów

| Doc | Rola |
|------|------|
| **Ten plik** | instrukcja człowieka |
| [CONFIGURE.md](CONFIGURE.md) | konfigurator, presety, doctor, język |
| [AGENTS.md](../AGENTS.md) | obowiązkowy start **agenta** |
| [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md) | workflow SE end-to-end |
| [MEMORY_API.md](MEMORY_API.md) | API / CLI schema |
| [README.md](../README.md) | landing |

---

## 9. Checklist „działa”

- [ ] `START.cmd` otwiera panel  
- [ ] Start → widać store / work  
- [ ] Doctor nie krzyczy na braki krytyczne  
- [ ] `python agent_boot.py --no-banner` zwraca JSON z `surfaces`  
- [ ] `python holon_agent_memory.py eval` → GOLDEN_EVAL OK (gdy dev)
