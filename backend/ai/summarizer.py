import subprocess
import textwrap

def summarize_event(event):
    prefix = textwrap.dedent("""\
        You're an AI created to log cyber attacks. The following attack
        may be a social engineering post, or may directly describe an attack.
        Describe the attack in a general sense, within a sentence of less than 25 words.
        Sentence format: "A <attack> attack on <location/company> <description>".
        Attack:
    """)
    src = event.get("source")
    if src == "OTX":
        detail = f"Attack Name: {event.get('otx_name', '')}\nAttack Description: {event.get('otx_description', '')}"
    elif src == "AbuseIPDB":
        detail = (
            f"Attacker's Country: {event.get('abuse_attacker_country', '')}\n"
            f"Victim's Country: {event.get('abuse_victim_country', '')}\n"
            f"Attack Description: {event.get('abuse_attack', '')}"
        )
    else:
        raise ValueError(f"Unknown event source: {src!r}")

    prompt = f"{prefix}\n{detail}\n"
    result = subprocess.run(
        ["ollama", "run", "mistral"],
        input=prompt.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.decode().strip()


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