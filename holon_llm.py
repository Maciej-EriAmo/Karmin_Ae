# -*- coding: utf-8 -*-
"""
holon_llm.py — klient LLM + **miejsce wszczepu lokalnego modelu**.

Kolejność (``backend=auto``):
  1. Zarejestrowana fabryka lokalna (``register_local_model_factory``)
  2. HOLON_LLM_BASE_URL / cfg.llm_base_url — dowolny OpenAI-compatible (llama.cpp, vLLM…)
  3. Ollama na localhost:11434
  4. Gemini (GEMINI_API_KEY / GOOGLE_API_KEY) — OpenAI-compatible Google AI
  5. GROQ_API_KEY
  6. DEEPSEEK_API_KEY
  7. None → brak LLM (pamięć i tak działa)

Env (priorytet nad auto-detect gdy ustawione wprost):
  HOLON_LLM_BACKEND = auto|local|ollama|openai|gemini|google|groq|deepseek|mock
  HOLON_LLM_BASE_URL, HOLON_LLM_MODEL, HOLON_LLM_API_KEY
  OLLAMA_MODEL, GEMINI_API_KEY, GOOGLE_API_KEY, GEMINI_MODEL
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

try:
    import requests
except ImportError:  # ekstremalnie chudy host
    requests = None  # type: ignore


@runtime_checkable
class ChatClient(Protocol):
    """Kontrakt LLM — wstrzyknij cokolwiek z chat_completion()."""

    model: str

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str: ...


# Fabryka: (model, base_url, api_key, timeout_s, **kw) -> ChatClient
LocalModelFactory = Callable[..., ChatClient]

_LOCAL_FACTORY: Optional[LocalModelFactory] = None


def register_local_model_factory(factory: Optional[LocalModelFactory]) -> None:
    """Wszczep własny lokalny backend (transformers, llama-cpp-python, …).

    Przykład (na kiedyś)::

        def my_local(*, model, **kw):
            return MyLlamaWrapper(model_path=model)

        register_local_model_factory(my_local)
        client = build_llm_client(backend="local", model="/path/to/gguf")
    """
    global _LOCAL_FACTORY
    _LOCAL_FACTORY = factory


def local_model_factory() -> Optional[LocalModelFactory]:
    return _LOCAL_FACTORY


class OpenAIClient:
    """OpenAI-compatible: Ollama, llama.cpp server, vLLM, Groq, DeepSeek, …"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen2.5:3b",
        timeout_s: float = 120.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = float(timeout_s)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        if requests is None:
            return "[Błąd LLM: brak pakietu requests]"
        filtered = [m for m in messages if m.get("content", "").strip()]
        if not filtered:
            return "[Błąd: brak wiadomości do wysłania]"
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": filtered,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=self.timeout_s
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            # nie dumpuj stacka w pętli czatu — krótki komunikat
            status = ""
            if hasattr(e, "response") and getattr(e, "response") is not None:
                try:
                    status = f" HTTP {e.response.status_code}"
                except Exception:
                    pass
            return f"[Błąd LLM{status}: {e}]"


class MockLLMClient:
    """Deterministyczny stub — testy / offline bez halucynacji „działa model”."""

    def __init__(self, model: str = "mock"):
        self.model = model

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        last = ""
        for m in reversed(messages):
            if m.get("role") == "user" and m.get("content"):
                last = m["content"][:200]
                break
        return f"[mock:{self.model}] Otrzymano {len(messages)} msg. Ostatni user: {last}"


