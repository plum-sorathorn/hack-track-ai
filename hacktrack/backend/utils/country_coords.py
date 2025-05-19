import json
import os

HERE = os.path.dirname(__file__)
JSON_PATH = os.path.join(HERE, "backend/utils/countries_centroids.json")

with open(JSON_PATH, "r", encoding="utf-8") as f:
    COUNTRY_CENTROIDS = json.load(f)

def get_country_centroid(country_name: str):
    """Return the centroid (lon, lat) for a given country name."""
    return COUNTRY_CENTROIDS.get(country_name, [0.0, 0.0])
