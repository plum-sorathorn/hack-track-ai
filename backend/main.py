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
    return {
        "count": len(pulses),
        "samples": pulses[:3]
    }