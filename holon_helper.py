# -*- coding: utf-8 -*-
"""
holon_helper.py — **pomocnik SE dla agenta** (Grok/CLI), nie chat EriAmo.

Domyślny mózg: **Ollama lokalnie** (``helper_llm_backend=ollama``, model ``gemma3:4b``).
Opcjonalnie chmura: ``helper_llm_backend=gemini`` + ``GEMINI_API_KEY``.

Użycie:
  python holon_agent_memory.py assist
  python holon_agent_memory.py assist --task orient
  python holon_agent_memory.py assist --task draft-close
  python holon_agent_memory.py assist --ask \"co domknąć w tej sesji?\"
  python -m holon_helper --project Holon
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from holon_agent_memory import AgentMemory
    from holon_config import Config
    from holon_llm import ChatClient

ROOT = Path(__file__).resolve().parent


@dataclass
class HelperReport:
    """Wynik jednego wywołania pomocnika."""

    ok: bool
    task: str
    backend: str = ""
    model: str = ""
    llm_used: bool = False
    text: str = ""
    structured: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "task": self.task,
            "backend": self.backend,
            "model": self.model,
            "llm_used": self.llm_used,
            "text": self.text,
            "structured": self.structured,
            "error": self.error,
            "actions": self.actions,
        }


def build_helper_client(
    cfg: Optional["Config"] = None,
    *,
    quiet: bool = True,
) -> Optional["ChatClient"]:
    """Klient LLM wyłącznie dla slotu pomocnika (Gemini domyślnie)."""
    from holon_config import Config
    from holon_llm import build_llm_client, _gemini_api_key

    if cfg is None:
        try:
            cfg = Config.from_settings(profile="agent")
        except Exception:
            cfg = Config.agent()

    if not getattr(cfg, "helper_enabled", True):
        return None

    be = (getattr(cfg, "helper_llm_backend", None) or "ollama").strip().lower()
    model = (getattr(cfg, "helper_llm_model", None) or "").strip()
    key = (getattr(cfg, "helper_llm_api_key", None) or "").strip()
    timeout = float(getattr(cfg, "helper_llm_timeout_s", 120.0) or 120.0)

    if not key:
        key = _gemini_api_key(None) or (getattr(cfg, "llm_api_key", None) or "")

    if be in ("", "auto"):
        # auto helper: Ollama gdy stoi, inaczej Gemini cloud jeśli klucz, inaczej chat slot
        from holon_llm import _ollama_running

        if _ollama_running():
            be = "ollama"
            model = model or getattr(cfg, "llm_model", None) or "gemma3:4b"
        elif _gemini_api_key(key or None) or _gemini_api_key(None):
            be = "gemini"
            model = model or "gemini-2.0-flash"
        else:
            be = (getattr(cfg, "llm_backend", None) or "auto").strip().lower()
            model = model or (getattr(cfg, "llm_model", None) or "")

    if be in ("ollama",) and not model:
        model = "gemma3:4b"
    if be in ("gemini", "google") and not model:
        model = "gemini-2.0-flash"

    return build_llm_client(
        api_key=key or None,
        model=model or None,
        backend=be,
        timeout_s=timeout,
        quiet=quiet,
    )


def describe_helper_slot(cfg: Optional["Config"] = None) -> Dict[str, Any]:
    from holon_config import Config
    from holon_llm import _gemini_api_key, describe_llm_slot

    if cfg is None:
        try:
            cfg = Config.from_settings(profile="agent")
        except Exception:
            cfg = Config.agent()
    return {
        "helper_enabled": bool(getattr(cfg, "helper_enabled", True)),
        "helper_llm_backend": getattr(cfg, "helper_llm_backend", "gemini"),
        "helper_llm_model": getattr(cfg, "helper_llm_model", "gemini-2.0-flash"),
        "has_gemini_key": bool(
            (getattr(cfg, "helper_llm_api_key", None) or "").strip()
            or _gemini_api_key(None)
        ),
        "role": "SE agent helper (not chat) — assist / draft-close / orient",
        "cli": "python holon_agent_memory.py assist [--task orient|hygiene|draft-close|ask]",
        "default_path": "Ollama local (gemma3:4b); optional cloud gemini API",
        "llm_slot": describe_llm_slot(),
    }


class HolonHelper:
    """
    Pomocnik agenta: czyta handoff, proponuje kroki, drafty close/fact.
    Gemini = mózg; store Holona = kanon (helper nie zapisuje bez flagi).
    """

    def __init__(
        self,
        am: "AgentMemory",
        *,
        project: str = "",
        client: Optional["ChatClient"] = None,
        quiet: bool = True,
    ):
        self.am = am
        self.project = (project or "").strip()
        self.cfg = am.hm.cfg
        self.quiet = quiet
        self._client = client

    @property
    def client(self) -> Optional["ChatClient"]:
        if self._client is None and getattr(self.cfg, "helper_enabled", True):
            self._client = build_helper_client(self.cfg, quiet=self.quiet)
        return self._client

    def handoff_ctx(self, *, compact: bool = True) -> Dict[str, Any]:
        return self.am.handoff(
            project=self.project,
            include_digest=False,
            compact=compact,
        )

    def _ctx_blob(self, h: Dict[str, Any], limit: int = 3500) -> str:
        def _lines(items: List[Any], key: str = "content") -> List[str]:
            out = []
            for it in items or []:
                if isinstance(it, dict):
                    out.append(str(it.get(key) or it.get("text") or "")[:400])
                else:
                    out.append(str(it)[:400])
            return [x for x in out if x]

        parts = [
            f"project_filter: {h.get('project_filter') or self.project or '-'}",
            f"stats: {json.dumps(h.get('stats') or {}, ensure_ascii=False)}",
            "active_work:",
            *("  - " + x for x in _lines(h.get("active_work") or [])),
            "key_facts:",
            *("  - " + x for x in _lines(h.get("key_facts") or [])),
            "recommended_actions:",
            *("  - " + str(x) for x in (h.get("recommended_actions") or [])[:6]),
            "suggested_mneme:",
            *("  - " + str(x) for x in (h.get("suggested_mneme") or [])[:4]),
        ]
        if h.get("wake"):
            parts.insert(1, f"wake: {str(h.get('wake'))[:300]}")
        text = "\n".join(parts)
        return text if len(text) <= limit else text[:limit] + "\n…[truncated]"

    def hygiene(self) -> HelperReport:
        """Bez LLM — szybka higiena z handoff."""
        h = self.handoff_ctx()
        st = h.get("stats") or {}
        work = h.get("active_work") or []
        facts_n = int(st.get("facts") or 0)
        actions = list(h.get("recommended_actions") or [])
        notes = []
        if len(work) > 1:
            notes.append(f"work-spam: {len(work)} aktywnych (kanon = 1)")
        if facts_n > 80:
            notes.append(f"store szumi: facts≈{facts_n} — rozważ crystallize")
        if not work:
            notes.append("brak active_work — set-work lub close poprzedniej sesji")
        if not notes:
            notes.append("higiena OK: 1 work, recommended_actions obecne")
        text = "\n".join(f"• {n}" for n in notes)
        if actions:
            text += "\n\nDalej:\n" + "\n".join(f"  {a}" for a in actions[:5])
        return HelperReport(
            ok=True,
            task="hygiene",
            text=text,
            structured={"notes": notes, "stats": st, "work_n": len(work)},
            actions=actions[:5],
            backend="rules",
            model="none",
            llm_used=False,
        )

    def _llm(self, system: str, user: str, *, max_tokens: int = 700) -> HelperReport:
        c = self.client
        be = getattr(self.cfg, "helper_llm_backend", "gemini") or "gemini"
        model = getattr(c, "model", "") if c else (getattr(self.cfg, "helper_llm_model", "") or "")
        if c is None:
            return HelperReport(
                ok=False,
                task="llm",
                backend=be,
                model=model,
                error=(
                    "Brak klienta pomocnika. Lokalnie: ollama serve + model "
                    f"(np. gemma3:4b), helper_llm_backend=ollama. "
                    "Cloud: GEMINI_API_KEY + helper_llm_backend=gemini."
                ),
                actions=[
                    "ollama serve",
                    "ollama pull gemma3:4b",
                    "python holon_configure.py set-override helper_llm_backend ollama",
                    "python holon_configure.py set-override helper_llm_model gemma3:4b",
                    "python holon_agent_memory.py assist --task hygiene  # bez LLM",
                ],
            )
        try:
            reply = c.chat_completion(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
            )
        except Exception as e:
            return HelperReport(
                ok=False,
                task="llm",
                backend=be,
                model=getattr(c, "model", model),
                error=str(e),
                llm_used=True,
            )
        err = ""
        ok = True
        if isinstance(reply, str) and reply.startswith("[Błąd"):
            ok = False
            err = reply
        return HelperReport(
            ok=ok,
            task="llm",
            backend=be,
            model=getattr(c, "model", model),
            text=(reply or "").strip(),
            error=err,
            llm_used=True,
        )

    def orient(self) -> HelperReport:
        """Gemini (lub fallback): krótka orientacja agenta po bootcie."""
        h = self.handoff_ctx()
        base = self.hygiene()
        sys_p = (
            "Jesteś pomocnikiem pamięci SE Holon dla agenta CLI (Grok). "
            "Nie jesteś chatbotem dla człowieka. "
            "Odpowiedz po polsku, zwięźle (max ~12 linii). "
            "Struktura: 1) stan 2) co domknąć 3) 2–4 konkretne komendy Holon CLI. "
            "Nie zmyślaj faktów spoza kontekstu. Nie recytuj AII/emocji."
        )
        user = (
            "Kontekst handoff (kanon):\n"
            f"{self._ctx_blob(h)}\n\n"
            "Zrób orientację sesji dla agenta."
        )
        rep = self._llm(sys_p, user, max_tokens=500)
        rep.task = "orient"
        if not rep.ok:
            # bez Gemini i tak daj higienę
            base.error = rep.error
            base.task = "orient"
            base.text = (
                "[pomocnik bez LLM — higiena regułowa]\n"
                + base.text
                + (f"\n\n({rep.error})" if rep.error else "")
            )
            return base
        rep.actions = list(h.get("recommended_actions") or [])[:5]
        rep.structured = {"hygiene": base.structured}
        return rep

    def draft_close(self) -> HelperReport:
        """Draft --work-text / --fact-text do close (do akceptacji agenta)."""
        h = self.handoff_ctx()
        sys_p = (
            "Jesteś pomocnikiem SE Holon. Na podstawie handoffu napisz draft domknięcia sesji. "
            "Format DOKŁADNIE (po jednej linii, bez powtórzeń):\n"
            "WORK: <jedna linia: co zostaje jako next work / stan wątku — NIE pisz "
            "'sesja zakończona' jeśli active_work mówi inaczej>\n"
            "FACT: <1–2 zdania trwałego faktu z active_work + key_facts — tylko to, "
            "co widać w handoffie; nie zmyślaj wersji/planów>\n"
            "Po polsku, konkret, bez ozdobników."
        )
        user = f"Handoff:\n{self._ctx_blob(h)}\n\nNapisz WORK i FACT."
        rep = self._llm(sys_p, user, max_tokens=400)
        rep.task = "draft-close"
        if rep.ok and rep.text:
            work, fact = "", ""
            for line in rep.text.splitlines():
                s = line.strip()
                if s.upper().startswith("WORK:"):
                    work = s.split(":", 1)[-1].strip()
                elif s.upper().startswith("FACT:"):
                    fact = s.split(":", 1)[-1].strip()
            rep.structured = {"work_text": work, "fact_text": fact}
            if work or fact:
                proj = self.project or "Holon"
                rep.actions = [
                    f'python holon_agent_memory.py close --work-text "{work}" '
                    f'--fact-text "{fact}" --project {proj}'
                ]
        return rep

    def ask(self, question: str) -> HelperReport:
        """Pytanie agenta do pomocnika na tle handoffu."""
        q = (question or "").strip()
        if not q:
            return HelperReport(ok=False, task="ask", error="puste pytanie")
        h = self.handoff_ctx()
        sys_p = (
            "Jesteś pomocnikiem pamięci SE Holon dla agenta. "
            "Odpowiadaj krótko po polsku, opieraj się na handoffie, "
            "proponuj komendy Holon gdy pasują. Nie jesteś czatem dla usera."
        )
        user = f"Handoff:\n{self._ctx_blob(h)}\n\nPytanie agenta:\n{q}"
        rep = self._llm(sys_p, user, max_tokens=600)
        rep.task = "ask"
        rep.structured = {"question": q}
        return rep

    def run(self, task: str = "orient", *, text: str = "") -> HelperReport:
        t = (task or "orient").strip().lower().replace("_", "-")
        if t in ("hygiene", "higiena"):
            return self.hygiene()
        if t in ("orient", "boot", "status", "help-me"):
            return self.orient()
        if t in ("draft-close", "close", "draft_close"):
            return self.draft_close()
        if t in ("ask", "q", "question"):
            return self.ask(text)
        return HelperReport(
            ok=False,
            task=t,
            error=f"nieznany task={t!r}; użyj: orient|hygiene|draft-close|ask",
        )


def open_helper(
    *,
    project: str = "",
    memory_path: str = "holon_memory.json",
    quiet: bool = True,
) -> HolonHelper:
    from holon_agent_memory import AgentMemory

    am = AgentMemory.open(memory_path=memory_path, profile="agent")
    return HolonHelper(am, project=project, quiet=quiet)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(description="Holon SE helper (Gemini → agent)")
    p.add_argument(
        "--task",
        default="orient",
        help="orient | hygiene | draft-close | ask",
    )
    p.add_argument("--ask", dest="ask_text", default="", help="pytanie (task=ask)")
    p.add_argument("--text", default="", help="alias --ask")
    p.add_argument("--project", default="")
    p.add_argument("--path", default="holon_memory.json")
    p.add_argument("--json", action="store_true")
    p.add_argument("--slot", action="store_true", help="tylko describe_helper_slot")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    if args.slot:
        print(json.dumps(describe_helper_slot(), indent=2, ensure_ascii=False))
        return 0

    helper = open_helper(
        project=args.project,
        memory_path=args.path,
        quiet=not args.verbose,
    )
    task = args.task
    text = args.ask_text or args.text
    if text and task in ("orient", "hygiene"):
        task = "ask"
    rep = helper.run(task, text=text)
    if args.json:
        print(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
    else:
        head = f"[holon-helper] task={rep.task} backend={rep.backend} model={rep.model} llm={rep.llm_used}"
        print(head)
        if rep.error:
            print("ERROR:", rep.error)
        if rep.text:
            print(rep.text)
        if rep.structured and not args.json:
            if rep.structured.get("work_text") or rep.structured.get("fact_text"):
                print("\n--- structured ---")
                print("WORK:", rep.structured.get("work_text") or "")
                print("FACT:", rep.structured.get("fact_text") or "")
        if rep.actions:
            print("\n--- actions ---")
            for a in rep.actions:
                print(" ", a)
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
