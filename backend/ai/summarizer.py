# backend/ai/summarizer.py

import subprocess
import textwrap

def summarize_event(event):
    """
    event is a SQLAlchemy Event instance.
    """
    prefix = textwrap.dedent("""\
        You're an AI created to log cyber attacks. The following attack
        may be a social engineering post, or may directly describe an attack.
        Describe the attack in a general sense, within a single sentence of less than 25 words.
        Sentence format: "A <attack> attack on <location/company> <description>".
        Attack:
    """)
    if event.source == "OTX":
        detail = (
            f"Attack Name: {event.otx_name or ''}\n"
            f"Attack Description: {event.otx_description or ''}"
        )
    elif event.source == "AbuseIPDB":
        detail = (
            f"Attacker's Country: {event.abuse_attacker_country or ''}\n"
            f"Victim's Country: {event.abuse_victim_country or ''}\n"
            f"Attack Description: {event.abuse_attack or ''}"
        )
    else:
        raise ValueError(f"Unknown event source: {event.source!r}")

    prompt = f"{prefix}\n{detail}\n"
    result = subprocess.run(
        ["ollama", "run", "mistral"],
        input=prompt.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.decode("utf-8").strip()



def create_arc_json(event):
    prompt = f"""
        Create a JSON response with the following format:

        IP: {event['ip']}
        Type: {event['type']}
        Location: {event['geo']}
        Time: {event['timestamp']}
        Details: {event['details']}
        """
    result = subprocess.run(
        ['ollama', 'run', 'mistral'],
        input=prompt.encode(),
        stdout=subprocess.PIPE
    )
    return result.stdout.decode()