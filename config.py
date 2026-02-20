from dotenv import load_dotenv
import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TFL_APP_KEY = os.getenv("TFL_APP_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# 40 postcode districts covering inner and outer London across all compass
# directions and zones. Mix of central (Z1), inner (Z2-3), outer (Z3-6).
LONDON_POSTCODE_DISTRICTS = [
    # Central – Zone 1
    "EC1", "WC1", "SW1", "W1",
    # Inner North
    "N1", "N4", "NW1", "NW3",
    # Inner East
    "E1", "E2",
    # Inner South-East
    "SE1", "SE5",
    # Inner South-West
    "SW4", "SW8",
    # Inner West
    "W2", "W6",
    # Inner North-West
    "NW6",
    # Outer North
    "N13", "N21", "EN1",
    # Outer North-East
    "E11", "E17", "IG1",
    # Outer East
    "RM1",
    # Outer South-East
    "SE9", "SE18", "DA1", "BR1", "BR3",
    # Outer South
    "CR0", "SM1",
    # Outer South-West
    "SW16", "SW19", "KT1", "TW1",
    # Outer West
    "W5", "W13", "UB1",
    # Outer North-West
    "NW9", "HA1",
]

SCORING_DIMENSIONS = {
    "safety": "Safety",
    "green_space": "Green Space",
    "nightlife": "Nightlife",
    "transport": "Transport",
    "rent": "Rent",
}
