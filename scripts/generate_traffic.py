import sys
import time
import random
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

ENDPOINTS = [
    ("/health", "GET", None, None),
    ("/users", "GET", None, None),
    ("/products", "GET", None, None),
    ("/secure-data", "GET", {"Authorization": "Bearer sentinel-secure-token-2026"}, None),
    ("/simulate-error?error_kind=math", "GET", None, None),
    ("/simulate-rate-limit?force_breach=true", "GET", None, None),
    ("/secure-data", "GET", {"Authorization": "Bearer bad-token"}, None),
]

# Weighted endpoint probability
WEIGHTS = [0.35, 0.30, 0.25, 0.05, 0.02, 0.02, 0.01]

def run_traffic_loop(rounds: int = 50, delay_between_requests: float = 0.2):
    print(f"🚀 Starting organic traffic generation ({rounds} requests) targeting {BASE_URL}...")
    client = httpx.Client(base_url=BASE_URL, timeout=5.0)

    for i in range(1, rounds + 1):
        chosen = random.choices(ENDPOINTS, weights=WEIGHTS, k=1)[0]
        path, method, headers, params = chosen
        
        try:
            r = client.request(method, path, headers=headers, params=params)
            status_symbol = "✅" if r.status_code < 400 else "⚠️" if r.status_code < 500 else "🚨"
            print(f"[{i}/{rounds}] {status_symbol} {method} {path} -> HTTP {r.status_code} ({r.headers.get('X-Response-Time-Ms', '0')} ms)")
        except Exception as e:
            print(f"[{i}/{rounds}] ❌ Connection error on {path}: {e}")

        time.sleep(delay_between_requests)

    print("🏁 Traffic burst completed.")

if __name__ == "__main__":
    run_traffic_loop(rounds=60, delay_between_requests=0.15)
