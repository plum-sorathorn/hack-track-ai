import asyncio
from backend.db.session import get_db
from backend.db.models import Event
from backend.ingest.otx import get_pulse_events
from backend.ingest.abuseipdb import get_abuseipdb_events
from sqlalchemy import select, delete, asc


# helper function to delete old entries in database if it goes over limit
MAX_EVENTS = 1000

async def trim_event_table(db, max_events=MAX_EVENTS):
    result = await db.execute(select(Event.id).order_by(asc(Event.timestamp)))
    all_ids = [row[0] for row in result.fetchall()]
    
    if len(all_ids) > max_events:
        ids_to_delete = all_ids[:len(all_ids) - max_events]
        await db.execute(delete(Event).where(Event.id.in_(ids_to_delete)))
        await db.commit()

# START OF FUNCTIONS TO CONTINUOUSLY FETCH FROM OTX AND ABUSEIPDB

async def fetch_otx_loop():
    while True:
        print("[INFO] FETCHING OTX EVENTS")
        otx_events = await get_pulse_events()
        print("[INFO] FETCHED OTX EVENTS")
        async for db in get_db():
            for e in otx_events:
                exists = await db.execute(
                    select(Event).where(
                        Event.source == e["source"],
                        Event.timestamp == e["timestamp"]
                    )
                )
                if not exists.scalar():
                    db.add(Event(**e))
            await db.commit()
            print("[INFO] OTX EVENTS COMMITTED")
            await trim_event_table(db)
        await asyncio.sleep(1800)  # 30 mins = 1800 seconds (may make this more frequent)

async def fetch_abuseipdb_loop():
    while True:
        print("[INFO] FETCHING AbuseIPDB EVENTS")
        abuse_events = await get_abuseipdb_events()
        print("[INFO] FETCHED AbuseIPDB EVENTS")
        async for db in get_db():
            for e in abuse_events:
                exists = await db.execute(
                    select(Event).where(
                        Event.source == e["source"],
                        Event.timestamp == e["timestamp"]
                    )
                )
                if not exists.scalar():
                    db.add(Event(**e))
            await db.commit()
            print("[INFO] AbuseIPDB EVENTS COMMITTED")
            await trim_event_table(db)
        await asyncio.sleep(21600)  # 6 hours = 21600 seconds (can only call 5 times a day due to free tier)

# END OF CONTINUOUS FUNCTIONS