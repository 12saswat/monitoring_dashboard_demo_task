import time
from collections import defaultdict
from fastapi import HTTPException


class InMemoryRateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 10):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients = defaultdict(list)

    def remaining(self, client_ip: str) -> int:
        now = time.time()
        self.clients[client_ip] = [t for t in self.clients[client_ip] if now - t < self.window_seconds]
        return max(0, self.max_requests - len(self.clients[client_ip]))

    def force_exceed(self, client_ip: str) -> None:
        now = time.time()
        self.clients[client_ip] = [now] * self.max_requests

    def reset(self, client_ip: str | None = None) -> None:
        if client_ip is None:
            self.clients.clear()
        else:
            self.clients.pop(client_ip, None)

    def check_rate_limit(self, client_ip: str) -> bool:
        now = time.time()
        self.clients[client_ip] = [t for t in self.clients[client_ip] if now - t < self.window_seconds]

        if len(self.clients[client_ip]) >= self.max_requests:
            oldest = self.clients[client_ip][0]
            retry_after = int(self.window_seconds - (now - oldest))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded: 10 requests per 10s quota exhausted.",
                headers={"Retry-After": str(max(1, retry_after))}
            )

        self.clients[client_ip].append(now)
        return True


rate_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=10)
