import asyncio
from collections import deque
import traceback
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.concurrency import asynccontextmanager
from sqlalchemy import asc, delete
from sqlalchemy.future import select

# database
from backend.db.session import get_db
from backend.db.init import init_db
from backend.db.models import Event
from typing import Dict, Any, Optional, Tuple
from backend.ai.summarizer import SummaryOutput

# background ingest
from backend.utils.ingestor import (
    fetch_otx_loop,
    fetch_abuseipdb_loop,
)

# summarisation
from backend.ai.summarizer import summarize_event, create_arc_json

load_dotenv()

log_and_arc_queue: deque[Tuple[Event, Optional[Dict[str, Any]], SummaryOutput]] = deque(maxlen=500)

from fastapi.middleware.cors import CORSMiddleware

# START OF HELPER FUNCTIONS 

# function to continuously create arcs jsons, summarize, and log events
async def arc_and_log_batch(db):
    print("[INFO] started summarization of events")
    # take 50 database entries
    events = (await db.execute(select(Event).order_by(asc(Event.timestamp)).limit(50))).scalars().all()
    if not events:
        return
    
    # function to create summaries/arcs
    sem = asyncio.Semaphore(10)
    async def _wrapped_summary(event):
        async with sem:
            return await summarize_event(event)

    summaries = await asyncio.gather(*[asyncio.create_task(_wrapped_summary(event)) for event in events], return_exceptions=True)
    
    arcs = []
    
    # We iterate over the results of the summary batch
    for event, summary in zip(events, summaries):
        if isinstance(summary, Exception):
            arcs.append(summary)
            continue

        try:
            # arc will now be a dict like {"arc": {...}, "resolved_names": {...}} or None
            resolved_arc_data = create_arc_json(
                summary['attacker_country'],
                summary['victim_country']
            )
            arcs.append(resolved_arc_data) 
        except Exception as arc_exc:
            arcs.append(arc_exc)

    ids_to_delete = []
    # resolved_arc_data is the full dict output of create_arc_json, or an Exception
    for event, resolved_arc_data, summary in zip(events, arcs, summaries):
        # Handle exceptions from summarization
        if isinstance(summary, Exception):
            print(f"[ERROR] summarising event {event.id}:\n{''.join(traceback.format_exception(summary))}")
            continue # Skip to next event, do not delete

        # Check if arc creation succeeded or failed
        if isinstance(resolved_arc_data, Exception) or resolved_arc_data is None:
            if isinstance(resolved_arc_data, Exception):
                print(f"[ERROR] creating arc for event {event.id}:\n{''.join(traceback.format_exception(resolved_arc_data))}")
            
            arc = None
            # If the arc logic failed, we fall back to the original AI summary for logging
            event.resolved_attacker_country = summary.get('attacker_country')
            event.resolved_victim_country = summary.get('victim_country')
        else:
            # Arc logic succeeded, use the resolved name for logging
            arc = resolved_arc_data['arc']
            resolved_names = resolved_arc_data['resolved_names']

            # Use the RESOLVED country names (original or random fallback) for the log
            event.resolved_attacker_country = resolved_names['attacker_country']
            event.resolved_victim_country = resolved_names['victim_country']

        # log_and_arc_queue is appended with the event, arc (or None), and the summary dictionary
        log_and_arc_queue.append((event, arc, summary))
        ids_to_delete.append(event.id)

    if ids_to_delete:
        await db.execute(delete(Event).where(Event.id.in_(ids_to_delete)))
        await db.commit()
        print("[INFO] summarised events deleted")

async def summariser_loop(interval: int = 30):
    while True:
        try:
            async for db in get_db():
                await arc_and_log_batch(db)
        except Exception as exc:
            print(f"[ERROR] summariser loop: {exc}")
        await asyncio.sleep(interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[INFO] initialising DB …")
    await init_db()

    tasks = [
        # REAL API FETCHING (COMMENTED OUT)
        asyncio.create_task(fetch_otx_loop()),
        asyncio.create_task(fetch_abuseipdb_loop()),
        
        # SIMULATED ATTACK GENERATION
        # asyncio.create_task(simulate_attacks_loop()),
        
        # summarization loop
        asyncio.create_task(summariser_loop()),
    ]

    yield

    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass
    print("[INFO] background tasks shut down")

app = FastAPI(lifespan=lifespan)

# define server endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# END OF HELPER FUNCTIONS

# START OF API ENDPOINTS

@app.get("/")
async def read_root():
    return {"message": "ThreatEchoAI API Running"}

@app.get("/events")
async def get_events(db=Depends(get_db)):
    res = await db.execute(select(Event).order_by(asc(Event.timestamp)).limit(50))
    return [e.__dict__ for e in res.scalars().all()]

@app.get("/logs")
async def get_logs():
    output = []
    # drain 50 entries from queue
    for _ in range(min(50, len(log_and_arc_queue))):
        event, arc, summary = log_and_arc_queue.popleft()
        event_dict = event.__dict__.copy()
        event_dict.pop('_sa_instance_state', None) 
        output.append((event_dict, arc, summary)) 

    return {"logs": output}

# END OF API ENDPOINTS