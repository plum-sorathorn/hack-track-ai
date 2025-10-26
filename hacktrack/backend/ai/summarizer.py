import os
import json
import textwrap
from typing import Optional, Dict, Any, TypedDict, Tuple # Added Tuple import
from mistralai import Mistral
import random # Added for randomization

# Define the expected JSON output structure (full country names)
class SummaryOutput(TypedDict):
    summary: str
    attacker_country: str
    victim_country: str

# New type hint for the return value of get_coords_or_random
ResolvedCoordTuple = Tuple[Optional[Dict[str, float]], str] 

# Changed return type to SummaryOutput
async def summarize_event(event) -> SummaryOutput:
    """
    Connects to the Mistral AI API to summarize event details.
    Uses the modern Mistral SDK with async support.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY environment variable not set.")

    # Initialize the modern Mistral client
    client = Mistral(api_key=api_key)

    attacker_country = 'None'
    victim_country = 'None'
    description = 'No description provided'
    
    if hasattr(event, 'source'):
        if event.source == "OTX":
            description = event.otx_description or 'No description provided'
            victim_country = event.otx_country or 'None'
            user_input_detail = textwrap.dedent(f"""
                Attack Name: {event.otx_name or 'Unknown'}
                Attack Description: {description}
                Victim's Country: {victim_country}
                Attacker's Country: {attacker_country} 
            """).strip()
        elif event.source == "AbuseIPDB":
            description = event.abuse_attack or 'No description provided'
            attacker_country = event.abuse_attacker_country or 'None'
            victim_country = event.abuse_victim_country or 'None'
            user_input_detail = textwrap.dedent(f"""
                Attacker's Country: {attacker_country}
                Victim's Country: {victim_country}
                Attack Description: {description}
            """).strip()
        else:
            raise ValueError(f"Unknown event source: {event.source!r}")
    else:
        # Simulated event structure - pass as much context as possible
        raw_data = event.raw_data if hasattr(event, 'raw_data') and event.raw_data else {}
        
        user_input_detail = textwrap.dedent(f"""
            Event Type: {event.event_type or 'Unknown'}
            Source IP: {event.source_ip or 'Unknown'}
            Description: {event.description or 'No description provided'}
            Severity: {event.severity or 'Unknown'}
            Protocol: {raw_data.get('protocol', 'Unknown')}
            Port: {raw_data.get('port', 'Unknown')}
            Victim's Country: {raw_data.get('country', 'None')} 
            Threat Score: {raw_data.get('threat_score', 'Unknown')}
            Attacker's Country: None
        """).strip()

    messages = [
        {
            "role": "user",
            "content": user_input_detail
        },
    ]

    response = None
    try:
        agent_id = os.getenv("MISTRAL_AGENT_ID", "ag:9cb2eb21:20251005:hacktrackai:51b9f218")
        
        response = await client.agents.complete_async(
            agent_id=agent_id,
            messages=messages,
        )
        
        # Parse the JSON response
        json_content = response.choices[0].message.content.strip()
        summary_output: SummaryOutput = json.loads(json_content)
        
        if not all(k in summary_output for k in ["summary", "attacker_country", "victim_country"]):
            raise ValueError("Mistral agent returned invalid JSON structure.")
        
        return summary_output
        
    except Exception as e:
        raw_response = response.choices[0].message.content if response and response.choices else 'N/A'
        raise RuntimeError(f"Mistral Agent API call failed or returned unparsable JSON: {e}\nRaw AI Response: {raw_response}") from e


# Signature changed to accept country names, not the event object
def create_arc_json(attacker_country_name: str, victim_country_name: str) -> Optional[Dict[str, Any]]:
    """
    Creates a JSON object for ARC visualization using AI-inferred full country names.
    If a country name is not found in the centroids file, it uses a random country's coordinates.
    The function returns a dictionary containing the 'arc' coordinates and the 
    'resolved_names' (the actual country names used for plotting).
    """
    try:
        with open("backend/utils/countries_centroids.json", "r") as f:
            country_coords = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Failed to load country coordinates: {e}")
        return None

    # Get a list of all country names that have coordinates, excluding "Undetermined"
    valid_country_names = [
        name for name in country_coords.keys() 
        if name.strip() != "Undetermined" and country_coords[name] is not None
    ]
    
    # Helper to get coordinates AND the resolved country name
    def get_coords_or_random(country_name: str, coords_map: Dict[str, Any], valid_names: list) -> ResolvedCoordTuple:
        """Looks up coordinates, or returns coordinates of a random valid country, and the resolved name."""
        
        name_to_check = country_name.strip()
        coords = coords_map.get(name_to_check)
        
        if coords:
            # Found the specific country.
            return coords, name_to_check
        
        if valid_names:
            # Not found, prioritize randomization. Return the random country's name.
            random_name = random.choice(valid_names)
            return coords_map[random_name], random_name
        
        # Last resort: return None coordinates and 'Unknown' name.
        return None, 'Unknown'


    # Use the helper function for both source (attacker) and destination (victim)
    final_src_coords, resolved_attacker_name = get_coords_or_random(attacker_country_name, country_coords, valid_country_names)
    final_dst_coords, resolved_victim_name = get_coords_or_random(victim_country_name, country_coords, valid_country_names)
    
    # Fallback to "Undetermined" coordinates if random choice also failed (i.e., country_centroids was near empty)
    default_coords = country_coords.get("Undetermined")
    
    # Apply Undetermined fallback coordinates if necessary
    final_src_coords = final_src_coords if final_src_coords else default_coords
    final_dst_coords = final_dst_coords if final_dst_coords else default_coords
    
    # If neither source nor destination could be resolved (even randomly or to Undetermined), return None
    if not final_src_coords and not final_dst_coords:
        return None
        
    return {
        "arc": {
            "src": final_src_coords, 
            "dst": final_dst_coords
        },
        "resolved_names": {
            "attacker_country": resolved_attacker_name,
            "victim_country": resolved_victim_name,
        }
    }