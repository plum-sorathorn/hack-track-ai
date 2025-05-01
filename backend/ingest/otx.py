import httpx
import os
from datetime import datetime, timedelta

OTX_API_KEY = os.getenv("OTX_API_KEY")
OTX_BASE_URL = "https://otx.alienvault.com/api/v1"

def get_recent_pulses(days=1):
    """
    Pull pulses (threat reports) from the past `days` days.
    """
    headers = {"X-OTX-API-KEY": OTX_API_KEY}
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    url = f"{OTX_BASE_URL}/pulses/subscribed?limit=50&modified_since={since}"

    try:
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"[ERROR] OTX fetch failed: {e}")
        return []
