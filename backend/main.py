# main script to process otx pulses (info about cyberattacks)
# then use mistral to translate them into simple English

import asyncio
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from backend.ai.summarizer import summarize_event
from backend.ingest.otx import get_pulse_events
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / '.env')

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "ThreatEchoAI API Running"}

@app.post("/summarize/")
def get_summary(event: dict):
    summary = summarize_event(event)
    return {"summary": summary}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background task
    async def fetch_loop():
        while True:
            now = datetime.now(timezone.utc)
            print(f"\n[FETCH] {now.isoformat()}")
            pulses = get_pulse_events()
            print(f"[INFO] Pulled {len(pulses)} pulses")
            for pulse in pulses[:3]:
                print(f" - {pulse.get('name')}")
            await asyncio.sleep(5)

    task = asyncio.create_task(fetch_loop())

    yield  # Let the app start

    # On shutdown (if needed)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("[INFO] Fetch task cancelled")

@app.get("/otx")
def read_otx():
    pulses = get_pulse_events()
    events = extract_pulse_content(pulses)
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