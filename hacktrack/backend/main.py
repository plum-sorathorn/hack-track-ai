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

# Simulated attack data
ATTACK_TYPES = [
    "SQL Injection",
    "DDoS Attack",
    "Brute Force Login",
    "Port Scan",
    "Malware Distribution",
    "Phishing Campaign",
    "XSS Attack",
    "Ransomware",
    "Cryptojacking",
    "Data Exfiltration"
]

COUNTRIES = [
    "United States", "China", "Russia", "Brazil", "India",
    "Germany", "United Kingdom", "France", "Japan", "South Korea",
    "Canada", "Australia", "Netherlands", "Singapore", "Israel"
]

ATTACK_DESCRIPTIONS = {
    "SQL Injection": [
        "Attempted SQL injection on login form",
        "Database enumeration via UNION-based SQLi",
        "Blind SQL injection targeting user authentication"
    ],
    "DDoS Attack": [
        "UDP flood attack detected",
        "SYN flood overwhelming network resources",
        "HTTP flood targeting web application"
    ],
    "Brute Force Login": [
        "Multiple failed SSH login attempts",
        "Credential stuffing attack on admin panel",
        "Dictionary attack on FTP service"
    ],
    "Port Scan": [
        "Comprehensive port scan detected",
        "Stealth SYN scan activity",
        "Service enumeration attempt"
    ],
    "Malware Distribution": [
        "Trojan payload delivery attempt",
        "Botnet command and control communication",
        "Malicious JavaScript injection"
    ]
}

PROTOCOLS = ["TCP", "UDP", "HTTP", "HTTPS", "SSH", "FTP", "ICMP"]
COMMON_PORTS = [21, 22, 23, 25, 80, 443, 3306, 3389, 5432, 8080]

def generate_random_ip():
    """Generate a random IP address"""
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 255)}"

def generate_simulated_event():
    """Generate a simulated security event"""
    attack_type = random.choice(ATTACK_TYPES)
    source_country = random.choice(COUNTRIES)
    target_country = random.choice(COUNTRIES)
    
    # Ensure source and target are different
    while target_country == source_country:
        target_country = random.choice(COUNTRIES)
    
    # Get description for the attack type, or use generic
    descriptions = ATTACK_DESCRIPTIONS.get(attack_type, ["Suspicious activity detected"])
    description = random.choice(descriptions)
    
    # Randomly choose between AbuseIPDB-style and OTX-style events
    if random.random() < 0.5:
        # AbuseIPDB-style event
        return {
            "source": "AbuseIPDB",
            "timestamp": (datetime.utcnow() - timedelta(minutes=random.randint(0, 60))).isoformat(),
            "abuse_attacker_country": source_country,
            "abuse_victim_country": target_country,
            "abuse_attack": description,
            "otx_name": None,
            "otx_description": None,
            "otx_country": None,
        }
    else:
        # OTX-style event
        return {
            "source": "OTX",
            "timestamp": (datetime.utcnow() - timedelta(minutes=random.randint(0, 60))).isoformat(),
            "abuse_attacker_country": None,
            "abuse_victim_country": None,
            "abuse_attack": None,
            "otx_name": f"{attack_type} Campaign",
            "otx_description": f"{description} targeting {target_country}",
            "otx_country": target_country
        }

async def simulate_attacks_loop(interval: int = 30):
    """Continuously generate simulated attack events"""
    while True:
        try:
            async for db in get_db():
                # Generate 3-8 random events per cycle
                num_events = random.randint(3, 8)
                events_to_add = [generate_simulated_event() for _ in range(num_events)]
                
                # Add events to database
                for event_data in events_to_add:
                    event = Event(**event_data)
                    db.add(event)
                
                await db.commit()
                print(f"[INFO] Generated {num_events} simulated attack events")
                
        except Exception as exc:
            print(f"[ERROR] simulate_attacks_loop: {exc}")
        
        await asyncio.sleep(interval)

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
        # REAL API FETCHING (COMMENTED OUT)
        # asyncio.create_task(fetch_otx_loop()),
        # asyncio.create_task(fetch_abuseipdb_loop()),
        
        # SIMULATED ATTACK GENERATION
        asyncio.create_task(simulate_attacks_loop()),
        
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