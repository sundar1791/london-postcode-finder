import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Callable, Optional


class RateLimiter:
    """In-memory per-IP hourly limit plus a global daily cap.

    The daily counter is seeded from the database on the first request of each
    UTC day, so a redeploy mid-day doesn't reset the spend guard to zero.
    """

    def __init__(
        self,
        per_hour: int,
        daily_cap: int,
        seed_daily_count: Optional[Callable[[], int]] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.per_hour = per_hour
        self.daily_cap = daily_cap
        self._seed = seed_daily_count
        self._clock = clock
        self._hits = defaultdict(deque)
        self._day: Optional[str] = None
        self._day_count = 0
        self._lock = threading.Lock()

    def _today(self) -> str:
        return datetime.fromtimestamp(self._clock(), tz=timezone.utc).strftime("%Y-%m-%d")

    def check_and_record(self, ip: str) -> Optional[dict]:
        """Return None if allowed (and record the hit), else a 429 payload."""
        with self._lock:
            now = self._clock()
            today = self._today()
            if self._day != today:
                self._day = today
                self._day_count = 0
                if self._seed:
                    try:
                        self._day_count = int(self._seed())
                    except Exception:
                        pass

            if self._day_count >= self.daily_cap:
                return {
                    "error": "daily_cap",
                    "message": "We've hit today's search limit, which keeps this free demo affordable. "
                               "Watch a recorded example run, or try again tomorrow.",
                    "retry_after": 3600,
                }

            hits = self._hits[ip]
            while hits and now - hits[0] > 3600:
                hits.popleft()
            if len(hits) >= self.per_hour:
                retry_after = int(3600 - (now - hits[0])) + 1
                return {
                    "error": "rate_limited",
                    "message": f"You've run {self.per_hour} searches in the last hour. "
                               f"Try again in about {max(1, retry_after // 60)} minutes, or watch a recorded example run.",
                    "retry_after": retry_after,
                }

            hits.append(now)
            self._day_count += 1
            return None
