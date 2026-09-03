# Bridge Transformer w Holonie

**Status:** włączony w `Config.agent()` (2026-09-01) · **energia→routing** domknięta 2026-09-03  
**Źródło:** `transform.py`  
**Wyłączenie:** `HOLON_USE_BRIDGE=0` albo `overrides.use_bridge=false` w settings.  
Ablacja samego routingu: `bridge_energy_to_importance=false` (mixer zostaje).

## Rola (nie mylić z Embedderem)

| Warstwa | Robi | Nie robi |
|---------|------|----------|
| **Embedder** (`holon_embedder.py`) | tekst → wektor Item | attention / Φ |
| **Bridge** (`holon_bridge.py` + `transform.py`) | mixer **gotowych** tokenów + sonda energii | `encode(text)` |
| **Prism** (`holon_holography.py`) | teleport patternu na poziomy Φ | retrieval po query |

Architektura: **Bridge → (energia→importance) → Prism → Φ**.  
Embedder zostaje tor **zapisu/odczytu store** (`remember` / `recall` / handoff).

### Profil osiągów

- **Układy wielowymiarowe** (rozrzut energii w oknie, wiele komór / peaki): Bridge bije Softmax (lab ~0.72 vs ~0.23; rząd ~20+ pkt na swoim tasku).  
- **Płaski Softmax-friendly:** Bridge jest przeciętny — nie oceniać go flat cosine recall.  
- Holon (komory + sonda + Prism Φ×N) to boisko Bridge, nie płaski bag.

## Skąd model

Kolejność ładowania (`load_bridge_module`):

1. `HOLON_BRIDGE_PATH` (pełna ścieżka do `transform.py`)  
2. `C:\Users\drwis\Transformers\bridge_transformer\transform.py`  
3. `~/Transformers/bridge_transformer/transform.py`

Wymaga **PyTorch**. Brak pliku/torch → `bridge_status=unavailable:…`, pamięć działa klasycznie.

## Jak działa pamięć z Bridge (tor SE)

```
Itemy aktywne (work/recalled/świeże)
        │
        ├─ token = emb Itema (pad/trunc → bridge_d_model)     ← bez Embedder.encode
        └─ sonda/tracer = relevance × e^{-age/τ} × emotion
              (+×1.2 work, +×1.5 recalled)
        │
        ▼
  BridgeStack.forward_tokens(..., pool="energy")
        │  Lorentzian attention na dE; V z treści
        ├─► pattern  ─────────────────────────────┐
        └─► tracer   ──► bridge_energy_importance  │
                              │                    │
                              ▼                    ▼
                     importance' (w range)    PrismRouter.route
                              │                    │
                              └────────► p[lv] + phase-shift per poziom
                                               │
                                               ▼
                                         update Φ
```

### Kroki w `_update_phi`

1. Z aktywnych Itemów: token + sonda (jak wyżej).  
2. `forward_tokens(..., pool="energy")` — Lorentzian attention.  
3. **Energia → routing:** `bridge_energy_importance(tracer)` → `importance`  
   (concentration + spread + top-mass w `importance_range` Prism).  
   Dzięki temu `p[lv]` **słyszy** układ wielowymiarowy, nie tylko skalar AII/recalled.  
4. `PrismRouter.route(importance, pattern)` → update warstw Φ.  
5. Pierwsze użycie w procesie: kalibracja (~`bridge_calibrate_steps`, cache wag w RAM).

### Co Bridge zmienia, a czego nie

| Powierzchnia | Wpływ Bridge |
|--------------|--------------|
| Pattern → Φ (treść update’ów) | **tak** — mixer ≠ classical / flat-softmax |
| Prism `p[lv]` (przy `energy→p` ON) | **tak** — multi-chamber vs flat różnicuje routing |
| `recall` / `handoff` / ranking tekstu | **nie bezpośrednio** — to Embedder + cosine/lexical + komory |
| Cold start procesu | ~kilka s kalibracji; warm ≈ ms |

Diagnostyka po pierwszym Φ: `stats()` → `bridge_status`, `bridge_energy_to_importance`, `bridge_energy` (`imp_in`/`imp_out`, `structure`, `boost`, …).

## Bench / testy

```bat
python scripts/bench_bridge_vs_prism.py --steps 600
python -m unittest tests.test_holon_bridge -v
```

Oczekiwane (home turf):

- Bridge vs Softmax (energy retrieval, 600 kroków): Bridge ≫ Softmax (~0.72 vs ~0.23).  
- Prism vs flat: Prism wygrywa tor pamięci (miękkie wagi + `phase_spread`; flat = one-hot).  
- `bridge_energy_importance`: structured tracer → wyższe `importance` i inne `p[lv]` niż flat.

Tied weights (`proca_bridge_transformer_fixed.py`) jest lekko stabilniejszy w paperze; **produkt ładuje `transform.py`**.

## API lab

```python
from holon_bridge import BridgeStack, bridge_energy_importance, prism_wins_demo
import torch
import numpy as np

stack = BridgeStack(d_model=32, n_heads=2, n_layers=1, phi_levels=3)
x = torch.randn(1, 16, 32)
tracer = torch.linspace(0, 3, 16).view(1, 16, 1)
fwd = stack.forward_tokens(x, tracer, pool="energy")
imp, meta = bridge_energy_importance(1.0, tracer.view(-1).numpy())
tele = stack.teleport_to_phi(fwd.pattern, importance=imp)
# tele.weights, tele.updates[lv], tele.dominant_level, meta["imp_out"]
```

CLI:

```bat
python holon_agent_memory.py stats
python holon_agent_memory.py entangle --project Holon
```

## Config

| Pole | Domyślnie (agent) | Opis |
|------|-------------------|------|
| `use_bridge` | `True` | włącz mixer |
| `bridge_d_model` | 64 | dim tokenów Bridge |
| `bridge_n_heads` | 4 | musi dzielić `d_model` |
| `bridge_n_layers` | 2 | głębokość |
| `bridge_calibrate_steps` | 400 | kroki przy pierwszym użyciu |
| `bridge_energy_to_importance` | `True` | sonda → importance → Prism `p[lv]` |
