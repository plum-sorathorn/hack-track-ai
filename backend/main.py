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

latest_events = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global latest_events
    async def fetch_loop():
        while True:
            otx_events = await get_pulse_events()
            abuse_events = {}
            latest_events.append([otx_events] + [abuse_events])
            print(f"[INFO] cache updated")
            await asyncio.sleep(60)

    task = asyncio.create_task(fetch_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("[INFO] Fetch task cancelled")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "ThreatEchoAI API Running"}

@app.post("/summarize/")
def get_summary(event: dict):
    summary = summarize_event(event)
    return {"summary": summary}

@app.get("/otx/raw")
async def otx_raw():
    pulses = await get_pulse_events()
    return pulses

@app.get("/events")
def get_all_events():
    return {"count": len(latest_events), "events": latest_events}
