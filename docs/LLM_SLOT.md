# LLM slot — wszczep lokalnego modelu

Pamięć Holona **nie wymaga** LLM. Slot jest dla czatu (`Session`) i insight/rumination.

## Priorytet backendów (`backend=auto`)

1. `register_local_model_factory(...)` jeśli zarejestrowana  
2. `HOLON_LLM_BASE_URL` — OpenAI-compatible (llama.cpp, vLLM, LocalAI)  
3. Ollama `localhost:11434`  
4. `GROQ_API_KEY`  
5. `DEEPSEEK_API_KEY`  
6. `None` — chat offline (pamięć działa)

## Env

```text
HOLON_LLM_BACKEND=auto|local|ollama|openai|groq|deepseek|mock
HOLON_LLM_BASE_URL=http://127.0.0.1:8080/v1
HOLON_LLM_MODEL=my-model
HOLON_LLM_API_KEY=local
HOLON_LLM_TIMEOUT=120
```

## Fabryka lokalna (Python)

```python
from holon_llm import register_local_model_factory, build_llm_client

class MyLocal:
    def __init__(self, model: str):
        self.model = model
    def chat_completion(self, messages, temperature=0.7, max_tokens=1024):
        # llama-cpp-python / transformers / …
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

cfg = Config.chat(llm_backend="openai", llm_base_url="http://127.0.0.1:8080/v1",
                  llm_model="qwen")
s = Session(cfg=cfg)
# lub:
s.set_llm_client(client)
```

## Diagnostyka

```bash
python holon_agent_memory.py llm-slot
```
