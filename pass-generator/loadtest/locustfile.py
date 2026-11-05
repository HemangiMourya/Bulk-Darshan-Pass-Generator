"""
locustfile.py – Locust load test for MandirMitra Pass Generator

Traffic mix:
  70 % – unique /load requests  (heavy CPU, no cache benefit)
  30 % – repeated /generate     (tests Redis cache hit path)

NOTE: Runs should be capped at 5 minutes maximum to stay within Azure lab budgets.
      Use the Locust web UI or CLI flag --run-time 5m to enforce this.

Usage:
  locust -f locustfile.py --host http://<EXTERNAL_IP> --run-time 5m --headless -u 20 -r 5
"""

import random
from locust import HttpUser, task, between


# Fixed pool of devotee names to test the Redis cache hit path
CACHED_DEVOTEES = [
    "Hemangi Mourya", "Aarav Sharma", "Naman Patel",
    "Priya Verma", "Divya Gupta", "Varun Joshi",
]


class PassUser(HttpUser):
    """Simulates devotees requesting darshan passes."""

    # Wait 0.5-1.5 seconds between tasks
    wait_time = between(0.5, 1.5)

    @task(7)
    def load_unique(self):
        """70 % of traffic: unique bulk pass generation (CPU-intensive)."""
        n = random.choice([50, 100, 150, 200])
        self.client.get(f"/load?n={n}&unique=1", name="/load")

    @task(3)
    def generate_cached(self):
        """30 % of traffic: single darshan pass (tests Redis cache hit path)."""
        name = random.choice(CACHED_DEVOTEES)
        self.client.post(
            "/generate",
            data={
                "name": name,
                "darshan_type": "Sheeghra Darshan (VIP)",
                "slot": "07:30 AM - 09:30 AM (Morning Slot)",
                "date": "2026-11-05",
            },
            name="/generate",
        )
