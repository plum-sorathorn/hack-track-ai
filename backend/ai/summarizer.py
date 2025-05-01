import subprocess

def summarize_event(event):
    prompt = f"""
        Explain this cyber event in simple English, understandable for the laymen:
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