def _ollama_running(base: str = "http://localhost:11434", timeout: float = 2.0) -> bool:
    if requests is None:
        return False
    try:
        r = requests.get(base, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _is_http_url(url: str) -> bool:
    """True tylko dla http(s)://… — ścieżki dyskowe (np. folder modeli Ollamy) nie są base_url."""
    u = (url or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")


# Google AI Studio / Gemini — OpenAI-compatible chat completions
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def _gemini_api_key(explicit: Optional[str] = None) -> str:
    """Klucz z argumentu, HOLON_LLM_API_KEY, GEMINI_API_KEY lub GOOGLE_API_KEY."""
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    return (
        _env("HOLON_LLM_API_KEY")
        or _env("GEMINI_API_KEY")
        or _env("GOOGLE_API_KEY")
        or _env("GOOGLE_AI_API_KEY")
    )


def build_llm_client(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    *,
    backend: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_s: Optional[float] = None,
    quiet: bool = False,
) -> Optional[ChatClient]:
    """Zbuduj klienta wg backendu / env / auto-detect.

    Zwraca ``None`` gdy brak backendu (pamięć Holona działa bez LLM).
    """
    be = (backend or _env("HOLON_LLM_BACKEND") or _env("HOLON_LLM") or "auto").lower()
    m = model or _env("HOLON_LLM_MODEL") or _env("OLLAMA_MODEL") or ""
    url_raw = (base_url or _env("HOLON_LLM_BASE_URL") or "").strip().rstrip("/")
    url = url_raw if _is_http_url(url_raw) else ""
    key = api_key if api_key is not None else _env("HOLON_LLM_API_KEY")
    timeout = float(timeout_s or _env("HOLON_LLM_TIMEOUT", "120") or 120)

    def log(msg: str) -> None:
        if not quiet:
            print(msg)

    if url_raw and not url:
        log(
            f"[LLM] llm_base_url nie jest URL-em HTTP(S) ({url_raw!r}) — ignoruję. "
            "Dla Ollamy zostaw puste (auto :11434/v1) albo http://localhost:11434/v1; "
            "ścieżka folderu modeli (np. ~/.ollama/models) nie jest API."
        )

    if be == "mock":
        log("[LLM] Backend: mock")
        return MockLLMClient(model=m or "mock")

    # 1) jawna fabryka lokalna
    if be in ("local", "custom") or (be == "auto" and _LOCAL_FACTORY is not None):
        if _LOCAL_FACTORY is not None:
            log(f"[LLM] Backend: local factory → {m or 'default'}")
            return _LOCAL_FACTORY(
                model=m or "local",
                base_url=url or None,
                api_key=key or "local",
                timeout_s=timeout,
            )
        if be in ("local", "custom") and not url:
            log("[LLM] backend=local bez fabryki i bez HOLON_LLM_BASE_URL → None")
            return None

    # 2) OpenAI-compatible URL (llama.cpp, vLLM, LocalAI, …)
    if url or be in ("openai", "openai-compatible", "llamacpp", "vllm"):
        if not url:
            url = "http://127.0.0.1:8080/v1"
        mm = m or "local-model"
        log(f"[LLM] Backend: OpenAI-compatible {url} → {mm}")
        return OpenAIClient(
            api_key=key or "local",
            base_url=url if url.endswith("/v1") or "/v1" in url else url,
            model=mm,
            timeout_s=timeout,
        )

    # 3) Ollama
    if be in ("auto", "ollama"):
        if _ollama_running():
            mm = m or "qwen2.5:3b"
            log(f"[LLM] Backend: Ollama lokalnie → {mm}")
            return OpenAIClient(
                api_key=key or "ollama",
                base_url="http://localhost:11434/v1",
                model=mm,
                timeout_s=timeout,
            )
        if be == "ollama":
            log("[LLM] ollama: brak serwera na :11434")
            return None

    # 4) Google Gemini (AI Studio) — OpenAI-compatible endpoint
    gemini_key = _gemini_api_key(key if be in ("gemini", "google") else None)
    if be in ("auto", "gemini", "google") and gemini_key:
        mm = m or _env("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        log(f"[LLM] Backend: Gemini → {mm}")
        return OpenAIClient(
            api_key=gemini_key,
            base_url=GEMINI_OPENAI_BASE,
            model=mm,
            timeout_s=timeout,
        )
    if be in ("gemini", "google"):
        log(
            "[LLM] gemini: brak klucza. Ustaw GEMINI_API_KEY lub GOOGLE_API_KEY "
            "(albo HOLON_LLM_API_KEY) z https://aistudio.google.com/apikey"
        )
        return None

    # 5) Groq
    groq_key = key if (key or "").startswith("gsk_") else _env("GROQ_API_KEY")
    if be in ("auto", "groq") and groq_key.startswith("gsk_"):
        mm = m or "llama-3.3-70b-versatile"
        log(f"[LLM] Backend: Groq → {mm}")
        return OpenAIClient(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
            model=mm,
            timeout_s=timeout,
        )

    # 6) DeepSeek
    ds_key = key if be == "deepseek" else _env("DEEPSEEK_API_KEY")
    if be in ("auto", "deepseek") and ds_key:
        mm = m or "deepseek-chat"
        log(f"[LLM] Backend: DeepSeek → {mm}")
        return OpenAIClient(
            api_key=ds_key,
            base_url="https://api.deepseek.com/v1",
            model=mm,
            timeout_s=timeout,
        )

    if be != "auto":
        log(f"[LLM] Backend '{be}' niedostępny.")
    else:
        log(
            "[LLM] Brak backendu. Opcje: ollama serve | GEMINI_API_KEY | "
            "HOLON_LLM_BASE_URL=… | GROQ_API_KEY | register_local_model_factory()."
        )
    return None


def describe_llm_slot() -> Dict[str, Any]:
    """Diagnostyka wszczepu — bez side-effect sieci (poza opcjonalnym ollama ping)."""
    return {
        "local_factory_registered": _LOCAL_FACTORY is not None,
        "env_backend": _env("HOLON_LLM_BACKEND") or _env("HOLON_LLM") or "auto",
        "env_base_url": _env("HOLON_LLM_BASE_URL"),
        "env_model": _env("HOLON_LLM_MODEL") or _env("OLLAMA_MODEL") or _env("GEMINI_MODEL"),
        "ollama_up": _ollama_running(),
        "has_gemini": bool(_gemini_api_key()),
        "has_groq": _env("GROQ_API_KEY").startswith("gsk_"),
        "has_deepseek": bool(_env("DEEPSEEK_API_KEY")),
        "gemini_default_model": DEFAULT_GEMINI_MODEL,
    }
