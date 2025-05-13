# connections
from fastapi import FastAPI, Depends

# database
from sqlalchemy import asc, delete
from backend.db.session import get_db
from backend.db.models import Event
from sqlalchemy.future import select

# helper functions
from backend.utils.ingestor import lifespan
from backend.ai.summarizer import summarize_event

# etc
from collections import deque
import asyncio

# env variables
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(lifespan=lifespan)

log_queue = deque()

# START OF MAIN SERVER FUNCTIONS

@app.get("/")
def read_root():
    return {"message": "ThreatEchoAI API Running"}

@app.get("/events")
async def get_events(db=Depends(get_db)):
    result = await db.execute(select(Event).order_by(asc(Event.timestamp)).limit(50))
    events = result.scalars().all()
    return [e.__dict__ for e in events]

async def summarize_and_log_events(db):
    # fetch up to 10 oldest events
    result = await db.execute(
        select(Event).order_by(asc(Event.timestamp)).limit(10)
    )
    events = result.scalars().all()
    if not events:
        return

    # spin up one background task per event
    tasks = [
        asyncio.create_task(
            asyncio.to_thread(summarize_event, event)
        )
        for event in events
    ]

    # wait for them all to finish (you can catch errors if you like)
    summaries = await asyncio.gather(*tasks, return_exceptions=True)

    # collect successes and IDs to delete
    ids_to_delete = []
    for event, summary in zip(events, summaries):
        if isinstance(summary, Exception):
            # you might log this, or re-raise—up to you
            continue
        log_queue.append(summary)
        ids_to_delete.append(event.id)

    # delete all the summarized events in one statement
    if ids_to_delete:
        await db.execute(delete(Event).where(Event.id.in_(ids_to_delete)))
        await db.commit()


@app.get("/logs")
async def display_logs(db=Depends(get_db)):
    if not log_queue:
        await summarize_and_log_events(db)

    output = []
    for _ in range(15):
        if not log_queue:
            break
        output.append(log_queue.popleft())

    return {"logs": output}

# END OF MAIN SERVER FUNCTIONS