import os
import httpx
from datetime import datetime
import asyncio
from collections import Counter

ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY")
if not ABUSEIPDB_API_KEY:
    raise RuntimeError("ABUSEIPDB_API_KEY environment variable is required")

BLACKLIST_URL = "https://api.abuseipdb.com/api/v2/blacklist"
CHECK_URL = "https://api.abuseipdb.com/api/v2/check"

CATEGORY_MAP = {
    3: "Fraud Orders", 4: "DDoS Attack", 5: "FTP Brute-Force",
    6: "Ping of Death", 7: "Phishing", 8: "Fraud VoIP",
    9: "Open Proxy", 10: "Web Spam", 11: "Email Spam",
    12: "Blog Spam", 13: "VPN IP", 14: "Port Scan",
    15: "Hacking", 16: "SQL Injection", 17: "Spoofing",
    18: "Brute Force", 19: "Bad Web Bot", 20: "Exploited Host",
    21: "Web App Attack", 22: "SSH Brute-Force", 23: "IoT Targeting"
}

HEADERS = {
    "Key": ABUSEIPDB_API_KEY,
    "Accept": "application/json"
}

def extract_attack_types(reports):
    categories = []
    for report in reports:
        for code in report.get("categories", []):
            categories.append(CATEGORY_MAP.get(code, f"Unknown({code})"))
    return dict(Counter(categories))

def extract_report_origins(reports):
    countries = [r.get("reporterCountryCode") for r in reports if r.get("reporterCountryCode")]
    return dict(Counter(countries))


async def fetch_blacklist(confidence_min=90):
    params = {"confidenceMinimum": confidence_min}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(BLACKLIST_URL, headers=HEADERS, params=params)
        resp.raise_for_status()
        return [item["ipAddress"] for item in resp.json().get("data", [])]

async def fetch_check_info(client: httpx.AsyncClient, ip: str):
    params = {
        "ipAddress": ip,
        "maxAgeInDays": 90,
        "verbose": True
    }
    try:
        resp = await client.get(CHECK_URL, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        reports = data.get("reports", [])

        return {
            "ip": ip,
            "type": "IPv4",
            "source": "AbuseIPDB",
            "timestamp": datetime.utcnow().isoformat(),
            "geo": {
                "country": data.get("countryCode"),
                "usageType": data.get("usageType"),
                "domain": data.get("domain"),
                "isp": data.get("isp")
            },
            "abuse_confidence_score": data.get("abuseConfidenceScore"),
            "total_reports": data.get("totalReports"),
            "last_reported_at": data.get("lastReportedAt"),
            "attack_types": extract_attack_types(reports),
            "report_sources": extract_report_origins(reports)
        }
    except httpx.HTTPError as e:
        print(f"[ERROR] Could not fetch check info for {ip}: {e}")
        return None

async def get_abuseipdb_events(confidence_min=90):
    ips = await fetch_blacklist(confidence_min)
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [fetch_check_info(client, ip) for ip in ips]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
