import os, httpx, asyncio
from datetime import datetime

ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY")
ABUSE_URL = "https://api.abuseipdb.com/api/v2/blacklist"
CHECK_URL = "https://api.abuseipdb.com/api/v2/check"
HEADERS = {
    "Key": ABUSEIPDB_API_KEY,
    "Accept": "application/json"
}

async def get_abuseipdb_events(confidence_min=90):
    params = {"confidenceMinimum": confidence_min}
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
            resp = await client.get(ABUSE_URL, params=params)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            ips = [item["ipAddress"] for item in data]
            return await check_events(ips)
    except httpx.HTTPError as e:
        print(f"[ERROR] AbuseIPDB blacklist fetch failed: {e}")
        return []

async def check_events(ips: list[str]):
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        tasks = [fetch_report(client, ips[ip]) for ip in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    flat = []
    for res in results:
        if isinstance(res, Exception):
            continue
        flat.extend(res)
    return flat

async def fetch_report(client: httpx.AsyncClient, ip: str):
    params = {"ipAddress": ip, "maxAgeInDays": 1, "verbose": "true"}
    try:
        resp = await client.get(CHECK_URL, params=params)
        resp.raise_for_status()
        data = resp.json()["data"]
        # only fetch up to 5 reports for each IP (for now)
        reports = data.get("reports", [])[:5]
        out = []
        for rpt in reports:
            out.append({
                "source": "AbuseIPDB",
                "timestamp": datetime.fromisoformat(data["lastReportedAt"]).isoformat(),
                "abuse_attacker_country": data.get("countryName"),
                "abuse_victim_country": rpt.get("reporterCountryName"),
                "abuse_attack": rpt.get("comment"),
                "otx_name": None,
                "otx_description": None,
            })
        return out
    except httpx.HTTPError as e:
        print(f"[ERROR] Failed to fetch AbuseIPDB report for {ip}: {e}")
        return []
