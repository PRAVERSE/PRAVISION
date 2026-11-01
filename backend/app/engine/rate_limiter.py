import asyncio
import time
from typing import Dict

class RateLimiter:
    """Sliding-window rate limiter per connector to avoid network bans and quota abuse."""

    def __init__(self, requests_per_minute: int = 30):
        self.rpm = requests_per_minute
        self._history: Dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, connector_name: str):
        async with self._lock:
            now = time.time()
            window_start = now - 60.0
            timestamps = self._history.setdefault(connector_name, [])
            # Filter old timestamps
            self._history[connector_name] = [t for t in timestamps if t > window_start]

            if len(self._history[connector_name]) >= self.rpm:
                sleep_time = 60.0 - (now - self._history[connector_name][0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            self._history[connector_name].append(time.time())

rate_limiter = RateLimiter()
