# main script to process otx pulses (info about cyberattacks)
# then use mistral to translate them into simple English

from fastapi import FastAPI
from ai.summarizer import summarize_event
from ingest.otx import get_recent_pulses 
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "ThreatEchoAI API Running"}

@app.post("/summarize/")
def get_summary(event: dict):
    summary = summarize_event(event)
    return {"summary": summary}

@app.get("/otx")
def read_otx():
    pulses = get_recent_pulses()
    events = extract_pulse_content(pulses)
    return {
        "count": len(pulses),
        "ip": events["ip"],
        "type": events["type"],
        "source": events["source"],
        "timestamp": events["timestamp"],
        "geo": None
    }

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