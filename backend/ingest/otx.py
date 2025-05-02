import os
import asyncio
from math import ceil
from datetime import datetime, timedelta, timezone

import httpx

OTX_API_KEY = os.getenv("OTX_API_KEY")
BASE = "https://otx.alienvault.com/api/v1"
PAGE_SIZE = 50  # max per page

async def fetch_page(client: httpx.AsyncClient, since: str, page: int):
    params = {
        "limit": PAGE_SIZE,
        "modified_since": since,
        "page": page
    }
    resp = await client.get(f"{BASE}/pulses/subscribed", params=params)
    resp.raise_for_status()
    data = resp.json()
    return data["results"], data.get("count", 0)

async def get_pulse_events(minutes: int = 30):
    """
    Pull all subscribed pulses from the past `minutes` minutes,
    fetching pages in parallel.
    """
    headers = {"X-OTX-API-KEY": OTX_API_KEY}
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=minutes)).isoformat()

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # 1) Fetch page 1 to get total count
        first_page, total_count = await fetch_page(client, since, page=1)

        # 2) Compute how many additional pages we need
        total_pages = ceil(total_count / PAGE_SIZE)
        if total_pages <= 1:
            return first_page

        # 3) Kick off the rest of the pages in parallel
        tasks = [
            fetch_page(client, since, page=p)
            for p in range(2, total_pages + 1)
        ]
        results = await asyncio.gather(*tasks)

        # 4) Flatten all pages’ "results"
        all_pulses = first_page + [
            item
            for page_results, _ in results
            for item in page_results
        ]
        return all_pulses