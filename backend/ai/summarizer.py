import asyncio
import textwrap

# helper function to run mistral for summarization
async def summarize_event(event):
    prefix = textwrap.dedent("""\
        ### ROLE
        You are an AI, created to concisely narrate cyber-security incidents.

        ### TASK
        Follow **all** rules below to transform the supplied event details into a single plain-English sentence.

        ### RULES
        1. Output **exactly one** sentence, ≤ 25 words.  
        2. Sentence **must** start with: "A <attack-type> attack on <location/company>"  
            - Replace the angle-bracket placeholders with concrete values.  
        3. After the subject, add a short description (≤ 15 words) of what happened.  
        4. Do **not** mention sources, indicators, IDs, dates, or severity scores.  
        5. Use simple vocabulary any non-expert can understand.  
        6. Reply with the sentence only—no bullet points, no commentary.

        ### EXAMPLES  
        INPUT:  
        Attack Type: Phishing  
        Location: UK bank  
        Description: Enter the link here and login to your banking systems! 
        OUTPUT:  
        A phishing attack on a UK bank tricking staff into revealing login details.  

        INPUT:  
        Attack Type: DDoS  
        Location: Government website (Brazil)  
        Description: Flood of traffic from botnet.  
        OUTPUT:  
        A DDoS attack on a Brazilian government website overwhelmed servers with botnet traffic.
    """)
    
    # Build the detail string based on event source
    if event.source == "OTX":
        detail = (
            f"Attack Name: {event.otx_name or 'Unknown'}\n"
            f"Attack Description: {event.otx_description or 'No description provided'}"
        )
    elif event.source == "AbuseIPDB":
        detail = (
            f"Attacker's Country: {event.abuse_attacker_country or 'Unknown'}\n"
            f"Victim's Country: {event.abuse_victim_country or 'Unknown'}\n"
            f"Attack Description: {event.abuse_attack or 'No description provided'}"
        )
    else:
        raise ValueError(f"Unknown event source: {event.source!r}")
    
    prompt = f"{prefix}\n{detail}\n"

    # concurrently create subprocesses for each mistral call
    proc = await asyncio.create_subprocess_exec(
        "ollama", "run", "mistral",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    stdout, stderr = await proc.communicate(prompt.encode("utf-8"))
    
    if proc.returncode != 0:
        raise RuntimeError(
            f"Mistral failed with code {proc.returncode}\n"
            f"Error: {stderr.decode().strip()}"
        )
    
    return stdout.decode().strip()


# def create_arc_json(event):
#     prompt = f"""
#         Create a JSON response with the following format:

#         IP: {event['ip']}
#         Type: {event['type']}
#         Location: {event['geo']}
#         Time: {event['timestamp']}
#         Details: {event['details']}
#         """
#     result = subprocess.run(
#         ['ollama', 'run', 'mistral'],
#         input=prompt.encode(),
#         stdout=subprocess.PIPE
#     )
#     return result.stdout.decode()