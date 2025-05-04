# backend/ingest/abuseipdb.py

import os
import httpx
from datetime import datetime

ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY")
if not ABUSEIPDB_API_KEY:
    raise RuntimeError("ABUSEIPDB_API_KEY environment variable is required")

ABUSE_URL = "https://api.abuseipdb.com/api/v2/blacklist"

async def get_abuseipdb_events(confidence_min=90):
    headers = {
        "Key": ABUSEIPDB_API_KEY,
        "Accept": "application/json"
    }
    params = {
        "confidenceMinimum": confidence_min
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(ABUSE_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        now = datetime.now()

        events = []
        for item in data.get("data", []):
            events.append({
                "ip": item["ipAddress"],
                "type": "IPv4",
                "source": "AbuseIPDB",
                "timestamp": now.isoformat(),
                "geo": None  # optional geolocation data
            })
        return events