import os, httpx, asyncio
from datetime import datetime, timedelta, timezone

OTX_API_KEY = os.getenv("OTX_API_KEY")
BASE        = "https://otx.alienvault.com/api/v1"
HDRS        = {"X-OTX-API-KEY": OTX_API_KEY}

async def get_pulse_events(minutes: int = 30):
    print("hi")
    now   = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=minutes)).isoformat()
    async with httpx.AsyncClient(base_url=BASE, headers=HDRS, timeout=10.0) as client:
        list_resp = await client.get("/pulses/events",params={"modified_since": since, "limit": 100},)
        list_resp.raise_for_status()
        results = list_resp.json().get("results", [])

        pulses = []
        for entry in results:
            if entry.get("object_type") != "pulse":
                print("not pulse")
                continue

            if entry.get("action") == "deleted":
                print(f"[INFO] Pulse {entry['object_id']} was deleted, skipping")
                continue

            pid = entry.get("object_id")
            if not pid:
                print("no id")
                continue

            try:
                detail = await client.get(f"/pulses/{pid}")
                detail.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    print(f"[WARN] Pulse {pid} not found, skipping")
                    continue
                raise

            pulses.append(detail.json())
        
        print(len(pulses))
        return pulses

# test harness
async def main():
    pulses = await get_pulse_events(1)
    print(f"Retrieved {len(pulses)} pulses:")
    for p in pulses:
        print(" →", p.get("name"))

if __name__ == "__main__":
    asyncio.run(main())
