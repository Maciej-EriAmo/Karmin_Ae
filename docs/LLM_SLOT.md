# LLM slot — wszczep lokalnego / chmurowego modelu

Pamięć Holona **nie wymaga** LLM. Slot jest dla czatu (`Session`) i insight/rumination.

## Priorytet backendów (`backend=auto`)

1. `register_local_model_factory(...)` jeśli zarejestrowana  
2. `HOLON_LLM_BASE_URL` — OpenAI-compatible (llama.cpp, vLLM, LocalAI)  
3. Ollama `localhost:11434`  
4. **Gemini** — `GEMINI_API_KEY` lub `GOOGLE_API_KEY`  
5. `GROQ_API_KEY`  
6. `DEEPSEEK_API_KEY`  
7. `None` — chat offline (pamięć działa)

## Env

```text
HOLON_LLM_BACKEND=auto|local|ollama|gemini|openai|groq|deepseek|mock
HOLON_LLM_BASE_URL=http://127.0.0.1:8080/v1
HOLON_LLM_MODEL=my-model
HOLON_LLM_API_KEY=local
HOLON_LLM_TIMEOUT=120

# Gemini (Google AI Studio)
GEMINI_API_KEY=…                 # lub GOOGLE_API_KEY
GEMINI_MODEL=gemini-2.0-flash    # opcjonalnie; default w holon_llm
```

## Pomocnik SE agenta (nie chat) — domyślnie **Ollama lokalnie**

Pomaga **Grok/CLI** po bootcie (orientacja, draft close, pytania).  
Implementacja: **`holon_helper.py`** (moduł) · wejście CLI: `holon_agent_memory.py assist` lub `python -m holon_helper`.  
U Ciebie: **`gemma3:4b` przez Ollamę** (nie cloud Gemini API).

| Slot | Config | Domyślnie |
|------|--------|-----------|
| **Chat** (człowiek) | `llm_backend` / `llm_model` | Ollama `gemma3:4b` |
| **Helper** (agent) | `helper_llm_backend` / `helper_llm_model` | Ollama `gemma3:4b` |

### Zadania (`--task`)

| Task | Rola |
|------|------|
| `orient` (default) | stan sesji, co domknąć, rekomendowane CLI |
| `draft-close` | szkic WORK/FACT do `close` (agent zatwierdza) |
| `hygiene` | podpowiedzi crystallize / work-spam / szum |
| `ask` | wolne pytanie (`--ask "…"`) |

### CLI

```powershell
ollama serve
ollama pull gemma3:4b

python holon_agent_memory.py llm-slot
python holon_agent_memory.py assist --project Holon
python holon_agent_memory.py assist --task hygiene --project Holon
python holon_agent_memory.py assist --task draft-close --project Holon
python holon_agent_memory.py assist --ask "co crystallize a co close?" --project Holon
python -m holon_helper --project Holon
python -m holon_helper --task draft-close --project Cynober_studio
```

Wynik: tekst + opcjonalnie `actions[]` (gotowe komendy `close` / `set-work` / `crystallize`).  
Bez Ollamy / klucza: graceful degrade (ok=false, błąd w `HelperReport`).

Cloud Gemini (opcjonalnie): `helper_llm_backend=gemini` + `GEMINI_API_KEY`  
(lub override w `holon_settings.json` / `holon_configure.py`).

Kod: [`holon_helper.py`](../holon_helper.py) · workflow: [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md).

## Gemini jako backend czatu (opcjonalnie)

```powershell
python holon_configure.py set-override llm_backend gemini
python holon_configure.py set-override llm_model gemini-2.0-flash
```

Endpoint: OpenAI-compatible  
`https://generativelanguage.googleapis.com/v1beta/openai`  
Modele m.in.: `gemini-2.0-flash`, `gemini-2.5-flash`, `gemini-1.5-pro`.


## Ollama (lokalnie)

```text
llm_backend=ollama
llm_model=gemma3:4b
llm_base_url=   # puste
```

## Fabryka lokalna (Python)

```python
from holon_llm import register_local_model_factory, build_llm_client

class MyLocal:
    def __init__(self, model: str):
        self.model = model
    def chat_completion(self, messages, temperature=0.7, max_tokens=1024):
        return "…"

def factory(*, model="local", **kw):
    return MyLocal(model)

register_local_model_factory(factory)
client = build_llm_client(backend="local", model="/models/x.gguf")
```

## Session

```python
from holon_session import Session
from holon_config import Config

cfg = Config.chat(llm_backend="gemini", llm_model="gemini-2.0-flash")
s = Session(cfg=cfg)
```

## Diagnostyka

```bash
python holon_agent_memory.py llm-slot
```
