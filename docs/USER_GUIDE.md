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
- **proto-emocje (AII)** — cichy reżim w tle (focus, napięcie, spokój),
- **bez chmury** — pliki u Ciebie; nie Mem0/SaaS.

| Plik | Znaczenie |
|------|-----------|
| `holon_memory.json` | **stan umysłu** (fakty, work, **aii**) — nie commituj |
| `holon_settings.json` | **preferencje** (profil, projekt, język, LLM) — nie commituj |
| `AGENTS.md` | kontrakt **dla agenta** |

### Proto-emocje w skrócie (dla Ciebie)

Nie ustawiasz „smutku suwakiem”. Silnik Holona trzyma w tle stan **AII** (`emotion`, `vacuum_signal`, `focus`):

- działa **często nieuświadomie** — nie jest tematem rozmowy,
- przy **focus** (kod/debug) łatwiej trzymać skupienie i jeden wątek,
- po długiej przerwie **wraca do spokoju** (nie trzyma alarmu wiecznie),
- w czacie EriAmo lekko barwi ton (**milej się rozmawia**), bez teatralnego afektu.

To **boost klimatu współpracy**, nie funkcja do klikiwania w panelu.  
Pełny opis (kod + grupa docelowa): **[AII_PROTO_EMOTIONS.md](AII_PROTO_EMOTIONS.md)**.

---

## 2. Pierwszy start (KANON)

```bat
cd C:\Users\drwis\Karmin_Ae
pip install -r requirements.txt
START.cmd
```

| Potrzeba | Start |
|----------|--------|
| Panel (codzień) | `START.cmd` |
| Chat / brainstorm | `START_CHAT.cmd` lub przycisk w panelu |
| Agent SE (Grok) | `python agent_boot.py` |

Albo: `python karmin_app.py`.  
Brak okienka (tkinter): `python holon_configure.py wizard` (**advanced**).

---

## 3. Control Center (`karmin_app.py`)

| Zakładka | Co robisz |
|----------|-----------|
| **Start** | Stan store, aktywny work, top facts, doctor score, podpowiedzi. **Odśwież** / **Doctor** / **Pokaż boot (agent)**. |
| **Sesja SE** | Podgląd **handoff** (to samo, co agent po bootcie). Projekt, `--since` (np. 24h). **Załaduj handoff** / **Zapisz handoff.md**. |
| **Pamięć** | Bez CLI: **fact**, **work**, **close** (summary + next work), **krystalizuj**. |
| **Ustawienia** | Preset (`se` / `se-compact` / …), domyślny projekt, język PL/EN. **Zapisz**. Zaawansowane: „CLI configure…”. |
| **Konsola** | Historia poleceń; pełny log |
| **Pomoc** | Skrót torów człowiek vs agent. |

### Linia poleceń (hybryda CLI w GUI)

Na **dole panelu** jest pole:

```text
Polecenie › fact [Holon] notatka
```

Enter / **Wykonaj**. Strzałki ↑↓ = historia.

To jest „linia komend” bez PowerShella — dla osób, które wolą pisać polecenia niż klikać formularze (skrypty `.md` dla AI to inna sprawa; tu wydajesz komendy **sobie**).

| Polecenie | Efekt |
|-----------|--------|
| `help` | lista komend |
| `status [projekt]` | stan work/fakty/doctor |
| `fact …` | zapisz fact |
| `work …` | ustaw work |
| `boot [--project P] [--since 24h]` | handoff jak agent |
| `handoff` / `handoff-md` | podgląd / plik |
| `close fact=… work=…` | domknięcie sesji |
| `crystallize` · `doctor` · `recall …` | jak w CLI |
| `use se-compact` | preset |
| `! python agent_boot.py …` | surowy subprocess w repo |

Bez GUI (jednorazowo):

```bat
python karmin_app.py -c "help"
python karmin_app.py -c "status Holon"
python karmin_app.py -c "fact [Holon] z linii"
```

### Chat / brainstorm (ukłon dla zapominalskich)

Rozmowa z EriAmo (LLM) to **osobny tor** od agenta SE — ale pamięć jest **wspólna** (`holon_memory.json`), w tym stan **AII** (proto-emocje w tle: focus, spokój, vacuum).  
Tu najbardziej widać „lekki boost” tonu — w torze SE dominuje handoff (fact/work).

| Jak | Co robi |
|-----|---------|
| Przycisk **Chat / brainstorm** na Start | nowe okno → `main_aware.py` |
| Polecenie `chat` / `brainstorm` | to samo |
| `chat aware` · `chat basic` · `chat secure` | warianty |
| Dwuklik **`START_CHAT.cmd`** | od razu czat, bez panelu |

```bat
python karmin_app.py -c "chat"
START_CHAT.cmd
python main_aware.py
```

W oknie czatu: `quit` kończy. **Agent SE** nadal: `python agent_boot.py` (nie mylić z burzą mózgów).

### Typowy dzień (człowiek)

1. `START.cmd`  
2. Zakładka **Start** → czy work/fakty mają sens  
3. Burza mózgów: **Chat / brainstorm** (osobne okno)  
4. Po pracy w agentcie (lub ręcznie): **Pamięć** / linia poleceń → close / fact  
5. Gdy store „szumi”: **Krystalizuj**  
6. Od czasu do czasu: **Doctor**

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

**Q: Gdzie ustawiam emocje agenta?**  
A: Nigdzie ręcznie. **Proto-emocje (AII)** aktualizują się w tle z rozmowy i czasu. To nie jest skórka czatu — [AII_PROTO_EMOTIONS.md](AII_PROTO_EMOTIONS.md).

**Q: Gdzie jest moja pamięć?**  
A: `holon_memory.json` w katalogu repo (fakty, work, **aii**). Backup = kopia pliku (nie gita).

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
| [AII_PROTO_EMOTIONS.md](AII_PROTO_EMOTIONS.md) | proto-emocje: kod + grupa docelowa |
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
