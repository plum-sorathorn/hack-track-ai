# main script to process otx pulses (info about cyberattacks)
# then use mistral to translate them into simple English

import asyncio
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from backend.ai.summarizer import summarize_event
from backend.ingest.otx import get_pulse_events
from backend.ingest.abuseipdb import get_abuseipdb_events
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone

load_dotenv()

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "ThreatEchoAI API Running"}

@app.post("/summarize/")
def get_summary(event: dict):
    summary = summarize_event(event)
    return {"summary": summary}

# background task to continuously fetch pulses from otx
@asynccontextmanager
async def lifespan():
    async def fetch_loop():
        while True:
            now = datetime.now(timezone.utc)
            print(f"\n[FETCH] {now.isoformat()}")
            otx_pulses = await get_pulse_events()
            abuse_events = await get_abuseipdb_events()

            all_events = extract_pulse_content(otx_pulses) + abuse_events
            print(f"[INFO] Pulled {len(otx_pulses)} OTX pulses and {len(abuse_events)} AbuseIPDB events")
            for event in all_events[:5]:
                print(f" - {event['ip']} from {event['source']}")
            await asyncio.sleep(5)

    task = asyncio.create_task(fetch_loop())

    yield  
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("[INFO] Fetch task cancelled")

# START OF INGESTION API FUNCTIONS
@app.get("/events")
async def get_all_events():
    otx = await get_pulse_events()
    abuse = await get_abuseipdb_events()
    events = extract_pulse_content(otx) + abuse
    return {"count": len(events), "events": events}

@app.get("/otx/raw")
async def otx_raw():
    pulses = await get_pulse_events()
    for i, pulse in enumerate(pulses[:5]):
        print(f"\n[{i+1}] Pulse name: {pulse.get('name')}")
        print(f"    Modified: {pulse.get('modified')}")
        print(f"    Tags: {pulse.get('tags')}")
        print(f"    Indicators: {len(pulse.get('indicators', []))}")
    
    return pulses

@app.get("/events")
async def get_all_events():
    otx_task = get_pulse_events()
    abuse_task = get_abuseipdb_events()
    
    otx, abuse = await asyncio.gather(otx_task, abuse_task)
    events = extract_pulse_content(otx) + abuse
    return {"count": len(events), "events": events}


def extract_pulse_content(pulses):
    events = []
    for pulse in pulses:
        for indicator in pulse.get("indicators", []):
            if indicator.get("type") == "IPv4":
                events.append({
                    "ip": indicator["indicator"],
                    "type": indicator["indicator_type"],
                    "source": pulse["name"],
                    "timestamp": pulse["modified"],
                    "geo": None  # Add geolocation later
                })
    return events