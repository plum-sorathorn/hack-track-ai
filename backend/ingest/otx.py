import os
import asyncio
from math import ceil

import httpx

OTX_API_KEY = os.getenv("OTX_API_KEY")
if not OTX_API_KEY:
    raise RuntimeError("OTX_API_KEY environment variable is required")

BASE = "https://otx.alienvault.com/api/v1"
PAGE_SIZE = 50
MAX_PAGES = 1

async def fetch_page(client: httpx.AsyncClient, page: int):
    params = {
        "limit": PAGE_SIZE,
        "page": page,
        "sort": "-modified",
        "q": "",
    }
    url = f"{BASE}/search/pulses"
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data["results"], data["count"]

async def get_pulse_events():
    headers = {"X-OTX-API-KEY": OTX_API_KEY}
    
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            first_page_results, total_count = await fetch_page(client, page=1)

            total_pages = ceil(total_count / PAGE_SIZE)
            pages_to_fetch = min(total_pages, MAX_PAGES)

            if pages_to_fetch <= 1:
                return first_page_results

            tasks = [
                fetch_page(client, page=p)
                for p in range(2, pages_to_fetch + 1)
            ]
            results = await asyncio.gather(*tasks)

            # stitch all results together
            all_pulses = first_page_results + [
                item
                for (page_results, _) in results
                for item in page_results
            ]
            return all_pulses
    except:
        print("Timed-out")