import os
import httpx
import asyncio
from datetime import datetime

ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY")
if not ABUSEIPDB_API_KEY:
    raise RuntimeError("ABUSEIPDB_API_KEY environment variable is required")

ABUSE_URL = "https://api.abuseipdb.com/api/v2/blacklist"


headers = {
    "Key": ABUSEIPDB_API_KEY,
    "Accept": "application/json"
}

# function to obtain suspicious IPs
async def get_abuseipdb_events(confidence_min=90):
    params = {
        "confidenceMinimum": confidence_min
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(ABUSE_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        now = datetime.now()

        eventsIP = []
        for item in data.get("data", []):
            eventsIP.append({
                "ip": item["ipAddress"],
            })
        
        events = await check_events(eventsIP)
        return events
    
# function to scan for reports on each IP concurrently using AbuseIPDB /check endpoint
async def check_events(eventsIP):
    headers = {
        "Key": ABUSEIPDB_API_KEY,
        "Accept": "application/json"
    }

    async def fetch_report(ip):
        url = "https://api.abuseipdb.com/api/v2/check"
        params = {
            "ipAddress": ip,
            "maxAgeInDays": 1,
            "verbose": "true"
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                result = resp.json()["data"]
                return {
                    "ip": result["ipAddress"],
                    "type": f"IPv{result.get('ipVersion', 4)}",
                    "source": "AbuseIPDB",
                    "timestamp": result.get("lastReportedAt"),
                    "geo": {
                        "countryCode": result.get("countryCode"),
                        "countryName": result.get("countryName"),
                        "usageType": result.get("usageType"),
                        "isp": result.get("isp"),
                        "domain": result.get("domain"),
                        "isTor": result.get("isTor"),
                    },
                    "confidenceScore": result.get("abuseConfidenceScore"),
                    "totalReports": result.get("totalReports"),
                    "distinctUsers": result.get("numDistinctUsers"),
                    "reports": result.get("reports", [])
                }
            except httpx.HTTPError as e:
                print(f"[ERROR] Failed to fetch report for {ip}: {e}")
                return None

    tasks = [fetch_report(i["ip"]) for i in eventsIP]
    results = await asyncio.gather(*tasks)
    return [event for event in results if event]


