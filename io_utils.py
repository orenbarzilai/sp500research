import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

DEFAULT_USER_AGENT = "sp500research/1.0 (contact: data-team@example.com)"


@dataclass
class RateLimiter:
    min_interval: float = 0.2
    last_call: float = 0.0

    def wait(self) -> None:
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


class CacheManager:
    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._key_to_path(key)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def set_json(self, key: str, payload: Dict[str, Any]) -> None:
        path = self._key_to_path(key)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)


class HttpClient:
    def __init__(self, cache: CacheManager, rate_limiter: RateLimiter) -> None:
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def get_json(self, url: str, cache_key: Optional[str] = None, retries: int = 3) -> Dict[str, Any]:
        key = cache_key or url
        cached = self.cache.get_json(key)
        if cached is not None:
            return cached
        for attempt in range(retries):
            self.rate_limiter.wait()
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                payload = response.json()
                self.cache.set_json(key, payload)
                return payload
            except requests.RequestException as exc:
                logging.warning("HTTP error on %s attempt %s: %s", url, attempt + 1, exc)
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError(f"Failed to fetch {url}")


def ensure_dir(path: str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}
