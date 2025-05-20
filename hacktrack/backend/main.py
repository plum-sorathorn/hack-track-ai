import asyncio
from collections import deque
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.concurrency import asynccontextmanager
from sqlalchemy import asc, delete
from sqlalchemy.future import select

# database
from backend.db.session import get_db
from backend.db.init import init_db
from backend.db.models import Event

# background ingest
from backend.utils.ingestor import (
    fetch_otx_loop,
    fetch_abuseipdb_loop,
)

# summarisation
from backend.ai.summarizer import summarize_event, create_arc_json

load_dotenv()

log_and_arc_queue: deque[str] = deque(maxlen=500)

from fastapi.middleware.cors import CORSMiddleware

# START OF HELPER FUNCTIONS 

# function to continuously create arcs jsons, summarize, and log events
async def arc_and_log_batch(db):
    # take 50 database entries
    events = (await db.execute(select(Event).order_by(asc(Event.timestamp)).limit(50))).scalars().all()
    if not events:
        return
    
    # function to create summaries/arcs
    sem = asyncio.Semaphore(10)
    async def _wrapped(func, event):
        async with sem:
            return await func(event)

    summaries = await asyncio.gather(*[asyncio.create_task(_wrapped(summarize_event, event)) for event in events], return_exceptions=True)
    
    arcs = []
    for event in events:
        try:
            arc = create_arc_json(event)
            arcs.append(arc)
        except Exception as arc_exc:
            arcs.append(arc_exc)

    ids_to_delete = []
    for event, arc, summary in zip(events, arcs, summaries):
        if isinstance(summary, Exception):
            print(f"[ERROR] summarising event {event.id}:\n{''.join(traceback.format_exception(summary))}")
            continue

        if isinstance(arc, Exception):
            print(f"[ERROR] creating arc for event {event.id}:\n{''.join(traceback.format_exception(arc))}")
            arc = None

        log_and_arc_queue.append((event, arc, summary))
        ids_to_delete.append(event.id)

    if ids_to_delete:
        await db.execute(delete(Event).where(Event.id.in_(ids_to_delete)))
        await db.commit()
        print("[INFO] summarised events deleted")

async def summariser_loop(interval: int = 60):
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
        asyncio.create_task(fetch_otx_loop()),
        asyncio.create_task(fetch_abuseipdb_loop()),
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
    # just drain up to 50 most-recent summaries
    output = [log_and_arc_queue.popleft() for _ in range(min(50, len(log_and_arc_queue)))]

    return {"logs": output}

# END OF API ENDPOINTS