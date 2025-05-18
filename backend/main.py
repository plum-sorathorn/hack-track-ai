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
from backend.ai.summarizer import summarize_event

load_dotenv()

log_queue: deque[str] = deque(maxlen=500)

# START OF HELPER FUNCTIONS 

# function to continuously summarize and log events
async def summarise_and_log_batch(db):
    events = (await db.execute(select(Event).order_by(asc(Event.timestamp)).limit(50))).scalars().all()
    if not events:
        return

    sem = asyncio.Semaphore(10)

    async def _wrapped(event):
        async with sem:
            return await summarize_event(event)

    summaries = await asyncio.gather(*[asyncio.create_task(_wrapped(event)) for event in events], return_exceptions=True)

    ids_to_delete = []
    for event, summary in zip(events, summaries):
        if isinstance(summary, Exception):
            print(f"[ERROR] summarising event {event.id}:\n{''.join(traceback.format_exception(summary))}")
            continue
        log_queue.append(summary)
        ids_to_delete.append(event.id)

    if ids_to_delete:
        await db.execute(delete(Event).where(Event.id.in_(ids_to_delete)))
        await db.commit()
        print("[INFO] summarised events deleted")

async def summariser_loop(interval: int = 10):
    while True:
        try:
            async for db in get_db():
                await summarise_and_log_batch(db)
        except Exception as exc:
            print(f"[ERROR] summariser loop: {exc}")
        await asyncio.sleep(interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[INFO] initialising DB …")
    await init_db()

    tasks = [
        asyncio.create_task(fetch_otx_loop()),
        # asyncio.create_task(fetch_abuseipdb_loop()),
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
    output = [log_queue.popleft() for _ in range(min(50, len(log_queue)))]
    return {"logs": output}

# END OF API ENDPOINTS