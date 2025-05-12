from fastapi import FastAPI, Depends
from sqlalchemy import asc
from backend.utils.ingestor import lifespan
from dotenv import load_dotenv
from backend.db.session import get_db
from backend.db.models import Event
from sqlalchemy.future import select
from backend.ingest.otx import get_pulse_events

load_dotenv()

app = FastAPI(lifespan=lifespan)

# START OF MAIN SERVER FUNCTIONS

@app.get("/")
def read_root():
    return {"message": "ThreatEchoAI API Running"}

@app.get("/events")
async def get_events(db=Depends(get_db)):
    result = await db.execute(select(Event).order_by(asc(Event.timestamp)).limit(50))
    events = result.scalars().all()
    return [e.__dict__ for e in events]
    
# END OF MAIN SERVER FUNCTIONS