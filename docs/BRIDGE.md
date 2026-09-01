# Bridge Transformer w Holonie

**Status:** włączony w `Config.agent()` (2026-09-01) · źródło: `transform.py`  
**Wyłączenie:** `HOLON_USE_BRIDGE=0` albo `overrides.use_bridge=false` w settings.

## Rola (nie mylić z Embedderem)

| Warstwa | Robi | Nie robi |
|---------|------|----------|
| **Embedder** (`holon_embedder.py`) | tekst → wektor Item | attention / Φ |
| **Bridge** (`holon_bridge.py` + `transform.py`) | mixer **gotowych** tokenów + sonda energii | `encode(text)` |
| **Prism** (`holon_holography.py`) | teleport patternu na poziomy Φ | retrieval po query |

Architektura zamierzona: **Bridge → Prism → Φ**. Embedder zostaje tor zapisu/odczytu store.

## Skąd model

Kolejność ładowania (`load_bridge_module`):

1. `HOLON_BRIDGE_PATH` (pełna ścieżka do `transform.py`)  
2. `C:\Users\drwis\Transformers\bridge_transformer\transform.py`  
3. `~/Transformers/bridge_transformer/transform.py`

Wymaga **PyTorch**. Brak pliku/torch → `bridge_status=unavailable:…`, pamięć działa klasycznie.

## Tor w `_update_phi`

1. Z aktywnych Itemów: token = wektor (pad/trunc do `bridge_d_model`), sonda = relevance × age × emotion.  
2. `BridgeStack.forward_tokens(..., pool="energy")` — Lorentzian attention.  
3. Wektor → `PrismRouter.route(importance, pattern)` → update warstw Φ.  
4. Pierwsze użycie: kalibracja (~`bridge_calibrate_steps`, cache w procesie).

## Bench / testy

```bat
python scripts/bench_bridge_vs_prism.py --steps 600
python -m unittest tests.test_holon_bridge -v
```

Oczekiwane (home turf):

- Bridge vs Softmax (energy retrieval, 600 kroków): Bridge ≫ Softmax (~0.72 vs ~0.23).  
- Prism vs flat: Prism wygrywa tor pamięci (miękkie wagi + `phase_spread` fazy; flat = one-hot bez geometrii).

Tied weights (`proca_bridge_transformer_fixed.py`) jest lekko stabilniejszy w paperze; **produkt ładuje `transform.py`** (kanon użytkownika).

## API lab

```python
from holon_bridge import BridgeStack, prism_wins_demo
import torch

stack = BridgeStack(d_model=32, n_heads=2, n_layers=1, phi_levels=3)
x = torch.randn(1, 16, 32)
tracer = torch.linspace(0, 3, 16).view(1, 16, 1)
fwd, tele = stack.bridge_then_prism(x, tracer, importance=2.2, pool="energy")
# tele.weights, tele.updates[lv], tele.dominant_level
```

CLI diagnostyka: `python holon_agent_memory.py stats` → `bridge_mode` / pole w silniku po pierwszym Φ;  
`python holon_agent_memory.py entangle --project Holon`.

## Config

| Pole | Domyślnie (agent) | Opis |
|------|-------------------|------|
| `use_bridge` | `True` | włącz mixer |
| `bridge_d_model` | 64 | dim tokenów Bridge |
| `bridge_n_heads` | 4 | musi dzielić `d_model` |
| `bridge_n_layers` | 2 | głębokość |
| `bridge_calibrate_steps` | 400 | kroki przy pierwszym użyciu |
