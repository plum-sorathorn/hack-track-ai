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

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(ABUSE_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            eventsIP = []
            for item in data.get("data", []):
                eventsIP.append({
                    "ip": item["ipAddress"],
                })
            
            events = await check_events(eventsIP)
            return events
    except httpx.HTTPError as e:
        print(f"[ERROR] Failed due to {e}")
        return None
    
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
                    "source": "AbuseIPDB",
                    "timestamp": datetime.fromisoformat(result.get("lastReportedAt")).isoformat(),
                    "abuse_type": f"IPv{result.get('ipVersion', 4)}",
                    "abuse_ip": result["ipAddress"],
                    "abuse_geo": {
                        "countryCode": result.get("countryCode"),
                        "countryName": result.get("countryName"),
                        "usageType": result.get("usageType"),
                        "isp": result.get("isp"),
                        "domain": result.get("domain"),
                        "isTor": result.get("isTor"),
                    },
                    "abuse_confidenceScore": result.get("abuseConfidenceScore"),
                    "abuse_totalReports": result.get("totalReports"),
                    "abuse_distinctUsers": result.get("numDistinctUsers"),
                    "abuse_reports": result.get("reports", [])[:5],
                    "otx_name": None,
                    "otx_description": None,
                }
            except httpx.HTTPError as e:
                print(f"[ERROR] Failed to fetch report for {ip}: {e}")
                return None

    tasks = [fetch_report(eventsIP[i]["ip"]) for i in range(10)]
    results = await asyncio.gather(*tasks)
    return [event for event in results if event]


