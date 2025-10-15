import os
import json
import textwrap
from typing import Optional, Dict, Any
from mistralai import Mistral

async def summarize_event(event) -> str:
    """
    Connects to the Mistral AI API to summarize event details.
    Uses the modern Mistral SDK with async support.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY environment variable not set.")

    # Initialize the modern Mistral client
    client = Mistral(api_key=api_key)

    # Build the detail string based on event source
    # Handle simulated events (which have different attributes)
    if hasattr(event, 'source'):
        if event.source == "OTX":
            user_input_detail = textwrap.dedent(f"""
                Attack Name: {event.otx_name or 'Unknown'}
                Attack Description: {event.otx_description or 'No description provided'}
                Victim's Country: {event.otx_country or 'Unknown'}
            """).strip()
        elif event.source == "AbuseIPDB":
            user_input_detail = textwrap.dedent(f"""
                Attacker's Country: {event.abuse_attacker_country or 'Unknown'}
                Victim's Country: {event.abuse_victim_country or 'Unknown'}
                Attack Description: {event.abuse_attack or 'No description provided'}
            """).strip()
        else:
            raise ValueError(f"Unknown event source: {event.source!r}")
    else:
        # Simulated event structure
        user_input_detail = textwrap.dedent(f"""
            Event Type: {event.event_type or 'Unknown'}
            Source IP: {event.source_ip or 'Unknown'}
            Description: {event.description or 'No description provided'}
            Severity: {event.severity or 'Unknown'}
            Protocol: {event.raw_data.get('protocol', 'Unknown') if event.raw_data else 'Unknown'}
            Port: {event.raw_data.get('port', 'Unknown') if event.raw_data else 'Unknown'}
            Country: {event.raw_data.get('country', 'Unknown') if event.raw_data else 'Unknown'}
            Threat Score: {event.raw_data.get('threat_score', 'Unknown') if event.raw_data else 'Unknown'}
        """).strip()

    # send just event details (instructions are configured on LLM agent)
    messages = [
        {
            "role": "user",
            "content": user_input_detail
        },
    ]

    try:
        # Use the agent configured in Le Platform
        agent_id = os.getenv("MISTRAL_AGENT_ID", "ag:9cb2eb21:20251005:hacktrackai:51b9f218")
        
        response = await client.agents.complete_async(
            agent_id=agent_id,
            messages=messages,
        )
        
        # Extract the response content
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        raise RuntimeError(f"Mistral Agent API call failed: {e}") from e


def create_arc_json(event) -> Optional[Dict[str, Any]]:
    """
    Creates a JSON object for ARC visualization.

    Args:
        event: An object with attributes for event details.

    Returns:
        Optional[Dict[str, Any]]: Coordinates for source and destination countries.
    """
    try:
        with open("backend/utils/countries_centroids.json", "r") as f:
            country_coords = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Failed to load country coordinates: {e}")
        return None

    src, dst = None, None
    
    # Handle original event structure with source attribute
    if hasattr(event, 'source'):
        if event.source == "AbuseIPDB":
            src = country_coords.get(event.abuse_attacker_country)
            dst = country_coords.get(event.abuse_victim_country)
        elif event.source == "OTX":
            dst = country_coords.get(event.otx_country)
    else:
        # Handle simulated events with raw_data
        if event.raw_data and 'country' in event.raw_data:
            dst = country_coords.get(event.raw_data['country'])

    if not dst and not src:
        return None
    
    return {"src": src or [0, 0], "dst": dst}