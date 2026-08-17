# -*- coding: utf-8 -*-
"""holon/embedder.py — Embedder + kodowanie czasowe

Backend: pakiet ``kurz`` jeśli jest. Inaczej signed feature-hash
(ten sam tekst → ten sam wektor). Nie ``randn``.
"""

import hashlib
import math
import os
import re
import time
from typing import Optional

import numpy as np

# ── Epoch ──────────────────────────────────────────────────────────────────
_HOLON_EPOCH: float = float(os.environ.get("HOLON_EPOCH", str(time.time())))


def time_embed(timestamp: float, time_dim: int = 8) -> np.ndarray:
    if time_dim <= 0:
        return np.zeros(0, dtype=np.float32)
    delta_days = (timestamp - _HOLON_EPOCH) / 86400.0
    vec = np.zeros(time_dim, dtype=np.float32)
    n_sincos = (time_dim - 1) // 2
    scales   = [1.0 / 24.0, 1.0, 7.0, 30.0, 365.0][:n_sincos]
    for i, scale in enumerate(scales):
        angle = 2.0 * math.pi * delta_days / (scale + 1e-8)
        vec[i * 2]     = math.sin(angle)
        vec[i * 2 + 1] = math.cos(angle)
    vec[-1] = float(np.clip(delta_days / 365.0, -10.0, 10.0))
    return vec


# ── KuRz / hash fallback ──────────────────────────────────────────────────
KURZ_IS_FALLBACK = False
try:
    from kurz import KuRz as _KuRz
except ImportError:
    KURZ_IS_FALLBACK = True

    _TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9_./-]{2,}")

    class _KuRz:
        """Signed feature-hash (256D). Deterministyczny; nie jest 15D KuRzem z archiwum."""

        def __init__(self, dim=256, dict_path=None):
            self.dim = int(dim)
            self.dict_path = dict_path
            self.vocab_size = 10000
            self.calls = 0

        def encode(self, text):
            self.calls += 1
            raw = (text or "").lower()
            vec = np.zeros(self.dim, dtype=np.float32)
            feats = _TOKEN_RE.findall(raw)
            compact = re.sub(r"\s+", " ", raw).strip()
            for n in (3, 4):
                if len(compact) >= n:
                    feats.extend(
                        compact[i : i + n] for i in range(len(compact) - n + 1)
                    )
            if not feats:
                feats = ["_empty"]
            dim = self.dim
            for f in feats:
                digest = hashlib.blake2b(
                    f.encode("utf-8"), digest_size=8
                ).digest()
                idx = int.from_bytes(digest[:4], "little") % dim
                sign = 1.0 if (digest[4] & 1) else -1.0
                vec[idx] += sign
            nrm = float(np.linalg.norm(vec)) + 1e-8
            return (vec / nrm).astype(np.float32)

        def save_dict(self):
            return None


# ── Embedder ───────────────────────────────────────────────────────────────
class Embedder:
    """KuRz jeśli jest; inaczej signed feature-hash. Ten sam tekst → ten sam content-wektor."""

    def __init__(self, dim: int = 256,
                 dict_path: Optional[str] = None,
                 cache_size: int = 256,
                 time_dim: int = 8):
        self.dim         = dim
        self.time_dim    = time_dim
        self._kurz       = _KuRz(dim=dim, dict_path=dict_path)
        self._cache: dict = {}
        self._cache_size  = cache_size
        self._cache_hits  = 0
        self.backend = "kurz" if not KURZ_IS_FALLBACK else "hash"

    def _content_vec(self, text: str) -> np.ndarray:
        key = (text or "")[:200]
        hit = self._cache.get(key)
        if hit is not None:
            self._cache_hits += 1
            return hit
        vec = self._kurz.encode(text or "")
        self._cache[key] = vec
        if len(self._cache) > self._cache_size:
            del self._cache[next(iter(self._cache))]
        return vec

    def encode(self, text: str, timestamp: float = None) -> np.ndarray:
        content = self._content_vec(text)
        if timestamp is None:
            return content
        t_vec = time_embed(timestamp, self.time_dim)
        full = np.concatenate([content * 0.7, t_vec * 0.3])
        n = float(np.linalg.norm(full)) + 1e-8
        return (full / n).astype(np.float32)

    def encode_timed(self, text: str) -> np.ndarray:
        return self.encode(text, timestamp=time.time())

    def save(self) -> None:
        if self._kurz.dict_path:
            self._kurz.save_dict()

    @property
    def vocab_size(self) -> int:
        return self._kurz.vocab_size


def embed_for_item(holomem, text: str) -> list:
    """Wektor do Item w store — prawdziwy encode, nie zera."""
    enc = getattr(holomem, "embedder", None)
    if enc is not None:
        return enc.encode(text or "", timestamp=time.time()).tolist()
    dim = int(getattr(getattr(holomem, "cfg", None), "total_dim", 264) or 264)
    return [0.0] * dim
