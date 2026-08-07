# archiwum — martwe / research poza produktem SE

Przeniesione z roota **Karmin_Ae** (2026-08-07), bo nie wchodzą w tor:

- `agent_boot` / `holon_agent_memory` / Mneme / MemoryAPI  
- chat EriAmo: `main.py` → `holon_session`

| Artefakt | Było | Powód archiwizacji |
|----------|------|--------------------|
| `hss_demo.py` | root | Standalone demo HSS; **0 importów** z silnika Holon |
| `HSS_sim.py` | root | Symulator socketu Unix HSS; niepodpięty, Linux-only |
| `holon_fs.py` | root | HolonFS daemon; tylko factory w `__init__` + stary entrypoint — nie SE |
| `HSS_Paper_v2.5.0*.md` | root | Papers research security |
| `Rozpad_Przestrzeni_Phi.png` | root | Ilustracja do papers (~8 MB) |
| `security/holo/*.c` | `security/` | LSM / Φ-HSS kernel research, nie MemoryAPI |

**Uruchomienie z archiwum (jeśli kiedyś potrzeba):**

```bat
cd archiwum
python hss_demo.py
python holon_fs.py --help
```

Nie dodawaj tych plików z powrotem do roota bez decyzji „wracamy do research HSS/HolonFS”.
